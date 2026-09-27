#!/usr/bin/env python3
"""Seed a realistic DEMO database for the dashboard (Task 14 enabling work).

The live Rust collector isn't running during dashboard development, so this writes a deterministic,
realistic SQLite DB the API can serve — markets with multi-point probability history (so sparklines
and charts have shape), a latest model prediction per open market (edge/EV via the real
`calibration.edge` math), and both kinds of arbitrage signal. The data is illustrative DEMO data,
clearly labeled as such in the questions; it is replaced by the live collector feed in Phase 15.

Usage:
    uv run python scripts/seed_demo_db.py [--out ../data/parallax-demo.db]
"""

from __future__ import annotations

import argparse
import json
import random
import sqlite3
import sys
from pathlib import Path

from parallax_research.calibration.edge import compute_edge_ev
from parallax_research.storage import ensure_schema

# Fixed epoch-ns base so the deterministic core never reads wall-clock (keeps seeds reproducible).
BASE_NS = 1_759_000_000_000_000_000
HOUR_NS = 3_600_000_000_000

# (question, close_time ISO, resolved_outcome | None). "[demo]" marks illustrative data.
_MARKETS: list[tuple[str, str, int | None]] = [
    ("Will Bitcoin close above $100k at the end of 2026? [demo]", "2026-12-31T23:59:00Z", None),
    ("Will the Fed cut rates at its next meeting? [demo]", "2026-11-01T00:00:00Z", None),
    ("Will GPT-6 be released before July 2027? [demo]", "2027-07-01T00:00:00Z", None),
    ("Will SpaceX reach orbit with Starship v3 in 2026? [demo]", "2026-12-31T23:59:00Z", None),
    ("Will a US recession be declared before 2028? [demo]", "2027-12-31T23:59:00Z", None),
    ("Will Ethereum flip Bitcoin by market cap in 2026? [demo]", "2026-12-31T23:59:00Z", None),
    ("Will the incumbent win the 2028 primary? [demo]", "2028-06-01T00:00:00Z", None),
    ("Will global temps set a new record in 2026? [demo]", "2026-12-31T23:59:00Z", None),
    ("Will Apple ship a foldable device in 2026? [demo]", "2026-12-31T23:59:00Z", None),
    ("Will Manifold surpass 1M users in 2026? [demo]", "2026-12-31T23:59:00Z", None),
    ("Did BTC reach $90k before Sep 2026? (resolved) [demo]", "2026-09-01T00:00:00Z", 1),
    ("Did the 2026 ballot measure pass? (resolved) [demo]", "2026-08-01T00:00:00Z", 0),
]


def _walk(rng: random.Random, n: int) -> list[float]:
    """A smooth-ish bounded random walk in (0.02, 0.98) for a probability series."""
    p = rng.uniform(0.2, 0.8)
    out = []
    for _ in range(n):
        p = min(0.98, max(0.02, p + rng.gauss(0.0, 0.035)))
        out.append(round(p, 4))
    return out


