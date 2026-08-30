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

## Status

Early stage — see the project plan and design docs for the full architecture and roadmap.

## License

Private repository. All rights reserved (for now).
