"""Per-producer C++17 level-book lifecycle and snapshot-to-delta adapter.

When the optional shared library is absent, a precisely labeled Python
reference implementation supports local development. Render requires native.
"""
import ctypes
import math
import os
from pathlib import Path

LIBRARY = Path(__file__).resolve().parents[1] / "engine" / "libmarketbook.so"


def encode(levels: list[list[float]]) -> dict[int, int]:
    if not 1 <= len(levels) <= 1000:
        raise ValueError("Invalid level count")
    result = {}
    for level in levels:
        if len(level) != 2 or not all(math.isfinite(float(x)) for x in level):
            raise ValueError("Non-finite level")
        price, quantity = (int(round(float(level[0]) * 100)),
                           int(round(float(level[1]) * 1000)))
        if price <= 0 or quantity <= 0 or price in result:
            raise ValueError("Invalid or duplicate price level")
        result[price] = quantity
    return result


class StatefulBook:
    def __init__(self):
        self._lib = None
        self._handle = None
        self._bids: dict[int, int] = {}
        self._asks: dict[int, int] = {}
        if LIBRARY.is_file():
            lib = ctypes.CDLL(str(LIBRARY))
            lib.ms_state_new.argtypes = []
            lib.ms_state_new.restype = ctypes.c_void_p
            lib.ms_state_free.argtypes = [ctypes.c_void_p]
            lib.ms_state_free.restype = None
            lib.ms_state_replace.argtypes = [
                ctypes.c_void_p,
                ctypes.POINTER(ctypes.c_int64), ctypes.POINTER(ctypes.c_int64), ctypes.c_size_t,
                ctypes.POINTER(ctypes.c_int64), ctypes.POINTER(ctypes.c_int64), ctypes.c_size_t,
                ctypes.POINTER(ctypes.c_int64)]
            lib.ms_state_replace.restype = ctypes.c_int
            handle = lib.ms_state_new()
            if not handle:
                raise RuntimeError("Failed to allocate native level book")
            self._lib = lib
            self._handle = handle
        elif os.getenv("MARKETSTREAM_REQUIRE_NATIVE") == "1":
            raise RuntimeError("Required native stateful book unavailable")

    def close(self):
        if self._handle is not None:
            self._lib.ms_state_free(self._handle)
            self._handle = None

    def apply(self, tick: dict) -> dict:
        if self._lib is not None and self._handle is None:
            raise RuntimeError("Order book already closed")
        bids = encode(tick["bids"])
        asks = encode(tick["asks"])
        if max(bids) >= min(asks):
            raise ValueError("Crossed level book")
        if self._handle is not None:
            def arr(values):
                return (ctypes.c_int64 * len(values))(*values)
            out = (ctypes.c_int64 * 6)()
            rc = self._lib.ms_state_replace(
                self._handle, arr(list(bids)), arr(list(bids.values())), len(bids),
                arr(list(asks)), arr(list(asks.values())), len(asks), out)
            if rc:
                raise ValueError(f"Native level-book update failed: {rc}")
            best_bid, best_ask, spread, bid_count, ask_count, applied = map(int, out)
            mode = "cpp17-stateful"
        else:
            applied = sum(1 for p, q in bids.items() if self._bids.get(p) != q)
            applied += sum(1 for p in self._bids if p not in bids)
            applied += sum(1 for p, q in asks.items() if self._asks.get(p) != q)
            applied += sum(1 for p in self._asks if p not in asks)
            best_bid, best_ask = max(bids), min(asks)
            spread = best_ask - best_bid
            bid_count, ask_count = len(bids), len(asks)
            mode = "python-stateful-fallback"
        self._bids = bids
        self._asks = asks
        if (best_bid != max(bids) or best_ask != min(asks)
                or bid_count != len(bids) or ask_count != len(asks)):
            raise ValueError("Stateful book diverged from generated snapshot")
        return {
            **tick, "spread": round(spread / 100, 2),
            "processor": mode,
            "book_levels": {"bids": bid_count, "asks": ask_count},
            "level_updates": applied, "book_mode": "snapshot-delta-reconciliation",
        }
