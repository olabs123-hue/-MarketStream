"""Focused ingress and native boundary security regressions.

Origin checks limit browser subscriptions; they are NOT user authentication.
"""
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from backend.app import app
from backend.stateful import encode


def test_cross_origin_websocket_blocked():
    with TestClient(app) as client:
        with pytest.raises(WebSocketDisconnect) as err:
            with client.websocket_connect(
                "/ws/BTC-USD", headers={"origin": "https://evil.example"}
            ) as ws:
                ws.receive_json()
        assert err.value.code == 1008


def test_same_origin_websocket_allowed():
    with TestClient(app) as client:
        with client.websocket_connect(
            "/ws/BTC-USD", headers={"origin": "http://testserver"}
        ) as ws:
            assert ws.receive_json()["simulated"] is True


def test_native_price_and_quantity_range_checked():
    for levels in ([[1e20, 1]], [[100, 1e20]], [[float('inf'), 1]], [[0, 1]]):
        with pytest.raises(ValueError):
            encode([levels])


def test_origin_policy_rejects_bad_ports_and_scheme():
    from backend.app import allowed_websocket_origin
    from starlette.datastructures import Headers
    class WS:
        def __init__(self, origin):
            self.headers = Headers({"host": "marketstream.example", "origin": origin})
    for origin in ("https://marketstream.example:9999", "file://marketstream.example",
                   "https://evil.example", "https://marketstream.example/path"):
        assert not allowed_websocket_origin(WS(origin))
    assert allowed_websocket_origin(WS("https://marketstream.example"))
