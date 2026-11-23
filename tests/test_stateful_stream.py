"""Stateful C++ order-book snapshot parity and streaming integration tests."""
import asyncio
import pytest
from fastapi.testclient import TestClient
from backend.app import app, snapshot
from backend.stateful import StatefulBook


def test_stateful_snapshots_and_rejected_crossed_book():
    book = StatefulBook()
    try:
        one = book.apply(snapshot("BTC-USD", 68000.0, 0))
        two = book.apply(snapshot("BTC-USD", 68002.0, 1))
        same = book.apply(snapshot("BTC-USD", 68002.0, 1))
        assert one["book_levels"] == {"bids": 8, "asks": 8}
        assert two["level_updates"] > 0
        assert same["level_updates"] == 0
        for tick in (one, two):
            assert tick["spread"] == round(tick["asks"][0][0] - tick["bids"][0][0], 2)
            assert tick["processor"] in ("cpp17-stateful", "python-stateful-fallback")
        bad = snapshot("BTC-USD", 68000.0, 3)
        bad["asks"][0][0] = bad["bids"][0][0]
        with pytest.raises(ValueError):
            book.apply(bad)
        # A rejected update must not corrupt accepted state.
        assert book.apply(snapshot("BTC-USD", 68002.0, 1))["level_updates"] == 0
    finally:
        book.close()


def test_live_websocket_uses_stateful_book():
    with TestClient(app) as client:
        with client.websocket_connect("/ws/ETH-USD") as ws:
            tick = ws.receive_json()
            assert tick["processor"] in ("cpp17-stateful", "python-stateful-fallback")
            assert tick["book_levels"] == {"bids": 8, "asks": 8}
            assert tick["level_updates"] == 16
            assert tick["spread"] == round(tick["asks"][0][0] - tick["bids"][0][0], 2)