def seed_demo_db(db_path: str | Path, *, seed: int = 7) -> dict[str, int]:
    """Write demo markets/snapshots/predictions/signals into `db_path`. Returns per-table row counts."""
    rng = random.Random(seed)
    path = Path(db_path)
    if path.exists():
        path.unlink()
    conn = sqlite3.connect(path)
    ensure_schema(conn)

    counts = {"markets": 0, "probability_snapshots": 0, "model_predictions": 0, "arbitrage_signals": 0}
    market_ids: list[str] = []
    latest_prob: dict[str, float] = {}

    for i, (question, close_time, resolved) in enumerate(_MARKETS):
        market_id = f"demo-{i:02d}"
        market_ids.append(market_id)
        conn.execute(
            "INSERT INTO markets (market_id, platform, question_text, close_time, resolved_outcome) "
            "VALUES (?, 'manifold', ?, ?, ?)",
            (market_id, question, close_time, resolved),
        )
        counts["markets"] += 1

        n_points = rng.randint(30, 55)
        probs = _walk(rng, n_points)
        start_ns = BASE_NS + i * HOUR_NS
        for j, prob in enumerate(probs):
            conn.execute(
                "INSERT INTO probability_snapshots (market_id, ts_ns, probability, volume_24h) "
                "VALUES (?, ?, ?, ?)",
                (market_id, start_ns + j * 6 * HOUR_NS, prob, round(rng.uniform(200, 9000), 2)),
            )
            counts["probability_snapshots"] += 1
        latest_prob[market_id] = probs[-1]

        # Latest model prediction for OPEN markets only (resolved ones aren't actionable).
        if resolved is None:
            p_market = probs[-1]
            p_model = min(0.98, max(0.02, p_market + rng.gauss(0.0, 0.08)))
            ee = compute_edge_ev(p_model, p_market, fee=0.01, slippage=0.01)
            conn.execute(
                "INSERT INTO model_predictions (market_id, ts_ns, p_model, p_market, edge, ev) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    market_id,
                    start_ns + (n_points - 1) * 6 * HOUR_NS,
                    round(p_model, 4),
                    round(p_market, 4),
                    round(ee.edge, 4),
                    round(ee.ev, 4),
                ),
            )
            counts["model_predictions"] += 1

    # Logical-constraint signals across nested demo markets.
    lc_pairs = [(0, 5), (2, 4), (1, 6)]  # (overpriced idx, underpriced idx)
    detected_base = "2026-09-2"
    for k, (hi, lo) in enumerate(lc_pairs):
        hi_id, lo_id = f"demo-{hi:02d}", f"demo-{lo:02d}"
        p_lhs = latest_prob[hi_id]
        p_rhs = max(0.02, p_lhs - rng.uniform(0.06, 0.18))
        gross = round(p_lhs - p_rhs, 4)
        cost = 0.04
        net = round(gross - cost, 4)
        details = {
            "group_id": f"demo-group-{k}",
            "constraint": "high <= low",
            "p_lhs": p_lhs,
            "p_rhs": round(p_rhs, 4),
            "gross_violation": gross,
            "cost": cost,
            "net_violation": net,
            "overpriced": "high",
            "underpriced": "low",
            "note": "logical-constraint violation, not tradeable arbitrage",
        }
        conn.execute(
            "INSERT INTO arbitrage_signals (type, market_refs, edge, detected_at, details_json) "
            "VALUES ('logical_constraint', ?, ?, ?, ?)",
            (json.dumps([hi_id, lo_id]), net, f"{detected_base}{k}T10:00:00+00:00", json.dumps(details)),
        )
        counts["arbitrage_signals"] += 1

    # Cross-source divergence signals.
    for k, idx in enumerate([3, 7, 9, 8]):
        mid = f"demo-{idx:02d}"
        p_manifold = latest_prob[mid]
        p_poly = min(0.98, max(0.02, p_manifold + rng.uniform(0.06, 0.22) * rng.choice([-1, 1])))
        edge = round(p_manifold - p_poly, 4)
        details = {
            "p_manifold": p_manifold,
            "p_polymarket": round(p_poly, 4),
            "divergence": abs(edge),
            "direction": "manifold_higher" if edge > 0 else "polymarket_higher",
            "note": "divergence signal, not tradeable arbitrage",
        }
        conn.execute(
            "INSERT INTO arbitrage_signals (type, market_refs, edge, detected_at, details_json) "
            "VALUES ('cross_source_divergence', ?, ?, ?, ?)",
            (json.dumps([mid, f"poly-{idx:02d}"]), edge, f"2026-09-2{k}T14:00:00+00:00", json.dumps(details)),
        )
        counts["arbitrage_signals"] += 1

    conn.commit()
    conn.close()
    return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed a demo dashboard database.")
    parser.add_argument("--out", default="../data/parallax-demo.db")
    args = parser.parse_args(argv)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    counts = seed_demo_db(args.out)
    print(f"seeded {args.out}: {counts}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
