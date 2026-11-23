"""Bounded simulation history: local SQLite by default; optional PostgreSQL.

Configure MARKETSTREAM_DATABASE_URL only when a database is explicitly provisioned.
Recorded ticks are synthetic, not exchange market data.
"""
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_FILE = Path(os.environ.get("MARKETSTREAM_DB", "/tmp/marketstream.sqlite3"))


def backend_name() -> str:
    return "postgresql" if os.getenv("MARKETSTREAM_DATABASE_URL") else "sqlite"


@contextmanager
def connect():
    url = os.getenv("MARKETSTREAM_DATABASE_URL")
    if url:
        # Imported lazily so the local SQLite-only mode remains standalone.
        import psycopg
        with psycopg.connect(url, connect_timeout=5) as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS ticks (
                    id BIGSERIAL PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    price DOUBLE PRECISION NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            db.execute("CREATE INDEX IF NOT EXISTS idx_ticks_symbol_id ON ticks(symbol, id DESC)")
            yield db
    else:
        DB_FILE.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(DB_FILE, timeout=3)
        try:
            db.execute("PRAGMA busy_timeout=3000")
            db.execute("""
                CREATE TABLE IF NOT EXISTS ticks (
                    id INTEGER PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    price REAL NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            db.execute("CREATE INDEX IF NOT EXISTS idx_ticks_symbol_id ON ticks(symbol, id DESC)")
            yield db
            db.commit()
        finally:
            db.close()


def record(symbol: str, price: float, when: str, keep: int = 500) -> None:
    if not 1 <= keep <= 100000:
        raise ValueError("Invalid retention")
    with connect() as db:
        if backend_name() == "postgresql":
            db.execute("INSERT INTO ticks(symbol,price,created_at) VALUES (%s,%s,%s)",
                       (symbol, price, when))
            db.execute("""DELETE FROM ticks WHERE symbol=%s AND id NOT IN
                       (SELECT id FROM ticks WHERE symbol=%s ORDER BY id DESC LIMIT %s)""",
                       (symbol, symbol, keep))
        else:
            db.execute("INSERT INTO ticks(symbol,price,created_at) VALUES (?,?,?)",
                       (symbol, price, when))
            db.execute("""DELETE FROM ticks WHERE symbol=? AND id NOT IN
                       (SELECT id FROM ticks WHERE symbol=? ORDER BY id DESC LIMIT ?)""",
                       (symbol, symbol, keep))


def _as_ticks(rows):
    return [{"id": row[0], "price": row[1], "timestamp": row[2]} for row in rows]


def recent(symbol: str, limit: int = 60) -> list[dict]:
    if not 1 <= limit <= 500:
        raise ValueError("Invalid limit")
    param = "%s" if backend_name() == "postgresql" else "?"
    with connect() as db:
        rows = db.execute(
            f"SELECT id,price,created_at FROM ticks WHERE symbol={param} "
            f"ORDER BY id DESC LIMIT {param}", (symbol, limit)).fetchall()
    return _as_ticks(reversed(rows))


def replay(symbol: str, after_id: int = 0, limit: int = 100) -> dict:
    """Stable, ID-ordered, bounded paging over retained synthetic observations."""
    if after_id < 0 or not 1 <= limit <= 500:
        raise ValueError("Invalid replay cursor or limit")
    p = "%s" if backend_name() == "postgresql" else "?"
    with connect() as db:
        rows = db.execute(
            f"SELECT id,price,created_at FROM ticks "
            f"WHERE symbol={p} AND id>{p} ORDER BY id ASC LIMIT {p}",
            (symbol, after_id, limit + 1)).fetchall()
    has_more = len(rows) > limit
    ticks = _as_ticks(rows[:limit])
    return {
        "ticks": ticks,
        "has_more": has_more,
        "next_after_id": ticks[-1]["id"] if ticks else after_id,
        "retention_limited": True,
    }
