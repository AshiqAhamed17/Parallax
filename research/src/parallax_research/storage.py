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

# `markets` and `feature_snapshots` are WRITTEN by the Rust collector; the research layer READS them
# (e.g. calibration training-set extraction, Phase 10). FK to `markets` omitted in these mirrors
# (SQLite doesn't enforce FKs by default; tests don't need it).
MARKETS_DDL = """
CREATE TABLE IF NOT EXISTS markets (
    market_id TEXT PRIMARY KEY,
    platform TEXT NOT NULL,
    question_text TEXT NOT NULL,
    close_time TEXT NOT NULL,
    resolved_outcome INTEGER
)
"""

FEATURE_SNAPSHOTS_DDL = """
CREATE TABLE IF NOT EXISTS feature_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    market_id TEXT NOT NULL,
    ts_ns INTEGER NOT NULL,
    prob_velocity REAL,
    bet_arrival_rate REAL,
    realized_vol REAL
)
"""

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

MODEL_PREDICTIONS_DDL = """
CREATE TABLE IF NOT EXISTS model_predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    market_id TEXT NOT NULL,
    ts_ns INTEGER NOT NULL,
    p_model REAL NOT NULL,
    p_market REAL NOT NULL,
    edge REAL NOT NULL,
    ev REAL NOT NULL
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


def ensure_markets(conn: sqlite3.Connection) -> None:
    conn.execute(MARKETS_DDL)
    conn.commit()


def ensure_feature_snapshots(conn: sqlite3.Connection) -> None:
    conn.execute(FEATURE_SNAPSHOTS_DDL)
    conn.commit()


def ensure_probability_snapshots(conn: sqlite3.Connection) -> None:
    conn.execute(PROBABILITY_SNAPSHOTS_DDL)
    conn.commit()


def ensure_model_predictions(conn: sqlite3.Connection) -> None:
    conn.execute(MODEL_PREDICTIONS_DDL)
    conn.commit()


def ensure_arbitrage_signals(conn: sqlite3.Connection) -> None:
    conn.execute(ARBITRAGE_SIGNALS_DDL)
    conn.commit()


def ensure_schema(conn: sqlite3.Connection) -> None:
    """Ensure every table the research layer touches exists (idempotent)."""
    ensure_markets(conn)
    ensure_feature_snapshots(conn)
    ensure_probability_snapshots(conn)
    ensure_cross_source_snapshots(conn)
    ensure_market_matches(conn)
    ensure_model_predictions(conn)
    ensure_arbitrage_signals(conn)


__all__ = [
    "ARBITRAGE_SIGNALS_DDL",
    "FEATURE_SNAPSHOTS_DDL",
    "MARKETS_DDL",
    "MODEL_PREDICTIONS_DDL",
    "PROBABILITY_SNAPSHOTS_DDL",
    "ensure_arbitrage_signals",
    "ensure_cross_source_snapshots",
    "ensure_feature_snapshots",
    "ensure_market_matches",
    "ensure_markets",
    "ensure_model_predictions",
    "ensure_probability_snapshots",
    "ensure_schema",
]
