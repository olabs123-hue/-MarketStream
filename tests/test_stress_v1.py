"""Repeatable stateful-book stress and recovery scenarios.

These tests assert correctness/invariants, not a latency or throughput target.
All data is synthetic. The CI job also runs them against the compiled C++ ABI.
"""
import random

from backend.app import snapshot
from backend.sequencing import SequencedBook, SequenceError, SequenceGapError


def test_500_consecutive_market_depth_updates_and_snapshot_recovery():
    book = SequencedBook()
    try:
        randomizer = random.Random(20261123)
        accepted = 0
        previous = None
        for i in range(500):
            price = 68000 + randomizer.uniform(-8, 8)
            target = snapshot("BTC-USD", price, i)
            event = target if i % 30 == 0 else book.make_delta(target)
            result = book.apply(event)
            assert result["sequence"] == i
            assert result["book_levels"] == {"bids": 8, "asks": 8}
            assert result["bids"] == target["bids"]
            assert result["asks"] == target["asks"]
            assert result["spread"] == round(result["asks"][0][0] - result["bids"][0][0], 2)
            assert result["level_updates"] >= 0
            if previous is not None:
                assert result["sequence"] == previous + 1
            previous = result["sequence"]
            accepted += 1
        assert accepted == 500
        assert book.gaps_detected == 0
        assert book.resyncs == 0
    finally:
        book.close()


def test_gap_fault_injection_followed_by_resynchronization():
    book = SequencedBook()
    try:
        for seq in range(5):
            full = snapshot("ETH-USD", 3475 + seq, seq)
            book.apply(full if seq == 0 else book.make_delta(full))
        interrupted = book.make_delta(snapshot("ETH-USD", 3481, 6))
        with __import__("pytest").raises(SequenceGapError):
            book.apply(interrupted)
        assert book.needs_snapshot
        assert book.last_sequence == 4
        recovered = book.apply(snapshot("ETH-USD", 3482, 7))
        assert recovered["resynchronized"]
        assert recovered["sequence_gaps_detected"] == 1
        assert book.resyncs == 1
        next_tick = book.apply(book.make_delta(snapshot("ETH-USD", 3483, 8)))
        assert next_tick["sequence"] == 8
        with __import__("pytest").raises(SequenceError):
            book.apply(snapshot("ETH-USD", 3482, 7))
    finally:
        book.close()
