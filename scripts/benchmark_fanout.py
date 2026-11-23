"""Reproducible in-process queue fanout microbenchmark.

This does not benchmark WebSocket delivery, C++ processing, database writes,
network throughput, or cross-instance fanout.
"""
import argparse
import asyncio
import json
import statistics
import time
from backend.hub import MarketHub


async def measure(subscribers: int, ticks: int) -> dict:
    hub = MarketHub({"BTC-USD": 100.0}, lambda s, p, i: {},
                    interval=3600, max_clients=max(1, subscribers),
                    max_per_symbol=max(1, subscribers))
    queues = [hub.subscribe("BTC-USD") for _ in range(subscribers)]
    # Let the producer run once; clear initial queued tick.
    await asyncio.sleep(0)
    for q in queues:
        if not q.empty():
            q.get_nowait()
    start = time.perf_counter()
    for seq in range(ticks):
        hub.publish("BTC-USD", {"sequence": seq})
    seconds = time.perf_counter() - start
    result = {
        "subscribers": subscribers,
        "ticks_published": ticks,
        "total_queue_deliveries": subscribers * ticks,
        "elapsed_seconds": round(seconds, 6),
        "ticks_per_second": round(ticks / seconds, 2),
        "queue_deliveries_per_second": round(subscribers * ticks / seconds, 2),
        "final_queue_max_size": max(q.qsize() for q in queues),
        "scope": "in-process queue publishing only; synthetic data"
    }
    for queue in queues:
        hub.unsubscribe("BTC-USD", queue)
    await hub.close()
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--subscribers", type=int, default=20)
    parser.add_argument("--ticks", type=int, default=10000)
    args = parser.parse_args()
    if not 1 <= args.subscribers <= 1000 or not 1 <= args.ticks <= 1000000:
        parser.error("subscribers 1..1000, ticks 1..1000000")
    print(json.dumps(asyncio.run(measure(args.subscribers, args.ticks)), indent=2))
