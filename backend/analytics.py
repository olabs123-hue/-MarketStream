"""Deterministic market-microstructure features on synthetic, validated L2 books.

Quantities are treated as simulated units. No trades, VWAP, market signals,
exchange prices, or predictive claims are produced by this module.
"""
import math


def book_analytics(bids: list[list[float]], asks: list[list[float]]) -> dict:
    """Compute normalized quote statistics from complete sorted L2 snapshots.

    All prices are rounded to integer cents and quantities to integer
    thousandths before calculations to match the existing C++ bridge.
    """
    if not 1 <= len(bids) <= 1000 or not 1 <= len(asks) <= 1000:
        raise ValueError("Expected nonempty bounded depth")
    def parse(levels):
        values = []
        for level in levels:
            if not isinstance(level, (list, tuple)) or len(level) != 2:
                raise ValueError("Expected [price, quantity] levels")
            p, q = level
            if isinstance(p, bool) or isinstance(q, bool) or not isinstance(p, (int, float)) or not isinstance(q, (int, float)):
                raise ValueError("Invalid level types")
            if not math.isfinite(p) or not math.isfinite(q):
                raise ValueError("Non-finite market depth")
            cents = round(p * 100)
            milli_units = round(q * 1000)
            if cents <= 0 or milli_units <= 0:
                raise ValueError("Price and size must be positive")
            values.append((cents, milli_units))
        return values
    b, a = parse(bids), parse(asks)
    if any(b[i][0] <= b[i + 1][0] for i in range(len(b) - 1)):
        raise ValueError("Bids must be strictly descending")
    if any(a[i][0] >= a[i + 1][0] for i in range(len(a) - 1)):
        raise ValueError("Asks must be strictly ascending")
    best_bid, best_ask = b[0][0], a[0][0]
    if best_bid >= best_ask:
        raise ValueError("Crossed or locked synthetic book")
    bid_quantity = sum(q for _, q in b)
    ask_quantity = sum(q for _, q in a)
    total = bid_quantity + ask_quantity
    best_bid_quantity, best_ask_quantity = b[0][1], a[0][1]
    mid_cents = (best_bid + best_ask) / 2
    micro_cents = (best_ask * best_bid_quantity + best_bid * best_ask_quantity) / (best_bid_quantity + best_ask_quantity)
    return {
        "mid_price": round(mid_cents / 100, 4),
        "spread_bps": round((best_ask - best_bid) / mid_cents * 10000, 4),
        "microprice": round(micro_cents / 100, 4),
        "depth_imbalance": round((bid_quantity - ask_quantity) / total, 6),
        "bid_depth_units": round(bid_quantity / 1000, 3),
        "ask_depth_units": round(ask_quantity / 1000, 3),
        "best_bid_size_units": round(best_bid_quantity / 1000, 3),
        "best_ask_size_units": round(best_ask_quantity / 1000, 3),
    }


class AnalyticsBook:
    """Decorate the native stateful sequence engine, without changing its ABI."""
    def __init__(self, processor):
        self.processor = processor

    def make_delta(self, tick):
        return self.processor.make_delta(tick)

    def apply(self, event):
        validated_tick = self.processor.apply(event)
        features = book_analytics(validated_tick["bids"], validated_tick["asks"])
        if abs(features["spread_bps"] - validated_tick["spread"] / features["mid_price"] * 10000) > 0.001:
            raise ValueError("Book spread inconsistency")
        return {**validated_tick, "analytics": features}

    def close(self):
        self.processor.close()
