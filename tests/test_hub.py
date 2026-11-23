"""Shared-feed and bounded-queue regression tests."""
import asyncio
from backend.hub import MarketHub


def test_two_subscribers_receive_same_tick_and_one_record():
    async def scenario():
        writes = []
        def make_snapshot(symbol, price, sequence):
            return {"symbol": symbol, "sequence": sequence, "price": price}
        def record(symbol, tick):
            writes.append((symbol, tick["sequence"]))
        hub = MarketHub({"BTC-USD": 100}, make_snapshot, record, interval=60)
        a = hub.subscribe("BTC-USD")
        b = hub.subscribe("BTC-USD")
        try:
            first_a = await asyncio.wait_for(a.get(), timeout=2)
            first_b = await asyncio.wait_for(b.get(), timeout=2)
            assert first_a == first_b
            assert first_a["sequence"] == 0
            assert writes == [("BTC-USD", 0)]
            assert len(hub._streams) == 1
        finally:
            hub.unsubscribe("BTC-USD", a)
            hub.unsubscribe("BTC-USD", b)
            await hub.close()
    asyncio.run(scenario())


def test_slow_subscriber_only_keeps_latest_tick():
    async def scenario():
        hub = MarketHub({"ETH-USD": 20}, lambda s, p, i: {"sequence": i})
        queue = hub.subscribe("ETH-USD")
        try:
            # No need to sleep: force a backlog and verify bounded latest-only policy.
            hub.publish("ETH-USD", {"sequence": 10})
            hub.publish("ETH-USD", {"sequence": 11})
            hub.publish("ETH-USD", {"sequence": 12})
            assert queue.qsize() == 1
            assert queue.get_nowait()["sequence"] == 12
        finally:
            hub.unsubscribe("ETH-USD", queue)
            await hub.close()
    asyncio.run(scenario())


def test_invalid_symbol_and_cleanup():
    async def scenario():
        hub = MarketHub({"SOL-USD": 10}, lambda s, p, i: {"sequence": i})
        try:
            hub.subscribe("INVALID")
            assert False, "invalid symbol must fail"
        except ValueError:
            pass
        queue = hub.subscribe("SOL-USD")
        hub.unsubscribe("SOL-USD", queue)
        assert hub._streams == {}
        await hub.close()
    asyncio.run(scenario())


def test_capacity_caps_and_stats():
    async def scenario():
        from backend.hub import CapacityExceeded
        hub = MarketHub({"BTC-USD": 100, "ETH-USD": 10},
                        lambda s, p, i: {"sequence": i},
                        interval=60, max_clients=2, max_per_symbol=1)
        a = hub.subscribe("BTC-USD")
        try:
            assert hub.connection_stats()["connected_subscribers"] == 1
            try:
                hub.subscribe("BTC-USD")
                assert False, "symbol cap not enforced"
            except CapacityExceeded:
                pass
            b = hub.subscribe("ETH-USD")
            try:
                assert hub.connection_stats()["connected_subscribers"] == 2
                try:
                    hub.subscribe("ETH-USD")
                    assert False, "global cap not enforced"
                except CapacityExceeded:
                    pass
            finally:
                hub.unsubscribe("ETH-USD", b)
        finally:
            hub.unsubscribe("BTC-USD", a)
            await hub.close()
        assert hub.connection_stats()["connected_subscribers"] == 0
    asyncio.run(scenario())


def test_invalid_limits_rejected():
    try:
        MarketHub({"BTC-USD": 1}, lambda s, p, i: {}, max_clients=0)
        assert False, "invalid client cap must fail"
    except ValueError:
        pass


def test_operational_counters_record_queue_shedding():
    async def scenario():
        hub = MarketHub({"SOL-USD": 10}, lambda s, p, i: {"sequence": i}, interval=60)
        q = hub.subscribe("SOL-USD")
        try:
            await asyncio.wait_for(q.get(), timeout=2)
            before = hub.connection_stats()["queue_updates_dropped"]
            hub.publish("SOL-USD", {"sequence": 20})
            hub.publish("SOL-USD", {"sequence": 21})
            assert hub.connection_stats()["queue_updates_dropped"] == before + 1
            assert q.get_nowait()["sequence"] == 21
        finally:
            hub.unsubscribe("SOL-USD", q)
            await hub.close()
    asyncio.run(scenario())
