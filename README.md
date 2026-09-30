# Parallax

> **Parallax** *(n.)* — the apparent difference in an object's position when observed from
> different viewpoints.

Same real-world event. Different prediction markets. Different implied prices. Parallax watches,
measures, and explains that difference.

## What this is

Parallax is a market microstructure and mispricing/arbitrage research system built around Kalshi,
with Polymarket, Manifold, and PredictIt as secondary cross-platform sources. It combines:

- A **low-latency Rust pipeline** ingesting Kalshi's live order book, with real, published
  latency benchmarks (not claims).
- A **calibrated probability model** that produces an independent estimate of event probability
  and compares it against the market's implied price.
- **Three arbitrage detectors**: same-market complement (`YES + NO ≠ $1`), cross-platform
  mispricing (the same event priced differently across platforms), and logical-constraint
  arbitrage across correlated markets.
- A **realistic backtester** that replays self-collected historical data with honest latency,
  fee, spread, and slippage modeling.
- A **public, read-only dashboard** — no accounts, no logins, no order execution. It observes and
  reports; it does not trade.

This is a research and engineering project, not a trading product. It never places real orders.

## Live data

The public dashboard serves **real, curated Manifold Markets data** — not a demo. A curated registry
of ~40 liquid binary markets across categories (politics, tech/AI, crypto, macro, sports, culture)
is backfilled from Manifold's public REST API: real prices and a per-market feature history
reconstructed from bet history. A logistic-regression calibration model is trained on real resolved
markets and its predictions stored per open market; the logical-constraint and Manifold↔Polymarket
cross-source detectors run over the live data.

Honest by construction: the model is measured against the market's own price and reported
transparently on the Performance page (the market is currently better-calibrated — no fabricated
edge), and cross-source signals only fire on hand-verified same-event pairs, which are rare.

Build / refresh the live DB and serve it:

```bash
./deploy/refresh_live_db.sh          # backfill + train + detectors -> data/parallax-live.db
./deploy/run_api.sh                  # serve the API against the live DB
```

Schedule `refresh_live_db.sh` on a cron (e.g. every 6h) to keep prices current. CI end-to-end tests
intentionally use a deterministic seeded DB (`research/scripts/seed_demo_db.py`) rather than the live
build, so tests don't depend on the network or live market movement.
