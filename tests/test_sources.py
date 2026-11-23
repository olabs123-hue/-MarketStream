"""Synthetic source normalization, deduplication, failover and WebSocket integration."""
import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.sources import (SimulatedVendor, SourceRouter, FeedUnavailable,
                             InvalidVendorEvent, normalize)


def test_vendor_formats_normalize_to_same_market_quote():
    assert normalize("SIM-A", {"ticker":"BTC-USD", "px":101.25, "vendor_seq":3}, "BTC-USD") == (101.25, 3)
    assert normalize("SIM-B", {"instrument":"BTC/USD", "last_price":"101.250000", "n":3}, "BTC-USD") == (101.25, 3)


@pytest.mark.parametrize("source,raw", [
    ("SIM-A", {"ticker":"ETH-USD","px":1,"vendor_seq":1}),
    ("SIM-A", {"ticker":"BTC-USD","px":-1,"vendor_seq":1}),
    ("SIM-A", {"ticker":"BTC-USD","px":float("inf"),"vendor_seq":1}),
    ("SIM-B", {"instrument":"BTC/USD","last_price":"not-a-price","n":1}),
    ("SIM-B", {"instrument":"BTC/USD","last_price":"101","n":0}),
])
def test_bad_vendor_events_rejected(source, raw):
    with pytest.raises(InvalidVendorEvent):
        normalize(source, raw, "BTC-USD")


def test_failover_to_backup_and_reject_duplicate_sequence():
    primary, backup = SimulatedVendor("SIM-A"), SimulatedVendor("SIM-B")
    router = SourceRouter("BTC-USD", primary, backup)
    first = router.next(101.25)
    assert first.source == "SIM-A" and first.source_sequence == 1
    with pytest.raises(InvalidVendorEvent):
        router._accept(primary, {"ticker":"BTC-USD", "px":101.25, "vendor_seq":1})
    assert router.duplicates_rejected == 1
    primary.fail = True
    second = router.next(101.5)
    assert second.source == "SIM-B" and second.failover and router.failovers == 1
    third = router.next(101.75)
    assert third.source == "SIM-B" and not third.failover
    backup.fail = True
    with pytest.raises(FeedUnavailable):
        router.next(102)
    backup.fail = False
    fourth = router.next(102)
    assert fourth.source == "SIM-B" and fourth.source_sequence == 3


def test_live_websocket_exposes_vendor_metadata():
    with TestClient(app) as client:
        with client.websocket_connect("/ws/ETH-USD") as socket:
            first = socket.receive_json()
            assert first["source"] == "SIM-A"
            assert first["source_sequence"] == 1
            assert first["source_failover"] is False
            assert first["simulated"] is True
            assert first["analytics"]["spread_bps"] > 0
            status = client.get("/api/stream-status").json()
            assert "source_failovers" in status
