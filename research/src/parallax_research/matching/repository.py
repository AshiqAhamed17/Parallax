"""Data-access for the `market_matches` table (Task 8.1).

A *match* links a Manifold market to its equivalent on the second source (Polymarket), with a
`status` lifecycle: `pending` (a candidate, possibly machine-generated) → `confirmed` (a human
approved it) or `rejected`. Only `confirmed` matches may drive a public divergence signal
(constraint §2.2), which `list_confirmed` enforces at the read boundary.

The production table is created by the Rust collector's migration (Task 4.1, `implementation.md`
§5). `ensure_market_matches` mirrors that DDL with `IF NOT EXISTS` so the Python side is
self-sufficient in tests and a no-op in production. `platform` is always inserted explicitly
(`'polymarket'`) — the column's DB-level default is legacy from the pre-pivot Metaculus design and
never relied upon (see §15).
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

# The production schema (Rust migration) declares `manifold_market_id ... REFERENCES markets`. The
# FK is omitted here: SQLite doesn't enforce foreign keys unless `PRAGMA foreign_keys=ON`, and this
# mirror only needs to stand up the table for Python-only tests. Prod uses the Rust table as-is.
MARKET_MATCHES_DDL = """
CREATE TABLE IF NOT EXISTS market_matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    manifold_market_id TEXT NOT NULL,
    platform TEXT NOT NULL DEFAULT 'polymarket',
    external_market_id TEXT NOT NULL,
    confidence REAL,
    status TEXT NOT NULL DEFAULT 'pending'
)
"""

STATUS_PENDING = "pending"
STATUS_CONFIRMED = "confirmed"
STATUS_REJECTED = "rejected"


@dataclass(frozen=True)
class MarketMatch:
    """One row of `market_matches`."""

    id: int
    manifold_market_id: str
    platform: str
    external_market_id: str
    confidence: float | None
    status: str


_COLUMNS = "id, manifold_market_id, platform, external_market_id, confidence, status"


def _row_to_match(row: tuple) -> MarketMatch:
    return MarketMatch(
        id=row[0],
        manifold_market_id=row[1],
        platform=row[2],
        external_market_id=row[3],
        confidence=row[4],
        status=row[5],
    )


def ensure_market_matches(conn: sqlite3.Connection) -> None:
    """Create the `market_matches` table if absent (idempotent). No-op when the Rust migration
    already created it."""
    conn.execute(MARKET_MATCHES_DDL)
    conn.commit()


def insert_candidate(
    conn: sqlite3.Connection,
    *,
    manifold_market_id: str,
    external_market_id: str,
    platform: str = "polymarket",
    confidence: float | None = None,
) -> int:
    """Insert a new `pending` candidate match and return its row id.

    Candidates start `pending` by design — nothing is confirmed without an explicit `confirm`
    (constraint §2.2). `confidence` is an informational similarity score (or None for a hand-curated
    match).
    """
    cur = conn.execute(
        "INSERT INTO market_matches "
        "(manifold_market_id, platform, external_market_id, confidence, status) "
        "VALUES (?, ?, ?, ?, ?)",
        (manifold_market_id, platform, external_market_id, confidence, STATUS_PENDING),
    )
    conn.commit()
    return int(cur.lastrowid)


def _set_status(conn: sqlite3.Connection, match_id: int, status: str) -> bool:
    cur = conn.execute(
        "UPDATE market_matches SET status = ? WHERE id = ?",
        (status, match_id),
    )
    conn.commit()
    return cur.rowcount > 0


def confirm(conn: sqlite3.Connection, match_id: int) -> bool:
    """Mark a match `confirmed`. Returns False if no such match exists."""
    return _set_status(conn, match_id, STATUS_CONFIRMED)


def reject(conn: sqlite3.Connection, match_id: int) -> bool:
    """Mark a match `rejected`. Returns False if no such match exists."""
    return _set_status(conn, match_id, STATUS_REJECTED)


def get(conn: sqlite3.Connection, match_id: int) -> MarketMatch | None:
    """Fetch a single match by id, or None."""
    row = conn.execute(
        f"SELECT {_COLUMNS} FROM market_matches WHERE id = ?", (match_id,)
    ).fetchone()
    return _row_to_match(row) if row is not None else None


def list_by_status(conn: sqlite3.Connection, status: str) -> list[MarketMatch]:
    """All matches with the given status, oldest first."""
    rows = conn.execute(
        f"SELECT {_COLUMNS} FROM market_matches WHERE status = ? ORDER BY id", (status,)
    ).fetchall()
    return [_row_to_match(r) for r in rows]


def list_confirmed(conn: sqlite3.Connection) -> list[MarketMatch]:
    """All `confirmed` matches — the only matches allowed to drive a divergence signal (§2.2)."""
    return list_by_status(conn, STATUS_CONFIRMED)
