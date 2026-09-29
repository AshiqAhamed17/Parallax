"""Training-corpus backfill for the calibration model (Task LD.5).

The model trains on *resolved* Manifold markets (known YES/NO outcome). For each, we fetch its bet
history and write several `feature_snapshots` at real bet timestamps (before close, so the Phase-10.4
anti-lookahead guard keeps them) with a `probability_snapshots` row at the same `ts_ns` for the
market-price feature. `resolved_outcome` supplies the supervised label.

The corpus is deliberately built in a *separate* connection (the orchestrator uses an in-memory DB)
so these resolved training markets never leak into the live dashboard's market list — only the
fitted model's predictions flow back to the live DB.
"""

from __future__ import annotations

import sqlite3

import httpx

from parallax_research.adapters.manifold import get_bets, iter_resolved_markets
from parallax_research.ingest.backfill import _MS_TO_NS, _close_iso
from parallax_research.ingest.features import compute_features
from parallax_research.storage import ensure_schema

# Broad terms chosen to pull a diverse, two-class resolved corpus (politics, crypto, tech, sports,
# culture) rather than one lopsided topic.
DEFAULT_TERMS = (
    "trump",
    "election",
    "bitcoin",
    "ethereum",
    "ai",
    "nba",
    "soccer",
    "price",
    "2025",
    "court",
)


def _sample_indices(n: int, k: int) -> list[int]:
    """Up to `k` indices spread across ``[2, n-1]`` (need ≥2 bets for a feature window)."""
    if n <= 2:
        return [n - 1]
    start = 2
    span = n - 1 - start
    if k >= span + 1:
        return list(range(start, n))
    return [start + round(i * span / (k - 1)) for i in range(k)]


def backfill_training_corpus(
    conn: sqlite3.Connection,
    *,
    client: httpx.Client | None = None,
    terms: tuple[str, ...] = DEFAULT_TERMS,
    max_markets: int = 120,
    snapshots_per_market: int = 6,
    min_bets: int = 8,
) -> int:
    """Populate `conn` with resolved markets + labeled feature snapshots. Returns rows written.

    A market with fewer than `min_bets` bets is skipped (too little history for stable features).
    """
    ensure_schema(conn)
    owned = client is None
    client = client or httpx.Client(timeout=20.0)
    written = 0
    processed = 0
    try:
        for market in iter_resolved_markets(list(terms), per_term=40, client=client):
            if processed >= max_markets:
                break
            try:
                bets = get_bets(market.market_id, limit=1000, client=client)
            except httpx.HTTPError:
                continue
            if len(bets) < min_bets:
                continue

            conn.execute(
                "INSERT OR REPLACE INTO markets "
                "(market_id, platform, question_text, close_time, resolved_outcome, category) "
                "VALUES (?, 'manifold', ?, ?, ?, ?)",
                (market.market_id, market.question_text, _close_iso(market.close_time_ms),
                 market.resolved_outcome, market.category),
            )
            for i in _sample_indices(len(bets), snapshots_per_market):
                window = bets[: i + 1]
                feats = compute_features(window)
                ts_ns = bets[i].created_time_ms * _MS_TO_NS
                conn.execute(
                    "INSERT INTO probability_snapshots (market_id, ts_ns, probability, volume_24h) "
                    "VALUES (?, ?, ?, ?)",
                    (market.market_id, ts_ns, bets[i].prob_after, None),
                )
                conn.execute(
                    "INSERT INTO feature_snapshots "
                    "(market_id, ts_ns, prob_velocity, bet_arrival_rate, realized_vol) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (market.market_id, ts_ns, feats.prob_velocity, feats.bet_arrival_rate,
                     feats.realized_vol),
                )
                written += 1
            processed += 1
        conn.commit()
    finally:
        if owned:
            client.close()
    return written


__all__ = ["DEFAULT_TERMS", "backfill_training_corpus"]
