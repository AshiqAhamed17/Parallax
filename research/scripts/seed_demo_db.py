#!/usr/bin/env python3
"""Seed a realistic DEMO database for the dashboard (Task 14 enabling work).

The live Rust collector isn't running during dashboard development, so this writes a deterministic,
realistic SQLite DB the API can serve — markets across many categories (F1, Football, NBA, Tennis,
Crypto, Politics, Tech, Macro, Culture) with multi-point probability history, a latest model
prediction per open market (edge/EV via the real `calibration.edge` math), and both kinds of
arbitrage signal. Several markets form nested "ladders" (constraint groups) for the correlated-
groups showcase. Illustrative DEMO data, clearly labeled; replaced by the live collector in Phase 15.

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

BASE_NS = 1_759_000_000_000_000_000
HOUR_NS = 3_600_000_000_000

# (id, question, close_time, resolved_outcome|None, category, target_prob)
# target_prob anchors the latest probability; ladder markets use ordered targets so the correlated
# groups are meaningful (with one deliberate F1 violation for the detector to catch).
_MARKETS: list[tuple[str, str, str, int | None, str, float]] = [
    # --- Crypto (incl. a nested BTC end-of-2026 threshold ladder) ---
    ("btc-100k", "Will Bitcoin close above $100k at the end of 2026?", "2026-12-31T23:59:00Z", None, "Crypto", 0.62),
    ("btc-120k", "Will Bitcoin close above $120k at the end of 2026?", "2026-12-31T23:59:00Z", None, "Crypto", 0.34),
    ("btc-150k", "Will Bitcoin close above $150k at the end of 2026?", "2026-12-31T23:59:00Z", None, "Crypto", 0.11),
    ("eth-flip", "Will Ethereum flip Bitcoin by market cap in 2026?", "2026-12-31T23:59:00Z", None, "Crypto", 0.09),
    ("eth-5k", "Will Ethereum close above $5,000 at the end of 2026?", "2026-12-31T23:59:00Z", None, "Crypto", 0.41),
    ("sol-etf", "Will a spot Solana ETF launch in the US in 2026?", "2026-12-31T23:59:00Z", None, "Crypto", 0.58),
    ("btc-90k-res", "Did Bitcoin reach $90k before Sep 2026?", "2026-09-01T00:00:00Z", 1, "Crypto", 0.97),
    # --- F1 (Verstappen ladder: title => a race win => points; deliberate small violation) ---
    ("f1-max-title", "Will Verstappen win the 2026 F1 Drivers' Championship?", "2026-12-13T00:00:00Z", None, "F1", 0.62),
    ("f1-max-race", "Will Verstappen win at least one race in 2026?", "2026-12-13T00:00:00Z", None, "F1", 0.55),
    ("f1-max-points", "Will Verstappen score championship points in 2026?", "2026-12-13T00:00:00Z", None, "F1", 0.98),
    ("f1-norris-title", "Will Lando Norris win the 2026 F1 title?", "2026-12-13T00:00:00Z", None, "F1", 0.24),
    ("f1-ferrari-win", "Will Ferrari win a Grand Prix in 2026?", "2026-12-13T00:00:00Z", None, "F1", 0.71),
    ("f1-hamilton-podium", "Will Hamilton finish on a podium in 2026?", "2026-12-13T00:00:00Z", None, "F1", 0.63),
    # --- Football / soccer (Man City ladder: win PL => top 4 => top 10) ---
    ("pl-city-win", "Will Man City win the 2026-27 Premier League?", "2027-05-24T00:00:00Z", None, "Football", 0.30),
    ("pl-city-top4", "Will Man City finish top four in 2026-27?", "2027-05-24T00:00:00Z", None, "Football", 0.74),
    ("pl-city-top10", "Will Man City finish top ten in 2026-27?", "2027-05-24T00:00:00Z", None, "Football", 0.985),
    ("pl-arsenal-win", "Will Arsenal win the 2026-27 Premier League?", "2027-05-24T00:00:00Z", None, "Football", 0.28),
    ("ucl-madrid", "Will Real Madrid win the 2026-27 Champions League?", "2027-05-30T00:00:00Z", None, "Football", 0.19),
    ("wc-england", "Will England win the 2026 World Cup?", "2026-07-19T00:00:00Z", None, "Football", 0.12),
    ("wc-messi-goal", "Will Messi score at the 2026 World Cup?", "2026-07-19T00:00:00Z", None, "Football", 0.44),
    # --- NBA ---
    ("nba-celtics", "Will the Celtics win the 2027 NBA title?", "2027-06-20T00:00:00Z", None, "NBA", 0.17),
    ("nba-rookie-20", "Will a rookie average 20+ PPG in 2026-27?", "2027-04-15T00:00:00Z", None, "NBA", 0.38),
    ("nba-jokic-mvp", "Will Jokić win the 2026-27 NBA MVP?", "2027-05-01T00:00:00Z", None, "NBA", 0.29),
    # --- Tennis ---
    ("tennis-alcaraz-wimb", "Will Alcaraz win Wimbledon 2027?", "2027-07-11T00:00:00Z", None, "Tennis", 0.33),
    ("tennis-sinner-no1", "Will Sinner finish 2026 as ATP world #1?", "2026-12-31T23:59:00Z", None, "Tennis", 0.52),
    # --- Politics ---
    ("pol-incumbent-primary", "Will the incumbent party hold the 2028 nomination?", "2028-06-01T00:00:00Z", None, "Politics", 0.33),
    ("pol-newsom-nominee", "Will Newsom be the 2028 Democratic nominee?", "2028-08-01T00:00:00Z", None, "Politics", 0.16),
    ("pol-shutdown-26", "Will there be a US government shutdown in 2026?", "2026-12-31T23:59:00Z", None, "Politics", 0.47),
    ("pol-ballot-res", "Did the 2026 state ballot measure pass?", "2026-08-01T00:00:00Z", 0, "Politics", 0.10),
    # --- Tech ---
    ("tech-gpt6", "Will GPT-6 be released before July 2027?", "2027-07-01T00:00:00Z", None, "Tech", 0.20),
    ("tech-apple-fold", "Will Apple ship a foldable device in 2026?", "2026-12-31T23:59:00Z", None, "Tech", 0.58),
    ("tech-agi-2027", "Will an AI lab publicly declare AGI before 2027?", "2027-01-01T00:00:00Z", None, "Tech", 0.07),
    ("tech-starship", "Will SpaceX reach orbit with Starship v3 in 2026?", "2026-12-31T23:59:00Z", None, "Tech", 0.62),
    ("tech-manifold-1m", "Will Manifold surpass 1M users in 2026?", "2026-12-31T23:59:00Z", None, "Tech", 0.79),
    # --- Macro ---
    ("macro-fed-cut", "Will the Fed cut rates at its next meeting?", "2026-11-01T00:00:00Z", None, "Macro", 0.41),
    ("macro-inflation-3", "Will US CPI inflation be below 3% at the end of 2026?", "2026-12-31T23:59:00Z", None, "Macro", 0.55),
    ("macro-recession-27", "Will the US enter a recession during 2027?", "2027-12-31T23:59:00Z", None, "Macro", 0.31),
    ("macro-sp-7000", "Will the S&P 500 close above 7,000 in 2026?", "2026-12-31T23:59:00Z", None, "Macro", 0.68),
    # --- Culture ---
    ("cult-gta6", "Will GTA 6 release in 2026?", "2026-12-31T23:59:00Z", None, "Culture", 0.46),
    ("cult-film-2b", "Will a 2026 film gross over $2B worldwide?", "2026-12-31T23:59:00Z", None, "Culture", 0.37),
    ("cult-swift-tour", "Will Taylor Swift announce a 2027 tour?", "2026-12-31T23:59:00Z", None, "Culture", 0.61),
    ("cult-temps-record", "Will global temperatures set a new record in 2026?", "2026-12-31T23:59:00Z", None, "Culture", 0.67),
]

# Nested ladders (constraint P(lhs) <= P(rhs)) for the correlated-groups showcase.
_GROUPS = [
    {
        "id": "btc-eoy-2026-thresholds",
        "category": "Crypto",
        "description": "Bitcoin's end-of-2026 close, sliced at rising thresholds. A higher threshold implies every lower one, so probability must fall as the threshold rises.",
        "markets": [("gt_100k", "btc-100k"), ("gt_120k", "btc-120k"), ("gt_150k", "btc-150k")],
        "constraints": [("gt_120k", "gt_100k"), ("gt_150k", "gt_120k")],
    },
    {
        "id": "verstappen-2026",
        "category": "F1",
        "description": "Winning the title implies winning a race implies scoring points. A live inconsistency here is a provable mispricing.",
        "markets": [("title", "f1-max-title"), ("race", "f1-max-race"), ("points", "f1-max-points")],
        "constraints": [("title", "race"), ("race", "points")],
    },
    {
        "id": "man-city-2026-27",
        "category": "Football",
        "description": "Winning the league implies a top-four finish implies a top-ten finish.",
        "markets": [("win", "pl-city-win"), ("top4", "pl-city-top4"), ("top10", "pl-city-top10")],
        "constraints": [("win", "top4"), ("top4", "top10")],
    },
]


def _walk_to(rng: random.Random, target: float, n: int) -> list[float]:
    """A mean-reverting bounded walk that ends exactly at `target` (so ladders stay meaningful)."""
    p = min(0.97, max(0.03, target + rng.gauss(0.0, 0.08)))
    out = []
    for _ in range(n - 1):
        p += 0.12 * (target - p) + rng.gauss(0.0, 0.03)
        p = min(0.98, max(0.02, p))
        out.append(round(p, 4))
    out.append(round(min(0.98, max(0.02, target)), 4))
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
    latest_prob: dict[str, float] = {}

    for i, (mid, question, close_time, resolved, category, target) in enumerate(_MARKETS):
        conn.execute(
            "INSERT INTO markets (market_id, platform, question_text, close_time, resolved_outcome, category) "
            "VALUES (?, 'manifold', ?, ?, ?, ?)",
            (mid, question, close_time, resolved, category),
        )
        counts["markets"] += 1

        n_points = rng.randint(32, 56)
        probs = _walk_to(rng, target, n_points)
        start_ns = BASE_NS + i * HOUR_NS
        for j, prob in enumerate(probs):
            conn.execute(
                "INSERT INTO probability_snapshots (market_id, ts_ns, probability, volume_24h) VALUES (?, ?, ?, ?)",
                (mid, start_ns + j * 6 * HOUR_NS, prob, round(rng.uniform(200, 12000), 2)),
            )
            counts["probability_snapshots"] += 1
        latest_prob[mid] = probs[-1]

        if resolved is None:
            p_market = probs[-1]
            p_model = min(0.98, max(0.02, p_market + rng.gauss(0.0, 0.07)))
            ee = compute_edge_ev(p_model, p_market, fee=0.01, slippage=0.01)
            conn.execute(
                "INSERT INTO model_predictions (market_id, ts_ns, p_model, p_market, edge, ev) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    mid,
                    start_ns + (n_points - 1) * 6 * HOUR_NS,
                    round(p_model, 4),
                    round(p_market, 4),
                    round(ee.edge, 4),
                    round(ee.ev, 4),
                ),
            )
            counts["model_predictions"] += 1

    # Logical-constraint signals from the ladders (flag genuine breaches of P(lhs) <= P(rhs)).
    for g in _GROUPS:
        m = dict(g["markets"])
        for k, (lhs, rhs) in enumerate(g["constraints"]):
            p_lhs, p_rhs = latest_prob[m[lhs]], latest_prob[m[rhs]]
            gross = round(p_lhs - p_rhs, 4)
            if gross <= 0:
                continue  # consistent — no signal
            cost = 0.04
            net = round(gross - cost, 4)
            details = {
                "group_id": g["id"],
                "constraint": f"{lhs} <= {rhs}",
                "p_lhs": p_lhs,
                "p_rhs": p_rhs,
                "gross_violation": gross,
                "cost": cost,
                "net_violation": net,
                "overpriced": lhs,
                "underpriced": rhs,
                "note": "logical-constraint violation, not tradeable arbitrage",
            }
            conn.execute(
                "INSERT INTO arbitrage_signals (type, market_refs, edge, detected_at, details_json) "
                "VALUES ('logical_constraint', ?, ?, ?, ?)",
                (json.dumps([m[lhs], m[rhs]]), net, f"2026-09-2{k}T10:00:00+00:00", json.dumps(details)),
            )
            counts["arbitrage_signals"] += 1

    # Cross-source divergence signals across a spread of markets.
    div_markets = ["btc-100k", "tech-gpt6", "macro-fed-cut", "pl-city-win", "nba-celtics", "cult-gta6"]
    for k, mid in enumerate(div_markets):
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
            (json.dumps([mid, f"poly-{mid}"]), edge, f"2026-09-2{k}T14:00:00+00:00", json.dumps(details)),
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
