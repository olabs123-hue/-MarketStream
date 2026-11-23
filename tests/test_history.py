"""Storage-contract tests run against SQLite and an optional PostgreSQL URL."""
import uuid

from fastapi.testclient import TestClient

from backend.app import app
from backend.history import backend_name, record, recent, replay


def test_retention_and_cursor_replay():
    symbol = "TEST-" + uuid.uuid4().hex
    for i in range(6):
        record(symbol, 100.0 + i, f"2026-01-01T00:00:0{i}Z", keep=4)
    latest = recent(symbol, limit=10)
    assert [round(x["price"]) for x in latest] == [102, 103, 104, 105]

    page1 = replay(symbol, limit=2)
    assert [round(x["price"]) for x in page1["ticks"]] == [102, 103]
    assert page1["has_more"] is True

    page2 = replay(symbol, after_id=page1["next_after_id"], limit=2)
    assert [round(x["price"]) for x in page2["ticks"]] == [104, 105]
    assert page2["has_more"] is False
    assert replay(symbol, after_id=page2["next_after_id"])["ticks"] == []


def test_replay_rejects_bad_limits():
    for kwargs in ({"limit": 0}, {"limit": 501}, {"after_id": -1}):
        try:
            replay("BTC-USD", **kwargs)
            assert False, "invalid replay parameters were accepted"
        except ValueError:
            pass


def test_replay_rest_contract():
    with TestClient(app) as client:
        response = client.get("/api/replay/BTC-USD?limit=2")
        assert response.status_code == 200
        data = response.json()
        assert data["symbol"] == "BTC-USD"
        assert data["simulated"] is True
        assert data["source"] == backend_name()
        assert len(data["ticks"]) <= 2
        assert isinstance(data["next_after_id"], int)
        assert client.get("/api/replay/BTC-USD?limit=501").status_code == 422
        assert client.get("/api/replay/INVALID").status_code == 404
