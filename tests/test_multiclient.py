"""Multi-client live ASGI WebSocket behavior (simulated data only)."""
from fastapi.testclient import TestClient
from backend.app import app


def test_multiple_clients_share_one_symbol_producer():
    with TestClient(app) as client:
        with client.websocket_connect("/ws/ETH-USD") as first:
            a = first.receive_json()
            with client.websocket_connect("/ws/ETH-USD") as second:
                b = second.receive_json()
                status = client.get("/api/stream-status").json()
                assert a["symbol"] == b["symbol"] == "ETH-USD"
                assert status["connected_subscribers"] >= 2
                assert status["active_symbols"] >= 1
                # The second user must join the existing stream (sequence > 0
                # if a tick has elapsed) rather than creating a separate symbol.
                assert b["sequence"] >= a["sequence"]
