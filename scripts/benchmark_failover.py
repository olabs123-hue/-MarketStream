"""Controlled source-failure injection and repeatable local recovery evidence.

This exercises only in-process simulated source selection and normalization.
No socket, remote source, retry backoff, network outage, or C++ processing.
"""
import argparse
import json
import platform
from backend.sources import SimulatedVendor, SourceRouter


def percentile(values, fraction):
    if not values:
        return None
    arr = sorted(values)
    return round(arr[max(0, int((len(arr)-1)*fraction+.5))], 3)


def run_benchmark(events=2000, fail_every=10):
    if not 2 <= events <= 100000 or not 2 <= fail_every <= events:
        raise ValueError("events must be 2..100000; fail_every between 2 and events")
    a, b = SimulatedVendor("SIM-A"), SimulatedVendor("SIM-B")
    router = SourceRouter("BTC-USD", a, b)
    switches = 0
    for i in range(events):
        a.fail = b.fail = False
        if (i + 1) % fail_every == 0:
            router.sources[router.active].fail = True
        quote = router.next(68000 + i / 1000)
        if quote.failover:
            assert quote.attempts == 2
            assert quote.failover_us is not None
            switches += 1
        else:
            assert quote.attempts == 1
    expected = events // fail_every
    assert switches == expected == router.failovers
    assert router.failed_attempts == expected
    return {
        "scenario": "in-process deterministic dual simulated vendor fault injection",
        "events": events,
        "fault_interval": fail_every,
        "successful_failovers": switches,
        "failed_primary_attempts": router.failed_attempts,
        "source_processing_us": {
            "p50": percentile(router.processing_samples_us, .5),
            "p95": percentile(router.processing_samples_us, .95),
            "p99": percentile(router.processing_samples_us, .99),
        },
        "failover_duration_us": {
            "p50": percentile(router.failover_samples_us, .5),
            "p95": percentile(router.failover_samples_us, .95),
            "p99": percentile(router.failover_samples_us, .99),
        },
        "sample_window": 256,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "scope": "in-process synchronous source selection + local schema normalization only; excludes network, C++, database and WebSocket",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--events", type=int, default=2000)
    parser.add_argument("--fail-every", type=int, default=10)
    parser.add_argument("--output", type=str, default="")
    args = parser.parse_args()
    result = run_benchmark(args.events, args.fail_every)
    output = json.dumps(result, indent=2)
    print(output)
    if args.output:
        from pathlib import Path
        Path(args.output).write_text(output+"\n", encoding="utf-8")
