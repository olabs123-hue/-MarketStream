# MarketStream — Targeted Security Review (2026-11-23)

## Scope and method

Static review of the repository's FastAPI WebSocket ingress, native C++17 ctypes boundary, Docker image, SQL history layer, synthetic data adapters and GitHub CI. This is **not** an independent penetration test, an authenticated production security audit, or a certification. All data remains fictional.

## Implemented controls verified in source

- WebSocket symbol allowlist and per-process connection caps (default 60 globally, 30 per symbol). Excess connections receive close code 1013.
- Bounded per-client queues (maxsize 1), stalled send timeout and producer cleanup; simulated stream payload has no trading or user-account functionality.
- Read-only REST data access, bounded replay and history limit validation; database query arguments are parameterized.
- Multi-stage Docker build and non-root application user; native library compilation with C++17 warning flags.
- Native stateful C++ validates levels, duplicate prices, crossed books and maximum levels, with a failure-safe candidate copy.
- Added WebSocket `Origin` screening for browser requests; non-browser clients with no Origin remain allowed because this public educational feed does not require authentication. An explicit server-side allowlist may be supplied using `MARKETSTREAM_ALLOWED_WS_ORIGINS` (comma-delimited exact origins). Local Vite origin at port 5173 is allowed only against localhost:8000 or 127.0.0.1:8000.
- Added checks rejecting values exceeding int64 bounds at the Python-to-C++ boundary.
- Focused regression cases added in `tests/test_security_boundaries.py`, and all backend/native CI tests must pass before deployment.

## Residual risks and limitations

1. **Public anonymous demo:** No identity, per-IP connection throttling, edge rate limiting, quota enforcement or abuse protection. Per-process caps do not protect multiple instances or unlimited reconnect attempts.
2. **Origin is not authentication:** WebSocket Origin checks primarily constrain browsers; custom clients may omit/forge Origin. Never enable transfers, real market-data license access or private information without proper authentication and additional controls.
3. **Ephemeral SQLite:** Render free instance storage can reset. No backup, production migrations or recovery point objectives exist. PostgreSQL adapter is tested but not deployed.
4. **Dependency maintenance:** Python requirements and npm dependencies use broad version ranges; GitHub workflows and Docker base image tags are not SHA/digest-pinned. Review dependency alerts, run audits and pin artifact versions as part of a real release process.
5. **Native safety:** C++ native processing is covered by correctness tests but has not undergone independent fuzzing, memory sanitizers, SAST, formal verification or third-party review.
6. **Availability:** No guarantee for a sleeping free-tier instance, network latency, sustained load, persistent subscriber state or cross-instance message ordering.
7. **Diagnostic accuracy:** Source-failover p95 is measured only for in-process synthetic Python selection; it is not real vendor recovery, full request latency or wire-to-wire performance.

## Recommended controls before any production use

Proper authentication and authorization, network egress limits, edge-level rate limiting, robust threat modeling, secret management, immutable dependency pinning, monitored error reporting, sanitizers/fuzz tests, dependency/SBOM scanning, distributed coordination, durable storage and a paid infrastructure capacity decision. Do not market this simulation as security-certified or production financial infrastructure.
