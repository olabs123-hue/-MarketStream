"""C++17 top-of-book validation with a transparent local Python fallback."""
import ctypes
import os
from pathlib import Path

LIBRARY = Path(__file__).resolve().parents[1] / "engine" / "libmarketbook.so"

def top_of_book(bids: list[list[float]], asks: list[list[float]]) -> dict:
    if not bids or len(bids) != len(asks) or len(bids) > 1000:
        raise ValueError("Invalid depth")
    bp = [int(round(x[0]*100)) for x in bids]
    ap = [int(round(x[0]*100)) for x in asks]
    if min(bp+ap) <= 0:
        raise ValueError("Prices must be positive")
    if LIBRARY.is_file():
        lib = ctypes.CDLL(str(LIBRARY))
        lib.ms_top_of_book.argtypes = [ctypes.POINTER(ctypes.c_int64), ctypes.POINTER(ctypes.c_int64), ctypes.c_size_t, ctypes.POINTER(ctypes.c_int64)]
        lib.ms_top_of_book.restype = ctypes.c_int
        n = len(bp)
        Arr = ctypes.c_int64 * n
        out = (ctypes.c_int64 * 3)()
        rc = lib.ms_top_of_book(Arr(*bp), Arr(*ap), n, out)
        if rc:
            raise ValueError(f"Invalid native book: {rc}")
        bid, ask, spread = [int(x) for x in out]
        processor = "cpp17"
    else:
        if os.getenv("MARKETSTREAM_REQUIRE_NATIVE") == "1":
            raise RuntimeError("Native processor required but unavailable")
        bid, ask = max(bp), min(ap)
        if bid >= ask:
            raise ValueError("Crossed book")
        spread = ask - bid
        processor = "python-fallback"
    return {"best_bid":bid/100, "best_ask":ask/100, "spread":spread/100, "processor":processor}
