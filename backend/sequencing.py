"""Sequence-aware simulated market-depth protocol adapter.

Full snapshots can recover a missing sequence. Incremental events require an
unbroken sequence. On a gap, deltas are rejected until an authoritative full
snapshot arrives. This is NOT an exchange protocol implementation.
"""
from backend.stateful import StatefulBook


class SequenceError(ValueError):
    pass


class SequenceGapError(SequenceError):
    pass


class SequencedBook:
    def __init__(self, book=None):
        self.book = book if book is not None else StatefulBook()
        self.last_sequence = None
        self.needs_snapshot = True
        self.last_tick = None
        self.gaps_detected = 0
        self.resyncs = 0

    def close(self):
        self.book.close()

    def _merged_levels(self, previous, updates, *, reverse):
        # Absolute quantity at a price; zero means delete.
        levels = {int(round(p * 100)): float(q) for p, q in previous}
        if len(updates) > 1000:
            raise SequenceError("Too many incremental updates")
        seen = set()
        for level in updates:
            if len(level) != 2:
                raise SequenceError("Invalid delta level")
            import math
            price, qty = float(level[0]), float(level[1])
            if not math.isfinite(price) or not math.isfinite(qty) or price <= 0 or qty < 0:
                raise SequenceError("Invalid delta price or quantity")
            cents = int(round(price * 100))
            if cents <= 0 or cents in seen:
                raise SequenceError("Duplicate or invalid delta price")
            seen.add(cents)
            if qty == 0:
                levels.pop(cents, None)
            else:
                levels[cents] = qty
        if not levels:
            raise SequenceError("A delta cannot empty a book side")
        ordered = sorted(levels.items(), key=lambda item: item[0], reverse=reverse)
        return [[p / 100, qty] for p, qty in ordered]

    def apply(self, event: dict) -> dict:
        sequence = event.get("sequence")
        if type(sequence) is not int or sequence < 0:
            raise SequenceError("Expected nonnegative integer sequence")
        event_type = event.get("event_type", "snapshot")
        if event_type not in ("snapshot", "delta"):
            raise SequenceError("Unsupported event type")
        if self.last_sequence is not None and sequence <= self.last_sequence:
            raise SequenceError("Duplicate or out-of-order event")
        expected = None if self.last_sequence is None else self.last_sequence + 1
        gap = expected is not None and sequence != expected

        if event_type == "delta":
            if gap:
                self.gaps_detected += 1
                self.needs_snapshot = True
                raise SequenceGapError("Missing incremental event; full snapshot required")
            if self.needs_snapshot or self.last_tick is None:
                raise SequenceGapError("Full snapshot required before deltas")
            # Validate and merge off to the side; only commit after native book accepts.
            base = self.last_tick
            bids = self._merged_levels(base["bids"], event.get("bids", []), reverse=True)
            asks = self._merged_levels(base["asks"], event.get("asks", []), reverse=False)
            candidate = {**base, **{k: v for k, v in event.items() if k not in ("bids", "asks")},
                         "bids": bids, "asks": asks, "sequence": sequence}
        else:
            candidate = dict(event)
            candidate["event_type"] = "snapshot"
            # Snapshot is an authoritative reset after dropped/missing deltas.
            if "bids" not in candidate or "asks" not in candidate:
                raise SequenceError("Snapshot must contain both sides")

        result = self.book.apply(candidate)
        result["event_type"] = event_type
        result["resynchronized"] = bool(event_type == "snapshot" and (gap or self.needs_snapshot) and self.last_sequence is not None)
        if result["resynchronized"]:
            self.resyncs += 1
        result["sequence_gaps_detected"] = self.gaps_detected
        self.last_sequence = sequence
        self.last_tick = result
        self.needs_snapshot = False
        return result
