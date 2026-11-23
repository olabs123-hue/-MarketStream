"""Two independent fictional vendor payload formats and bounded failover router.

Both feeds derive *synthetic* quotes from the caller's generated reference price.
There are no network calls, exchange connections or external data vendors.
"""
import math
import time
from collections import deque
from dataclasses import dataclass

class FeedUnavailable(RuntimeError):
    pass

class InvalidVendorEvent(ValueError):
    pass

@dataclass(frozen=True)
class NormalizedQuote:
    symbol: str
    price: float
    source: str
    source_sequence: int
    failover: bool
    processing_us: float = 0.0
    failover_us: float | None = None
    attempts: int = 1

class SimulatedVendor:
    def __init__(self, name: str):
        if name not in ("SIM-A", "SIM-B"):
            raise ValueError("Unknown simulated source")
        self.name = name
        self.fail = False
        self._sequence = 0

    def read(self, symbol: str, reference_price: float) -> dict:
        if self.fail:
            raise FeedUnavailable(self.name)
        self._sequence += 1
        # Intentionally different imaginary vendor payload schemas.
        if self.name == "SIM-A":
            return {"ticker": symbol, "px": reference_price,
                    "vendor_seq": self._sequence}
        return {"instrument": symbol.replace("-", "/"),
                "last_price": f"{reference_price:.6f}", "n": self._sequence}


def normalize(source: str, raw: dict, expected_symbol: str) -> tuple[float, int]:
    if source == "SIM-A":
        symbol, price, sequence = raw.get("ticker"), raw.get("px"), raw.get("vendor_seq")
    elif source == "SIM-B":
        value = raw.get("instrument")
        symbol = value.replace("/", "-") if isinstance(value, str) else None
        price, sequence = raw.get("last_price"), raw.get("n")
    else:
        raise InvalidVendorEvent("Unknown source")
    if symbol != expected_symbol:
        raise InvalidVendorEvent("Vendor symbol mismatch")
    if isinstance(price, bool) or not isinstance(price, (int, float, str)):
        raise InvalidVendorEvent("Bad vendor price")
    try:
        normalized_price = float(price)
    except (ValueError, OverflowError):
        raise InvalidVendorEvent("Bad vendor price")
    if not math.isfinite(normalized_price) or normalized_price <= 0:
        raise InvalidVendorEvent("Bad vendor price")
    if type(sequence) is not int or sequence < 1:
        raise InvalidVendorEvent("Invalid source sequence")
    return normalized_price, sequence


class SourceRouter:
    """Per-symbol local process router; one preferred vendor and one backup."""
    def __init__(self, symbol: str, primary=None, backup=None):
        self.symbol = symbol
        self.sources = [primary or SimulatedVendor("SIM-A"),
                        backup or SimulatedVendor("SIM-B")]
        self.active = 0
        self.last_seen = {}
        self.failovers = 0
        self.duplicates_rejected = 0
        self.failed_attempts = 0
        self.processing_samples_us = deque(maxlen=256)
        self.failover_samples_us = deque(maxlen=256)

    def _accept(self, source, raw):
        price, sequence = normalize(source.name, raw, self.symbol)
        prior = self.last_seen.get(source.name, 0)
        if sequence <= prior:
            self.duplicates_rejected += 1
            raise InvalidVendorEvent("Duplicate or stale vendor sequence")
        self.last_seen[source.name] = sequence
        return price, sequence

    def next(self, reference_price: float) -> NormalizedQuote:
        """Read at most two in-process synthetic sources; measure synchronous cost.

        Measurements include local Python read + normalization + selection, but
        exclude simulated tick generation, C++, persistence, network and sockets.
        """
        started = time.perf_counter_ns()
        failures = 0
        for index in (self.active, 1 - self.active):
            source = self.sources[index]
            try:
                price, sequence = self._accept(
                    source, source.read(self.symbol, reference_price))
            except (FeedUnavailable, InvalidVendorEvent):
                self.failed_attempts += 1
                failures += 1
                continue
            switched = index != self.active
            if switched:
                self.failovers += 1
                self.active = index
            elapsed = max(0.0, (time.perf_counter_ns() - started) / 1000)
            self.processing_samples_us.append(elapsed)
            failover_us = elapsed if switched else None
            if failover_us is not None:
                self.failover_samples_us.append(failover_us)
            return NormalizedQuote(self.symbol, price, source.name,
                                   sequence, switched,
                                   processing_us=round(elapsed, 3),
                                   failover_us=round(failover_us, 3) if failover_us is not None else None,
                                   attempts=failures + 1)
        raise FeedUnavailable("Both simulated sources unavailable or invalid")

    def close(self):
        pass
