"""
zink/store/sqlite.py
--------------------
SQLite backing store for all stateful Zink layers.
One instance per ZinkEngine. Shared by L4, L6, L7, L8.

Opened at engine init. Closed when engine is garbage collected.
File persists across runs — dedup hashes, rate counters, audit log,
behavioral data all survive process restarts.

Default path: ./zink_store.db
Override:     Zink("./configs/", store_path="./data/zink.db")
              or ZINK_STORE_PATH env var
"""

import sqlite3
import threading
import os 
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS dedup_hashes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    hash        TEXT    NOT NULL,
    agent       TEXT    NOT NULL,
    resource    TEXT    NOT NULL,
    created_at  REAL    NOT NULL,
    ttl         REAL    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_dedup_hash ON dedup_hashes(hash);

CREATE TABLE IF NOT EXISTS rate_counters (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    agent        TEXT    NOT NULL,
    resource     TEXT    NOT NULL,
    window_start REAL    NOT NULL,
    count        INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_rate ON rate_counters(agent, resource, window_start);

CREATE TABLE IF NOT EXISTS audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT    NOT NULL,
    agent       TEXT    NOT NULL,
    resource    TEXT    NOT NULL,
    params      TEXT,
    approved    INTEGER NOT NULL,
    reason      TEXT,
    caller      TEXT,
    layer_trace TEXT,
    outcome     TEXT,
    entry_hash  TEXT    NOT NULL,
    prev_hash   TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS behavioral (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent TEXT NOT NULL,
    resource TEXT NOT NULL,
    outcome TEXT,
    params_hash TEXT,
    ts REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_behavioral ON behavioral (agent, resource,ts);
"""

class ZinkStore:
    """
    SQLite backing store. One instance per ZinkEngine.
    Thread-safe for single-process use via a lock on writes.
    WAL mode for concurrent reads.
    """
    def __init__(self, path: str | Path = None):
        if Path is None:
            path = os.getenv("ZINK_STORE_PATH", "zink_store.db")
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = self._connect()
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(
            str(self._path), check_same_thread=False # Let multiple threads use the connection
        )
        conn.execute("PRAGMA journal_mode= WAL") # Mutex locks
        conn.execute("PRAGMA foreign_keys = ON") # # Make sure related data actually exists in other tables
        conn.row_factory = sqlite3.Row # access data using keys like a dict
        return conn 

    def _init_schema(self):
        with self._lock:
            self._conn.executescript(SCHEMA)
            self._conn.commit()

    def execute(self, sql: str, params: tuple = ())->sqlite3.Cursor:
        """ Write operation, acquire lock"""
        with self._lock:
            cur = self._conn.execute(sql,params)
            self._conn.commit()
            return cur
    
    def query(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        """Read operation — no lock needed in WAL mode."""
        return self._conn.execute(sql, params).fetchall()

    def query_one(self, sql: str, params: tuple = ()) -> sqlite3.Row | None:
        return self._conn.execute(sql, params).fetchone()

    def close(self):
        self._conn.close()

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass



