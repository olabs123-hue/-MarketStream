# MarketStream — Real-Time Market Data Simulation Terminal

**React · TypeScript · WebSockets · FastAPI · C++17 · Docker**

MarketStream is a **full-stack educational simulation** of a financial market-data terminal. It streams generated prices and synthetic order-book snapshots, with a responsive chart and symbol selector. **It does not connect to real exchanges, execute trades, or give investment advice.**

## Live demo status

**[Open the live simulated terminal](https://marketstream-sim-olabs123.onrender.com)** — hosted on Render's free tier. Docker and React production builds passed during initial deployment on 23 November 2026. All prices, volume levels, and changes are simulated. No external market-data subscription or API key is required.

## Features

- Real-time WebSocket stream at one tick per second, with automatic client reconnect
- BTC-USD, ETH-USD and SOL-USD *simulated* feeds
- Live React/TypeScript price chart, top-of-book spread, and eight synthetic depth levels on each side
- Deterministic Python simulation helpers and independently tested REST endpoints
- Native C++17 order-book top-of-book validation in the Docker WebSocket feed, plus standalone C++ smoke tests
- Bounded SQLite history of generated simulation observations with a read-only endpoint
- Multi-stage Docker deployment and GitHub Actions test/build checks

## Architecture

```mermaid
flowchart LR
  S[Python seeded simulated prices] --> API[FastAPI WebSocket /ws/:symbol]
  API --> B[React browser dashboard]
  S --> BOOK[Synthetic L2 snapshot generation]
  BOOK --> API
  CPP[C++17 native top-of-book validation] --> API
  API --> DB[(SQLite bounded synthetic history)]
```

Docker builds a C++17 shared library that validates the synthetic book's bid, ask and spread from the Python WebSocket path. Local development may use a Python fallback. SQLite retains only generated samples and is ephemeral on free hosting. No Kafka, Redis, or PostgreSQL are included.

## Quick start

Python 3.11+, Node.js 20+, npm.

Terminal 1:

```bash
pip install -r backend/requirements.txt
uvicorn backend.app:app --reload --port 8000
```

Terminal 2:

```bash
cd frontend
npm install
npm run dev
```

**Local development WebSockets:** Vite serves the UI at `http://localhost:5173` while FastAPI listens at `localhost:8000`. Set `VITE_WS_URL=ws://localhost:8000` in `frontend/.env.local` before starting Vite. Do not commit `.env.local`.

## Docker (frontend and API same origin)

```bash
docker build -t marketstream .
docker run --rm -p 8000:8000 marketstream
```

Open http://localhost:8000. No authentication or exchange key is needed because the feed is entirely fictional.

## API

- `GET /health` — status and simulation mode
- `GET /api/markets` — available simulated symbols and reference values
- `GET /api/history/{symbol}` — reproducible example prices
- `GET /api/recorded/{symbol}?limit=60` — latest generated observations in bounded SQLite history
- `WS /ws/{symbol}` — synthetic price and order-book snapshots; rejects invalid symbols

## Tests

```bash
pip install pytest httpx
python -m pytest -q tests
g++ -std=c++17 -Wall -Wextra -pedantic engine/order_book.cpp -o /tmp/orderbook && /tmp/orderbook
cd frontend && npm install && npm run build
```

## Limitations

This is a **portfolio MVP**. It has no live financial data, durable hosted persistence, Kafka integration, production-grade multi-user fanout, backpressure handling, rate limiting, order matching, trade execution or service-level guarantees. The server creates an independent synthetic random walk per connected client. The Docker WebSocket path uses the C++ top-of-book validator; local development can fall back to Python. WebSocket messages are illustrative snapshots rather than market-grade level-2 incremental updates.

## Future roadmap

1. Extend the native C++ integration to stateful incremental order-book processing.
2. Add bounded fanout and client backpressure policy.
3. Replace ephemeral SQLite with PostgreSQL persistence and add deterministic replay.
4. Add benchmark evidence and failure-recovery tests.
5. Evaluate an authorized real-market-data adapter, clearly labeled and rate-limited.

## Native engine and bounded history

The deployed Docker image compiles `engine/book_native.cpp` as a shared library and sets `MARKETSTREAM_REQUIRE_NATIVE=1`. The Python stream calls it to validate best bid, best ask and spread. The local fallback is explicitly labeled in the `processor` message field. The standalone `engine/order_book.cpp` remains a separate educational example.

The `GET /api/recorded/{symbol}` endpoint returns up to 500 recent **generated** observations, stored in local SQLite (`MARKETSTREAM_DB`, default `/tmp/marketstream.sqlite3`). The store has a per-symbol retention limit of 500 and is **ephemeral on free hosting**. No exchange data, trading service, or order matching is provided.

### Validation

Backend tests: `python -m pytest -q tests`. Native mode: `g++ -std=c++17 -O2 -fPIC -shared -Wall -Wextra -Werror engine/book_native.cpp -o engine/libmarketbook.so && MARKETSTREAM_REQUIRE_NATIVE=1 python -m pytest -q tests`. Docker and frontend checks are in GitHub Actions; their status must be verified separately.
