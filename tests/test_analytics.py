"""Bloomberg-aligned educational microstructure calculation contracts.

The tests use fictional quotes; the formulas do not produce a trading signal.
"""
import math
import pytest
from fastapi.testclient import TestClient
from backend.analytics import book_analytics, AnalyticsBook
from backend.app import app, snapshot
from backend.sequencing import SequencedBook
from backend.stateful import StatefulBook


def test_hand_calculated_mid_spread_microprice_imbalance():
    result = book_analytics([[100, 3]], [[102, 1]])
    assert result["mid_price"] == 101.0
    assert result["spread_bps"] == pytest.approx(198.0198, abs=0.0001)
    assert result["microprice"] == 101.5
    assert result["depth_imbalance"] == 0.5
    assert result["bid_depth_units"] == 3
    assert result["ask_depth_units"] == 1


@pytest.mark.parametrize("bids,asks", [
    ([], [[101, 1]]),
    ([[100, 1]], []),
    ([[101, 1]], [[101, 2]]),
    ([[102, 1]], [[101, 2]]),
    ([[100, 1], [101, 2]], [[102, 3]]),
    ([[100, 1]], [[102, 2], [101, 3]]),
    ([[100, -1]], [[102, 1]]),
    ([[100, float("nan")]], [[102, 1]]),
    ([[100, 1]], [[102, float("inf")]]),
    ([[True, 1]], [[102, 1]]),
])
def test_invalid_quote_is_rejected(bids, asks):
    with pytest.raises(ValueError):
        book_analytics(bids, asks)


def test_live_stream_matches_derived_statistics_and_rest_endpoint():
    with TestClient(app) as client:
        assert client.get("/api/analytics/UNKNOWN").status_code == 404
        with client.websocket_connect("/ws/BTC-USD") as socket:
            tick = socket.receive_json()
            assert tick["simulated"] is True
            assert tick["processor"] in ("cpp17-stateful", "python-stateful-fallback")
            assert tick["analytics"] == book_analytics(tick["bids"], tick["asks"])
            response = client.get("/api/analytics/BTC-USD")
            assert response.status_code == 200
            assert response.json()["status"] == "active"
            assert response.json()["analytics"] == tick["analytics"]
        assert client.get("/api/analytics/BTC-USD").json()["status"] == "no_active_feed"


def test_native_sequence_adapter_decorated_with_metrics():
    processor = AnalyticsBook(SequencedBook(StatefulBook()))
    try:
        initial = processor.apply(snapshot("ETH-USD", 3475, 0))
        next_tick = processor.apply(processor.make_delta(snapshot("ETH-USD", 3476, 1)))
        assert initial["event_type"] == "snapshot"
        assert next_tick["event_type"] == "delta"
        assert 0 < next_tick["analytics"]["spread_bps"] < 500
        assert -1 <= next_tick["analytics"]["depth_imbalance"] <= 1
        assert math.isfinite(next_tick["analytics"]["microprice"])
    finally:
        processor.close()
