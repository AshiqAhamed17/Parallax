"""Build the live data DB from real Manifold data (Phase LD orchestrator).

Currently runs the market/price/feature backfill (Task LD.3); later tasks (LD.5–LD.7) extend this to
train the model and run the signal detectors. Produces a DB the API can serve directly.

Usage:
    uv run python scripts/build_live_db.py --db ../data/parallax-live.db
"""

from __future__ import annotations

import argparse
import sqlite3

from parallax_research.ingest.backfill import backfill_registry


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="../data/parallax-live.db", help="SQLite path to build")
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)
    try:
        print(f"Backfilling curated Manifold markets into {args.db} …")
        counts = backfill_registry(conn)
        print(
            f"  markets={counts.markets}  bets={counts.bets}  "
            f"snapshots={counts.snapshots}  features={counts.features}"
        )
    finally:
        conn.close()
    print("Done.")


if __name__ == "__main__":
    main()
