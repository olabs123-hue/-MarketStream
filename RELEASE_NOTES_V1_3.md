# MarketStream — Technical release notes (v1.3)

Date: 2026-11-23
Commit SHA: See the successful GitHub Actions run on the repository main branch.

## Verified capabilities

- Python/FastAPI simulated price and full-depth WebSocket terminal with React/TypeScript frontend.
- Stateful C++17 order book with synthetic snapshot/delta reconstruction, monotonically increasing sequence validation, and full-snapshot recovery tests.
- Two local fictional quote-vendor schemas (SIM-A/SIM-B), normalized, with source-specific deduplication and backup failover logic.
- Microstructure analytics: mid-price, spread in basis points, top-level microprice and visible depth imbalance.
- Bounded subscriber queues, capacity limits, per-process status diagnostics and a lightweight read-only quote analytics endpoint.
- Controlled source-failure injection: 2,000 synthetic events with 200 successful forced source switches; p95 local selection/recovery duration 2.964 microseconds on the documented CI runner. **Only synchronous in-process Python time was measured.**
- SQLite observation retention; optional PostgreSQL adapter exercised in temporary GitHub Actions integration tests (no hosted PostgreSQL provisioned).
- Multi-stage Docker builds and Render free-tier deployment.

## Verification

- Automated GitHub workflows: backend, native C++ integration, standalone C++, frontend, Docker, PostgreSQL storage contract, bounded in-process fanout benchmark, controlled fault-injection benchmark.
- Fault-injection evidence: https://github.com/olabs123-hue/MarketStream/actions/runs/45196355759
- Historical Python fanout evidence: https://github.com/olabs123-hue/MarketStream/actions/runs/45190849808
- Latest workflow results: https://github.com/olabs123-hue/MarketStream/actions
- Live app: https://marketstream-sim-olabs123.onrender.com

## Boundaries

All market data and vendor schemas are simulated; no real exchange or external vendor interfaces exist. The project does not execute trades, produce investment decisions, replicate external proprietary market-data infrastructure, or benchmark network propagation latency. Hosting remains free-tier, with ephemeral local SQLite. This is a demonstrable engineering portfolio project rather than a production market-data service.

## Portfolio description

**MarketStream — C++17 & Full-Stack Market Data Simulation:** Built a simulated real-time market-data terminal using C++17 stateful order-book validation, Python/FastAPI WebSockets, TypeScript/React and Docker; added sequence-aware delta reconstruction, quote normalization, microstructure analytics, bounded fanout and deterministic dual-source failover, verified by integration tests and scope-limited benchmark artifacts.

Release v1.3.0 is published and the repository is named MarketStream.
