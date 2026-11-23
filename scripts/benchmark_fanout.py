"""In-process market fanout microbenchmark with measured publish-call latency.

Not a network, WebSocket, database, or C++ processing benchmark. Figures are
hardware-dependent; this tool does not assert production throughput.
"""
import argparse
import asyncio
import json
import os
import platform
import statistics
import time

from backend.hub import MarketHub


def percentile(sorted_values: list[float], fraction: float) -> float:
    """Nearest-rank percentile for nonempty sorted measurements."""
    if not sorted_values:
        raise ValueError("No measurements")
    return sorted_values[max(0, min(len(sorted_values) - 1, int((len(sorted_values) - 1) * fraction + 0.5)))]


async def measure(subscribers: int = 20, ticks: int = 10000, warmup: int = 1000) -> dict:
    if not 1 <= subscribers <= 1000 or not 1 <= ticks <= 1000000 or not 0 <= warmup <= 100000:
        raise ValueError("subscribers 1..1000, ticks 1..1000000, warmup 0..100000")
    hub = MarketHub({"BTC-USD": 100.0}, lambda s, p, i: {"sequence": i},
                    interval=3600, max_clients=subscribers,
                    max_per_symbol=subscribers)
    queues = [hub.subscribe("BTC-USD") for _ in range(subscribers)]
    try:
        await asyncio.sleep(0)
        for queue in queues:
            if not queue.empty():
                queue.get_nowait()
        for n in range(warmup):
            hub.publish("BTC-USD", {"sequence": -n})
        samples_ns = []
        started = time.perf_counter_ns()
        for n in range(ticks):
            beginning = time.perf_counter_ns()
            hub.publish("BTC-USD", {"sequence": n})
            samples_ns.append(time.perf_counter_ns() - beginning)
        elapsed = max((time.perf_counter_ns() - started) / 1e9, 1e-12)
        values = sorted(v / 1000 for v in samples_ns)
        assert all(q.qsize() <= 1 for q in queues)
        assert all(q.get_nowait()["sequence"] == ticks - 1 for q in queues)
        result = {
            "scenario": "single-process Python asyncio Queue(maxsize=1) publication",
            "subscribers": subscribers,
            "warmup_publishes": warmup,
            "measured_publishes": ticks,
            "attempted_queue_deliveries": ticks * subscribers,
            "elapsed_seconds": round(elapsed, 6),
            "publish_calls_per_second": round(ticks / elapsed, 2),
            "attempted_queue_deliveries_per_second": round(ticks * subscribers / elapsed, 2),
            "publish_call_latency_us": {
                "p50": round(percentile(values, .50), 3),
                "p95": round(percentile(values, .95), 3),
                "p99": round(percentile(values, .99), 3),
            },
            "queue_capacity": 1,
            "queued_updates_dropped": hub.queue_updates_dropped,
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "scope": "in-process enqueue only; excludes WebSocket and network transmission, database writes, and C++"
        }
        return result
    finally:
        for queue in queues:
            hub.unsubscribe("BTC-USD", queue)
        await hub.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--subscribers", type=int, default=20)
    parser.add_argument("--ticks", type=int, default=10000)
    parser.add_argument("--warmup", type=int, default=1000)
    parser.add_argument("--output", default="", help="Optional path for JSON results")
    args = parser.parse_args()
    result = asyncio.run(measure(args.subscribers, args.ticks, args.warmup))
    rendered = json.dumps(result, indent=2)
    print(rendered)
    if args.output:
        from pathlib import Path
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
