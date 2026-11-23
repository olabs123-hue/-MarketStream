"""One simulated producer per symbol per app process, with bounded subscriber queues.

This is an in-process demo fanout, not a cross-instance message broker.
"""
import asyncio
import random
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class _Stream:
    subscribers: set[asyncio.Queue] = field(default_factory=set)
    task: asyncio.Task | None = None


class CapacityExceeded(Exception):
    """Refuse subscribers before allocating resources when capacity is reached."""


class MarketHub:
    def __init__(self, prices: dict[str, float], make_snapshot: Callable, on_tick: Callable | None = None, interval: float = 1.0, max_clients: int = 60, max_per_symbol: int = 30):
        if max_clients < 1 or max_per_symbol < 1:
            raise ValueError("Subscriber limits must be positive")
        self.max_clients = max_clients
        self.max_per_symbol = max_per_symbol
        self.prices = prices
        self.make_snapshot = make_snapshot
        self.on_tick = on_tick
        self.interval = interval
        self._streams: dict[str, _Stream] = {}

    def subscribe(self, symbol: str) -> asyncio.Queue:
        if symbol not in self.prices:
            raise ValueError("Unknown symbol")
        stream = self._streams.get(symbol)
        total = sum(len(existing.subscribers) for existing in self._streams.values())
        if total >= self.max_clients or (stream is not None and len(stream.subscribers) >= self.max_per_symbol):
            raise CapacityExceeded("WebSocket subscriber capacity reached")
        if stream is None:
            stream = _Stream()
            self._streams[symbol] = stream
        queue: asyncio.Queue = asyncio.Queue(maxsize=1)
        stream.subscribers.add(queue)
        if stream.task is None:
            stream.task = asyncio.create_task(self._produce(symbol, stream))
        return queue

    def unsubscribe(self, symbol: str, queue: asyncio.Queue) -> None:
        stream = self._streams.get(symbol)
        if stream is None:
            return
        stream.subscribers.discard(queue)
        if not stream.subscribers:
            self._streams.pop(symbol, None)
            if stream.task:
                stream.task.cancel()

    async def close(self) -> None:
        tasks = [s.task for s in self._streams.values() if s.task]
        self._streams.clear()
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def connection_stats(self) -> dict:
        return {
            "connected_subscribers": sum(len(s.subscribers) for s in self._streams.values()),
            "active_symbols": len(self._streams),
            "max_subscribers": self.max_clients,
            "max_per_symbol": self.max_per_symbol,
        }

    def publish(self, symbol: str, tick: dict) -> None:
        stream = self._streams.get(symbol)
        if stream is None:
            return
        for queue in tuple(stream.subscribers):
            if queue.full():
                queue.get_nowait()  # keep the newest snapshot for a slow consumer
            queue.put_nowait(tick)

    async def _produce(self, symbol: str, stream: _Stream) -> None:
        rng = random.Random(f"marketstream:{symbol}")
        price = self.prices[symbol]
        sequence = 0
        try:
            while stream.subscribers and self._streams.get(symbol) is stream:
                price = max(0.01, price * (1 + rng.gauss(0, 0.0005)))
                tick = self.make_snapshot(symbol, price, sequence)
                if self.on_tick is not None:
                    # Persist only one observation per generated tick, not one per client.
                    await asyncio.to_thread(self.on_tick, symbol, tick)
                self.publish(symbol, tick)
                sequence += 1
                await asyncio.sleep(self.interval)
        except asyncio.CancelledError:
            raise
        finally:
            # A failed producer must not leave hanging subscribers indefinitely.
            if self._streams.get(symbol) is stream:
                self._streams.pop(symbol, None)
                for queue in tuple(stream.subscribers):
                    if queue.full():
                        queue.get_nowait()
                    queue.put_nowait(None)
