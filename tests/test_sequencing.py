"""Sequence continuity, fail-closed deltas, and simulated snapshot recovery."""
import pytest
from fastapi.testclient import TestClient

from backend.app import app, snapshot
from backend.sequencing import SequencedBook, SequenceError, SequenceGapError


def tick(seq, price=68000.0):
    return snapshot("BTC-USD", price, seq)


def test_incremental_events_and_native_parity():
    sequencer = SequencedBook()
    try:
        initial = sequencer.apply(tick(0))
        assert initial["event_type"] == "snapshot"
        assert not initial["resynchronized"]
        target = tick(1, 68002.0)
        event = sequencer.make_delta(target)
        assert event["event_type"] == "delta"
        out = sequencer.apply(event)
        assert out["sequence"] == 1
        assert out["event_type"] == "delta"
        assert out["bids"] == target["bids"]
        assert out["asks"] == target["asks"]
        assert out["spread"] == round(target["asks"][0][0] - target["bids"][0][0], 2)
        assert out["processor"] in ("cpp17-stateful", "python-stateful-fallback")
        with pytest.raises(SequenceError):
            sequencer.apply(event)  # duplicate must never mutate state
        assert sequencer.last_sequence == 1
    finally:
        sequencer.close()


def test_gap_rejection_and_authoritative_snapshot_resync():
    sequencer = SequencedBook()
    try:
        sequencer.apply(tick(0))
        missed = sequencer.make_delta(tick(2, 68003.0))
        with pytest.raises(SequenceGapError):
            sequencer.apply(missed)
        assert sequencer.needs_snapshot
        assert sequencer.last_sequence == 0
        with pytest.raises(SequenceGapError):
            sequencer.apply({**missed, "sequence": 1})
        recovered = sequencer.apply(tick(3, 68003.0))
        assert recovered["resynchronized"] is True
        assert recovered["sequence_gaps_detected"] == 1
        assert not sequencer.needs_snapshot
        followup = sequencer.apply(sequencer.make_delta(tick(4, 68004.0)))
        assert followup["event_type"] == "delta"
        assert followup["sequence"] == 4
        with pytest.raises(SequenceError):
            sequencer.apply(tick(3))
    finally:
        sequencer.close()


def test_invalid_delta_is_atomic():
    sequencer = SequencedBook()
    try:
        first = sequencer.apply(tick(0))
        bad = {"event_type": "delta", "sequence": 1,
               "bids": [[first["bids"][0][0], -1]], "asks": []}
        with pytest.raises(SequenceError):
            sequencer.apply(bad)
        assert sequencer.last_sequence == 0
        assert not sequencer.needs_snapshot
        good = sequencer.apply(sequencer.make_delta(tick(1)))
        assert good["sequence"] == 1
    finally:
        sequencer.close()


def test_live_stream_sends_snapshot_then_delta():
    with TestClient(app) as client:
        with client.websocket_connect("/ws/SOL-USD") as ws:
            first = ws.receive_json()
            second = ws.receive_json()
            assert first["event_type"] == "snapshot"
            assert second["event_type"] == "delta"
            assert first["sequence"] == 0
            assert second["sequence"] == 1
            assert second["book_levels"] == {"bids": 8, "asks": 8}
            assert second["simulated"] is True
