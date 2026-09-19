"""Polymarket polling scheduler (Task 7.3).

Periodically fetches live Polymarket markets (via the Phase 7.2 adapter) and appends a snapshot row
per market into `cross_source_snapshots`, building the time series the cross-source divergence
detector (Phase 9) reads.

Cadence guardrail (Polymarket ToS — see `implementation.md` §15): poll *gently*. Market-implied
probabilities on the large markets we compare move slowly relative to Manifold's live stream, and
the ToS has anti-scraping / rate-limit clauses, so the intended interval is hourly-ish, never
aggressive. This module only reads the public API and writes locally — it never trades.

Storage note (`implementation.md` §5): the production schema is created by the Rust collector's
migration (Task 4.1). `ensure_cross_source_snapshots` mirrors that DDL with `IF NOT EXISTS` so the
Python side is self-sufficient in tests (and a harmless no-op in production). Its
`community_prediction` column holds Polymarket's market-implied probability (the column name is
legacy from the Metaculus design — semantics documented in §15).
"""

from __future__ import annotations

import logging
import sqlite3
import time
from collections.abc import Sequence
from datetime import UTC, datetime

import httpx

from parallax_research.adapters.polymarket import fetch_markets
from parallax_research.schemas import NormalizedMarket

logger = logging.getLogger(__name__)

CROSS_SOURCE_SNAPSHOTS_DDL = """
CREATE TABLE IF NOT EXISTS cross_source_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    market_id TEXT NOT NULL,
    polled_at TEXT NOT NULL,
    community_prediction REAL NOT NULL
)
"""


def ensure_cross_source_snapshots(conn: sqlite3.Connection) -> None:
    """Create the `cross_source_snapshots` table if absent (idempotent). No-op when the Rust
    migration already created it."""
    conn.execute(CROSS_SOURCE_SNAPSHOTS_DDL)
    conn.commit()


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def poll_once(
    conn: sqlite3.Connection,
    markets: Sequence[NormalizedMarket],
    *,
    polled_at: str | None = None,
) -> int:
    """Append one snapshot row per market and commit. Returns the number of rows written.

    `polled_at` defaults to the current UTC time (ISO 8601); it's a parameter so tests can pin it.
    Each call appends — the table is a time series, so repeated polls accumulate rows rather than
    overwriting.
    """
    stamp = polled_at or _utc_now_iso()
    rows = [(m.market_id, stamp, m.probability) for m in markets]
    conn.executemany(
        "INSERT INTO cross_source_snapshots (market_id, polled_at, community_prediction) "
        "VALUES (?, ?, ?)",
        rows,
    )
    conn.commit()
    return len(rows)


def fetch_and_store(
    conn: sqlite3.Connection,
    client: httpx.Client,
    *,
    polled_at: str | None = None,
    limit: int = 100,
) -> int:
    """Fetch live Polymarket markets and store a snapshot of each. Returns rows written."""
    markets = fetch_markets(client, limit=limit)
    stamp = polled_at or _utc_now_iso()
    written = poll_once(conn, markets, polled_at=stamp)
    logger.info("polymarket poll: stored %d market snapshots at %s", written, stamp)
    return written


def run_poller(
    conn: sqlite3.Connection,
    client: httpx.Client,
    *,
    interval_secs: float = 3600.0,
    limit: int = 100,
    max_polls: int | None = None,
) -> int:
    """Run the poll loop, sleeping `interval_secs` between polls. Returns the number of polls run.

    `max_polls` bounds the loop (used by tests and by bounded/one-shot runs); leave it None for a
    continuous background poller. The default hourly interval respects the ToS cadence guardrail.
    """
    ensure_cross_source_snapshots(conn)
    polls = 0
    while max_polls is None or polls < max_polls:
        try:
            fetch_and_store(conn, client, limit=limit)
        except (httpx.HTTPError, sqlite3.Error):
            logger.exception("polymarket poll failed; will retry next interval")
        polls += 1
        if max_polls is not None and polls >= max_polls:
            break
        time.sleep(interval_secs)
    return polls
