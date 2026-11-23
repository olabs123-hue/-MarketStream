"""Simulated streaming market data API. No real market data or investment functions."""
import asyncio
import math
import random
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
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
    return {'symbol': symbol, 'sequence': sequence, 'timestamp': datetime.now(timezone.utc).isoformat(),
            'price': round(price, 2), 'change_pct': round((price / SYMBOLS[symbol] - 1) * 100, 3),
            'bids': bids, 'asks': asks, 'spread': round(asks[0][0] - bids[0][0], 2), 'simulated': True}


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


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield

app = FastAPI(title='MarketStream', version='0.1.0', lifespan=lifespan)


@app.get('/health')
def health():
    return {'status': 'ok', 'mode': 'simulation'}


@app.get('/api/markets')
def markets():
    return [{'symbol': s, 'reference_price': p} for s, p in SYMBOLS.items()]


@app.get('/api/history/{symbol}')
def history(symbol: str):
    from fastapi import HTTPException
    if symbol not in SYMBOLS:
        raise HTTPException(404, 'Unknown symbol')
    return {'symbol': symbol, 'simulated': True, 'prices': generate_path(symbol)}


@app.websocket('/ws/{symbol}')
async def market_stream(websocket: WebSocket, symbol: str):
    if symbol not in SYMBOLS:
        await websocket.close(code=1008, reason='Unknown symbol')
        return
    await websocket.accept()
    sequence = 0
    rng = random.Random(110)
    price = SYMBOLS[symbol]
    try:
        while True:
            price = max(.01, price * (1 + rng.gauss(0, .0005)))
            await websocket.send_json(snapshot(symbol, price, sequence))
            sequence += 1
            await asyncio.sleep(1)
    except (WebSocketDisconnect, RuntimeError, OSError):
        return

DIST = Path(__file__).resolve().parents[1] / 'frontend' / 'dist'
if (DIST / 'index.html').exists():
    app.mount('/assets', StaticFiles(directory=DIST / 'assets'), name='assets')

    @app.get('/')
    def index():
        return FileResponse(DIST / 'index.html')
