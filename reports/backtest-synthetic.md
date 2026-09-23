# Parallax — Backtest (synthetic demonstration)

> SYNTHETIC DEMONSTRATION — no real resolved Manifold markets collected yet (Task 4.2 gap). These numbers come from a deterministic synthetic scenario run through the real backtester (CPMM fill -> latency-aware execution -> settlement -> aggregation) to exercise it end-to-end. Task 11.5 produces the real-data validation report. (§2.3: measured, not fabricated; labeled synthetic.)

## Run

- Range: synthetic (12 markets)
- Trades: 12  (wins: 6)

## Results

| Metric | Value |
|---|---:|
| Hit rate | 50.0% |
| Total staked | 1200.00 |
| Total cost | 1200.00 |
| Total payout | 1244.34 |
| **Realized P&L** | **+44.34** |
| Theoretical P&L (model-expected) | +60.00 |
| ROI (P&L / cost) | +3.70% |
| Realized edge (P&L / stake) | +0.0370 |
| Theoretical edge (expected / stake) | +0.0500 |
