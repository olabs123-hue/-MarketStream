import pytest
from backend.processor import top_of_book
from backend import history

def test_top_of_book():
    book = top_of_book([[99.98,2],[99.97,1]],[[100.02,2],[100.03,1]])
    assert book["spread"] == pytest.approx(0.04)
    assert book["best_bid"] == 99.98
    assert book["processor"] in ("cpp17","python-fallback")
    with pytest.raises(ValueError):
        top_of_book([[100.01,3]],[[100.0,1]])

def test_bounded_recorded_history(tmp_path,monkeypatch):
    monkeypatch.setattr(history,"DB_FILE",tmp_path/"ticks.sqlite3")
    for n in range(9):
        history.record("BTC-USD",100+n,"2026-01-01T00:00:00Z",keep=5)
    assert [r["price"] for r in history.recent("BTC-USD",100)] == [104,105,106,107,108]
    assert history.recent("ETH-USD") == []
