"""Regression tests for bounded source diagnostics and deterministic fault recovery."""
import asyncio
from fastapi.testclient import TestClient
from backend.app import app
from backend.sources import SimulatedVendor, SourceRouter, FeedUnavailable
from backend.hub import MarketHub
from scripts.benchmark_failover import run_benchmark


def test_measured_failover_and_bounded_samples():
    primary, backup = SimulatedVendor("SIM-A"), SimulatedVendor("SIM-B")
    router = SourceRouter("ETH-USD", primary, backup)
    first = router.next(3500)
    assert first.processing_us >= 0
    assert first.failover_us is None
    assert first.attempts == 1
    primary.fail = True
    switched = router.next(3501)
    assert switched.source == "SIM-B"
    assert switched.failover and switched.attempts == 2
    assert switched.processing_us >= 0 and switched.failover_us >= 0
    assert len(router.failover_samples_us) == 1
    assert router.failed_attempts == 1
    for _ in range(300):
        router.next(3502)
    assert len(router.processing_samples_us) == 256


def test_fault_injection_workload_checks_successful_recovery():
    result = run_benchmark(events=120, fail_every=12)
    assert result["successful_failovers"] == 10
    assert result["failed_primary_attempts"] == 10
    assert result["source_processing_us"]["p95"] >= 0
    assert result["failover_duration_us"]["p95"] >= 0
    assert "excludes network" in result["scope"]


def test_source_outage_fails_closed():
    a, b = SimulatedVendor("SIM-A"), SimulatedVendor("SIM-B")
    a.fail = b.fail = True
    router = SourceRouter("BTC-USD", a, b)
    try:
        router.next(68000)
        assert False, "outage must stop the feed"
    except FeedUnavailable:
        assert router.failed_attempts == 2
    assert not router.processing_samples_us


def test_hub_diagnostics_includes_aggregated_successful_switch():
    async def scenario():
        a, b = SimulatedVendor("SIM-A"), SimulatedVendor("SIM-B")
        a.fail = True
        router = SourceRouter("BTC-USD", a, b)
        hub = MarketHub(
            {"BTC-USD": 100.0},
            lambda symbol, price, seq: {"symbol":symbol, "price":price, "sequence":seq},
            interval=60, source_factory=lambda symbol: router
        )
        queue = hub.subscribe("BTC-USD")
        try:
            tick = await asyncio.wait_for(queue.get(), timeout=2)
            assert tick["source"] == "SIM-B"
            assert tick["source_failover"] is True
            assert tick["source_attempts"] == 2
            assert tick["source_failover_us"] is not None
            status = hub.connection_stats()
            assert status["source_failovers"] == 1
            assert status["source_failed_attempts"] == 1
            assert status["source_latency_sample_count"] == 1
            assert status["source_latency_p95_us"] >= 0
            assert status["source_failover_p95_us"] >= 0
        finally:
            hub.unsubscribe("BTC-USD", queue)
            await hub.close()
    asyncio.run(scenario())


def test_live_rest_stream_status_has_optional_latency_metrics():
    with TestClient(app) as client:
        with client.websocket_connect("/ws/SOL-USD") as ws:
            tick = ws.receive_json()
            assert tick["source_processing_us"] >= 0
            assert tick["source_attempts"] >= 1
            response = client.get("/api/stream-status")
            assert response.status_code == 200
            body = response.json()
            assert body["source_latency_sample_count"] >= 1
            assert body["source_latency_p95_us"] >= 0
