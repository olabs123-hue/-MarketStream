"""Basic benchmark correctness tests; intentionally no hardware-specific performance thresholds."""
import asyncio

from scripts.benchmark_fanout import measure, percentile


def test_percentile_and_bad_inputs():
    assert percentile([1, 2, 3, 4, 5], 0.5) == 3
    assert percentile([1, 2, 3, 4, 5], 0.95) == 5
    for args in ((0, 10, 0), (2, 0, 0), (2, 10, -1)):
        try:
            asyncio.run(measure(*args))
            assert False, "invalid benchmark input accepted"
        except ValueError:
            pass


def test_bounded_fanout_benchmark_reports_truthful_scope():
    result = asyncio.run(measure(subscribers=3, ticks=100, warmup=10))
    assert result["measured_publishes"] == 100
    assert result["attempted_queue_deliveries"] == 300
    assert result["queue_capacity"] == 1
    assert result["queued_updates_dropped"] >= 0
    assert result["publish_calls_per_second"] > 0
    times = result["publish_call_latency_us"]
    assert 0 <= times["p50"] <= times["p95"] <= times["p99"]
    assert "excludes WebSocket" in result["scope"]
