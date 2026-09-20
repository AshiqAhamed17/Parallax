"""Schema helpers for the tables the Python research layer reads/writes.

Production schema is owned by the Rust collector migration (`implementation.md` §5); these mirror it
with `IF NOT EXISTS` so the Python side is self-sufficient in tests and a no-op in production. The
two tables that already had `ensure_*` helpers (`cross_source_snapshots`, `market_matches`) are
re-exported here so there's one place to "ensure everything," without duplicating their DDL.
"""

from __future__ import annotations

import sqlite3

from parallax_research.adapters.poller import ensure_cross_source_snapshots
from parallax_research.matching.repository import ensure_market_matches

# `probability_snapshots` is WRITTEN by the Rust collector; the research layer only READS it. FK to
# `markets` omitted in this mirror (SQLite doesn't enforce FKs by default; tests don't need it).
PROBABILITY_SNAPSHOTS_DDL = """
CREATE TABLE IF NOT EXISTS probability_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    market_id TEXT NOT NULL,
    ts_ns INTEGER NOT NULL,
    probability REAL NOT NULL,
    volume_24h REAL
)
"""

ARBITRAGE_SIGNALS_DDL = """
CREATE TABLE IF NOT EXISTS arbitrage_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL,
    market_refs TEXT NOT NULL,
    edge REAL NOT NULL,
    detected_at TEXT NOT NULL,
    details_json TEXT NOT NULL
)
"""


def ensure_probability_snapshots(conn: sqlite3.Connection) -> None:
    conn.execute(PROBABILITY_SNAPSHOTS_DDL)
    conn.commit()


def ensure_arbitrage_signals(conn: sqlite3.Connection) -> None:
    conn.execute(ARBITRAGE_SIGNALS_DDL)
    conn.commit()


def ensure_schema(conn: sqlite3.Connection) -> None:
    """Ensure every table the research layer touches exists (idempotent)."""
    ensure_probability_snapshots(conn)
    ensure_cross_source_snapshots(conn)
    ensure_market_matches(conn)
    ensure_arbitrage_signals(conn)


__all__ = [
    "ARBITRAGE_SIGNALS_DDL",
    "PROBABILITY_SNAPSHOTS_DDL",
    "ensure_arbitrage_signals",
    "ensure_cross_source_snapshots",
    "ensure_market_matches",
    "ensure_probability_snapshots",
    "ensure_schema",
]
