"""Backfill real Manifold data into the DB (Task LD.3).

For each curated market: write its `markets` row (real question / close time / category / resolution),
its bet history, a `probability_snapshots` series reconstructed from those bets (the sparkline the
dashboard draws), and a latest `feature_snapshots` row for the calibration model. The feature row's
`ts_ns` is aligned to the final snapshot's `ts_ns` so `evaluate_open_markets`' join finds a market
price.

Idempotent per market: existing snapshot/bet/feature rows for a market are cleared before reinsert,
so a refresh replaces rather than duplicates.
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx

from parallax_research.adapters.manifold import get_bets
from parallax_research.ingest.features import compute_features
from parallax_research.ingest.registry import RegistryEntry, resolve_registry
from parallax_research.storage import ensure_schema

_MAX_BETS = 1000
_MAX_SNAPSHOTS = 120
_MS_TO_NS = 1_000_000


@dataclass
class BackfillCounts:
    markets: int = 0
    bets: int = 0
    snapshots: int = 0
    features: int = 0

    def add(self, other: BackfillCounts) -> None:
        self.markets += other.markets
        self.bets += other.bets
        self.snapshots += other.snapshots
        self.features += other.features


def _close_iso(ms: int | None) -> str:
    # `markets.close_time` is TEXT NOT NULL; empty string when the market has no close date.
    if not ms:
        return ""
    return datetime.fromtimestamp(ms / 1000.0, UTC).isoformat()


def backfill_market(
    conn: sqlite3.Connection,
    entry: RegistryEntry,
    *,
    client: httpx.Client,
    now_ms: int,
) -> BackfillCounts:
    """Backfill a single curated market. Commits nothing — the caller controls the transaction."""
    market = entry.market
    mid = market.market_id

    conn.execute("DELETE FROM probability_snapshots WHERE market_id = ?", (mid,))
    conn.execute("DELETE FROM bets WHERE market_id = ?", (mid,))
    conn.execute("DELETE FROM feature_snapshots WHERE market_id = ?", (mid,))

    conn.execute(
        "INSERT OR REPLACE INTO markets "
        "(market_id, platform, question_text, close_time, resolved_outcome, category) "
        "VALUES (?, 'manifold', ?, ?, ?, ?)",
        (mid, market.question_text, _close_iso(market.close_time_ms),
         market.resolved_outcome, entry.category),
    )

    bets = get_bets(mid, limit=_MAX_BETS, client=client)
    conn.executemany(
        "INSERT INTO bets "
        "(market_id, ts_ns, prob_before, prob_after, amount, shares, is_limit_order) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            (mid, b.created_time_ms * _MS_TO_NS, b.prob_before, b.prob_after,
             b.amount, b.shares, int(b.is_limit_order))
            for b in bets
        ],
    )

    # Price series: one point per bet, plus a final point at "now" carrying the current price.
    series: list[tuple[int, float]] = [(b.created_time_ms, b.prob_after) for b in bets]
    series.append((now_ms, market.probability))
    series = series[-_MAX_SNAPSHOTS:]
    conn.executemany(
        "INSERT INTO probability_snapshots (market_id, ts_ns, probability, volume_24h) "
        "VALUES (?, ?, ?, ?)",
        [(mid, ms * _MS_TO_NS, prob, None) for ms, prob in series],
    )

    # One feature row at the latest ts, aligned to the final snapshot so the model join finds a price.
    feats = compute_features(bets)
    latest_ts_ns = series[-1][0] * _MS_TO_NS
    conn.execute(
        "INSERT INTO feature_snapshots "
        "(market_id, ts_ns, prob_velocity, bet_arrival_rate, realized_vol) VALUES (?, ?, ?, ?, ?)",
        (mid, latest_ts_ns, feats.prob_velocity, feats.bet_arrival_rate, feats.realized_vol),
    )

    return BackfillCounts(markets=1, bets=len(bets), snapshots=len(series), features=1)


def backfill_registry(
    conn: sqlite3.Connection,
    entries: list[RegistryEntry] | None = None,
    *,
    client: httpx.Client | None = None,
    now_ms: int | None = None,
) -> BackfillCounts:
    """Backfill every curated market. Resolves the registry if not supplied. Commits once at the end;
    a single market that errors is skipped rather than aborting the batch."""
    ensure_schema(conn)
    owned = client is None
    client = client or httpx.Client(timeout=20.0)
    now_ms = now_ms if now_ms is not None else int(time.time() * 1000)
    if entries is None:
        entries = resolve_registry(client=client)

    total = BackfillCounts()
    try:
        for entry in entries:
            try:
                total.add(backfill_market(conn, entry, client=client, now_ms=now_ms))
            except (httpx.HTTPError, sqlite3.Error):
                continue
        conn.commit()
    finally:
        if owned:
            client.close()
    return total


__all__ = ["BackfillCounts", "backfill_market", "backfill_registry"]
