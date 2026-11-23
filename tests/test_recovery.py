"""Failure recovery and reconnection coverage for simulated WebSocket fanout."""
import asyncio

from backend.hub import MarketHub


def test_reconnect_creates_new_producer_after_last_disconnect():
    async def scenario():
        hub = MarketHub(
            {"BTC-USD": 100.0},
            lambda symbol, price, seq: {"symbol": symbol, "sequence": seq},
            interval=60,
        )
        first = hub.subscribe("BTC-USD")
        try:
            assert (await asyncio.wait_for(first.get(), timeout=2))["sequence"] == 0
        finally:
            hub.unsubscribe("BTC-USD", first)
        assert hub.connection_stats()["connected_subscribers"] == 0
        second = hub.subscribe("BTC-USD")
        try:
            tick = await asyncio.wait_for(second.get(), timeout=2)
            assert tick["symbol"] == "BTC-USD"
            assert tick["sequence"] == 0
        finally:
            hub.unsubscribe("BTC-USD", second)
            await hub.close()
    asyncio.run(scenario())


def test_producer_failure_notifies_clients_then_allows_reconnect():
    async def scenario():
        attempts = 0
        def sometimes_fails(symbol, price, seq):
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise RuntimeError("simulated producer fault")
            return {"sequence": seq, "symbol": symbol}

        hub = MarketHub({"SOL-USD": 10}, sometimes_fails, interval=60)
        first = hub.subscribe("SOL-USD")
        try:
            # On failure the hub sends None rather than leaving subscribers blocked.
            sentinel = await asyncio.wait_for(first.get(), timeout=2)
            assert sentinel is None
            assert hub.connection_stats()["active_symbols"] == 0
        finally:
            hub.unsubscribe("SOL-USD", first)

        second = hub.subscribe("SOL-USD")
        try:
            assert (await asyncio.wait_for(second.get(), timeout=2))["sequence"] == 0
        finally:
            hub.unsubscribe("SOL-USD", second)
            await hub.close()
    asyncio.run(scenario())


def test_shutdown_cancels_all_producers():
    async def scenario():
        hub = MarketHub(
            {"BTC-USD": 100, "ETH-USD": 10},
            lambda symbol, price, seq: {"sequence": seq},
            interval=60
        )
        first = hub.subscribe("BTC-USD")
        second = hub.subscribe("ETH-USD")
        await asyncio.wait_for(first.get(), timeout=2)
        await asyncio.wait_for(second.get(), timeout=2)
        await hub.close()
        assert hub.connection_stats()["connected_subscribers"] == 0
        assert hub.connection_stats()["active_symbols"] == 0
    asyncio.run(scenario())
