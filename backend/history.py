"""Bounded, ephemeral SQLite history of generated simulation observations."""
import os
import sqlite3
from pathlib import Path

DB_FILE = Path(os.environ.get("MARKETSTREAM_DB", "/tmp/marketstream.sqlite3"))

def connect():
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    db=sqlite3.connect(DB_FILE,timeout=3)
    db.execute("PRAGMA busy_timeout=3000")
    db.execute("CREATE TABLE IF NOT EXISTS ticks (id INTEGER PRIMARY KEY, symbol TEXT NOT NULL, price REAL NOT NULL, created_at TEXT NOT NULL)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_ticks_symbol_id ON ticks(symbol,id DESC)")
    return db

def record(symbol:str,price:float,when:str,keep:int=500):
    with connect() as db:
        db.execute("INSERT INTO ticks(symbol,price,created_at) VALUES (?,?,?)",(symbol,price,when))
        db.execute("DELETE FROM ticks WHERE symbol=? AND id NOT IN (SELECT id FROM ticks WHERE symbol=? ORDER BY id DESC LIMIT ?)",(symbol,symbol,keep))

def recent(symbol:str,limit:int=60):
    if not 1<=limit<=500: raise ValueError("Invalid limit")
    with connect() as db:
        return [{"id":r[0],"price":r[1],"timestamp":r[2]} for r in db.execute(
            "SELECT id,price,created_at FROM ticks WHERE symbol=? ORDER BY id DESC LIMIT ?",
            (symbol,limit)).fetchall()[::-1]]
