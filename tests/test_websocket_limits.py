"""WebSocket admission and status endpoint integration tests."""
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from backend.app import app, hub


def test_stream_status_endpoint():
    with TestClient(app) as client:
        result = client.get("/api/stream-status")
        assert result.status_code == 200
        data = result.json()
        assert data["mode"] == "simulation"
        assert data["max_subscribers"] >= 1
        assert data["max_per_symbol"] >= 1


def test_websocket_over_capacity_is_rejected():
    # TestClient handles these sequentially on the same app event loop.
    previous = hub.max_per_symbol
    hub.max_per_symbol = 1
    try:
        with TestClient(app) as client:
            with client.websocket_connect("/ws/BTC-USD") as first:
                assert first.receive_json()["sequence"] == 0
                try:
                    with client.websocket_connect("/ws/BTC-USD") as excess:
                        excess.receive_json()
                    assert False, "second websocket should have been rejected"
                except WebSocketDisconnect as exc:
                    assert exc.code == 1013
    finally:
        hub.max_per_symbol = previous
