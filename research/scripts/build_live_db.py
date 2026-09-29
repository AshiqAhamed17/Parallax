"""Build the live data DB from real Manifold data (Phase LD orchestrator).

Steps:
  1. Backfill curated open markets: real prices + features (Task LD.3).
  2. Train the calibration model on a real resolved-market corpus and store honest predictions for
     every open market (Task LD.5), reporting Brier score vs. the market baseline.

Later tasks (LD.6–LD.7) add the signal detectors. Produces a DB the API can serve directly.

Usage:
    uv run python scripts/build_live_db.py --db ../data/parallax-live.db
    uv run python scripts/build_live_db.py --db ../data/parallax-live.db --skip-model
"""

from __future__ import annotations

import argparse
import sqlite3

import httpx

from parallax_research.calibration.dataset import extract_training_dataset
from parallax_research.calibration.edge import evaluate_and_store
from parallax_research.calibration.model import BaselineModel
from parallax_research.calibration.scoring import brier_score
from parallax_research.ingest.backfill import backfill_registry
from parallax_research.ingest.training import backfill_training_corpus


def _fit_and_store(live_conn: sqlite3.Connection, *, client: httpx.Client, max_markets: int) -> None:
    print("Building resolved-market training corpus (this fetches bet history) …")
    corpus = sqlite3.connect(":memory:")
    try:
        rows = backfill_training_corpus(corpus, client=client, max_markets=max_markets)
        df = extract_training_dataset(corpus)
    finally:
        corpus.close()
    print(f"  training rows={len(df)} (from {rows} feature snapshots)")

    if len(df) < 30 or df["outcome"].nunique() < 2:
        print("  ! corpus too small / single-class — model falls back to base rate.")

    # Honest skill check: hold out 20%, compare the model's Brier to the market-price baseline.
    holdout = df.sample(frac=0.2, random_state=0) if len(df) >= 30 else df
    train = df.drop(holdout.index) if len(df) >= 30 else df
    model = BaselineModel().fit(train)
    if len(holdout):
        p_model = model.predict_proba(holdout)
        b_model = brier_score(holdout["outcome"], p_model)
        b_market = brier_score(holdout["outcome"], holdout["market_prob"])
        verdict = "model better" if b_model < b_market else "market better"
        print(f"  Brier  model={b_model:.4f}  market={b_market:.4f}  → {verdict} (lower is better)")

    # Refit on all data for production predictions; store every open market (min_ev < 0 keeps the
    # negative-edge ones too, so the dashboard shows the model's view on every market, not just bets).
    model_full = BaselineModel().fit(df)
    stored = evaluate_and_store(live_conn, model_full, fee=0.0, slippage=0.0, min_ev=-1.0)
    print(f"  stored predictions for {stored} open markets")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="../data/parallax-live.db", help="SQLite path to build")
    parser.add_argument("--skip-model", action="store_true", help="skip model training/prediction")
    parser.add_argument("--train-markets", type=int, default=120, help="resolved markets to train on")
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)
    client = httpx.Client(timeout=20.0)
    try:
        print(f"Backfilling curated Manifold markets into {args.db} …")
        counts = backfill_registry(conn, client=client)
        print(
            f"  markets={counts.markets}  bets={counts.bets}  "
            f"snapshots={counts.snapshots}  features={counts.features}"
        )
        if not args.skip_model:
            _fit_and_store(conn, client=client, max_markets=args.train_markets)
    finally:
        client.close()
        conn.close()
    print("Done.")


if __name__ == "__main__":
    main()
