"""Two independent fictional vendor payload formats and bounded failover router.

Both feeds derive *synthetic* quotes from the caller's generated reference price.
There are no network calls, exchange connections or external data vendors.
"""
import math
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

    def _accept(self, source, raw):
        price, sequence = normalize(source.name, raw, self.symbol)
        prior = self.last_seen.get(source.name, 0)
        if sequence <= prior:
            self.duplicates_rejected += 1
            raise InvalidVendorEvent("Duplicate or stale vendor sequence")
        self.last_seen[source.name] = sequence
        return price, sequence

    def next(self, reference_price: float) -> NormalizedQuote:
        # A bad primary quote triggers one backup attempt; never loop forever.
        for index in (self.active, 1 - self.active):
            source = self.sources[index]
            try:
                price, sequence = self._accept(
                    source, source.read(self.symbol, reference_price))
            except (FeedUnavailable, InvalidVendorEvent):
                continue
            switched = index != self.active
            if switched:
                self.failovers += 1
                self.active = index
            return NormalizedQuote(self.symbol, price, source.name,
                                   sequence, switched)
        raise FeedUnavailable("Both simulated sources unavailable or invalid")

    def close(self):
        pass
