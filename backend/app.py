"""Simulated streaming market data API. No real market data or investment functions."""
import math
import os
import asyncio
import random
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query
from backend.processor import top_of_book
from backend.history import record, recent, replay, backend_name
from backend.hub import MarketHub, CapacityExceeded
from backend.stateful import StatefulBook
from backend.sequencing import SequencedBook
from backend.analytics import AnalyticsBook
from backend.sources import SourceRouter
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

SYMBOLS = {'BTC-USD': 68420.0, 'ETH-USD': 3475.0, 'SOL-USD': 166.0}


def snapshot(symbol: str, price: float, sequence: int, *, seed: int = 73) -> dict:
    """Create deterministic educational order-book depth around a mock mid-price."""
    if symbol not in SYMBOLS:
        raise ValueError('unsupported symbol')
    if not math.isfinite(price) or price <= 0:
        raise ValueError('price must be positive and finite')
    rng = random.Random(f'{symbol}:{seed}:{sequence}')
    tick = 0.01 if price < 1000 else 0.1
    spread = max(tick * 2, round(price * .0001, 2))
    best_bid = price - spread / 2
    best_ask = price + spread / 2
    bids = [[round(best_bid - i * tick, 2), round(rng.uniform(.15, 6), 3)] for i in range(8)]
    asks = [[round(best_ask + i * tick, 2), round(rng.uniform(.15, 6), 3)] for i in range(8)]
    calculated = top_of_book(bids, asks)
    return {'symbol': symbol, 'sequence': sequence, 'timestamp': datetime.now(timezone.utc).isoformat(),
            'price': round(price, 2), 'change_pct': round((price / SYMBOLS[symbol] - 1) * 100, 3),
            'bids': bids, 'asks': asks, 'spread': calculated['spread'], 'processor': calculated['processor'], 'simulated': True}


def generate_path(symbol: str, count: int = 36, seed: int = 21) -> list[float]:
    if symbol not in SYMBOLS or not 1 <= count <= 500:
        raise ValueError('invalid symbol or count')
    rng = random.Random(f'{symbol}:{seed}')
    price = SYMBOLS[symbol]
    result = []
    for _ in range(count):
        price = max(.01, price * (1 + rng.gauss(0, 0.0008)))
        result.append(round(price, 2))
    return result


def persist_tick(symbol: str, tick: dict) -> None:
    record(symbol, tick['price'], tick['timestamp'])


hub = MarketHub(SYMBOLS, snapshot, persist_tick, max_clients=max(1, int(os.getenv('MARKETSTREAM_MAX_CLIENTS', '60'))), max_per_symbol=max(1, int(os.getenv('MARKETSTREAM_MAX_PER_SYMBOL', '30'))), processor_factory=lambda symbol: AnalyticsBook(SequencedBook(StatefulBook())), source_factory=lambda symbol: SourceRouter(symbol))


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        yield
    finally:
        await hub.close()

app = FastAPI(title='MarketStream', version='1.2.0', lifespan=lifespan)


@app.get('/health')
def health():
    return {'status': 'ok', 'mode': 'simulation'}


@app.get('/api/stream-status')
def stream_status():
    return {'mode': 'simulation', **hub.connection_stats()}


@app.get('/api/analytics/{symbol}')
def latest_analytics(symbol: str):
    if symbol not in SYMBOLS:
        raise HTTPException(404, 'Unknown symbol')
    latest = hub.latest_ticks.get(symbol)
    if latest is None:
        return {'symbol': symbol, 'simulated': True, 'status': 'no_active_feed',
                'analytics': None}
    return {'symbol': symbol, 'simulated': True, 'status': 'active',
            'sequence': latest['sequence'], 'timestamp': latest['timestamp'],
            'analytics': latest['analytics']}


@app.get('/api/markets')
def markets():
    return [{'symbol': s, 'reference_price': p} for s, p in SYMBOLS.items()]


@app.get('/api/history/{symbol}')
def history(symbol: str):
    from fastapi import HTTPException
    if symbol not in SYMBOLS:
        raise HTTPException(404, 'Unknown symbol')
    return {'symbol': symbol, 'simulated': True, 'prices': generate_path(symbol)}


@app.get('/api/recorded/{symbol}')
def recorded_history(symbol: str, limit: int = Query(default=60, ge=1, le=500)):
    if symbol not in SYMBOLS:
        raise HTTPException(404, 'Unknown symbol')
    return {'symbol': symbol, 'simulated': True, 'source': 'local-observations', 'ticks': recent(symbol, limit)}


@app.get('/api/replay/{symbol}')
def recorded_replay(symbol: str, after_id: int = Query(default=0, ge=0),
                    limit: int = Query(default=100, ge=1, le=500)):
    if symbol not in SYMBOLS:
        raise HTTPException(404, 'Unknown symbol')
    return {'symbol': symbol, 'simulated': True, 'source': backend_name(),
            **replay(symbol, after_id=after_id, limit=limit)}


@app.websocket('/ws/{symbol}')
async def market_stream(websocket: WebSocket, symbol: str):
    if symbol not in SYMBOLS:
        await websocket.close(code=1008, reason='Unknown symbol')
        return
    try:
        queue = hub.subscribe(symbol)
    except CapacityExceeded:
        await websocket.close(code=1013, reason='Stream capacity reached')
        return
    try:
        await websocket.accept()
        while True:
            tick = await queue.get()
            if tick is None:
                await websocket.close(code=1011, reason='Feed unavailable')
                break
            # A stalled client must not block a handler forever.
            await asyncio.wait_for(websocket.send_json(tick), timeout=5.0)
    except (WebSocketDisconnect, RuntimeError, OSError, asyncio.TimeoutError):
        return
    finally:
        hub.unsubscribe(symbol, queue)

DIST = Path(__file__).resolve().parents[1] / 'frontend' / 'dist'
if (DIST / 'index.html').exists():
    app.mount('/assets', StaticFiles(directory=DIST / 'assets'), name='assets')

    @app.get('/')
    def index():
        return FileResponse(DIST / 'index.html')
