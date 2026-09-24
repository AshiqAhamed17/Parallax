# Parallax — Backtester Validation (real resolved Manifold market)

> Task 11.5: the backtester run end-to-end against one real, resolved Manifold market (fetched live from the public API). Read-only; no bets placed.

## Market

- ID: `ICnSIPIgZO`
- Question: GPT 6 Sol released today?
- Resolution: **YES** (outcome=1)
- Usable bets (price points): 48
- Total liquidity (pool size used): 1000.00

## Strategy (validation harness, not alpha)

Buy YES with 100 mana at 5 evenly-spaced points in the first half of the market's life; each fill uses the latency-aware execution price and settles against the real resolution.

## Result

# Aggregated P&L

> single real market

## Run

- Range: ICnSIPIgZO
- Trades: 5  (wins: 5)

## Results

| Metric | Value |
|---|---:|
| Hit rate | 100.0% |
| Total staked | 500.00 |
| Total cost | 500.00 |
| Total payout | 823.02 |
| **Realized P&L** | **+323.02** |
| Theoretical P&L (model-expected) | +0.00 |
| ROI (P&L / cost) | +64.60% |
| Realized edge (P&L / stake) | +0.6460 |
| Theoretical edge (expected / stake) | +0.0000 |

## By-hand sanity check

- Market resolved **YES**, so every YES trade should WIN.
- Wins: 5/5 → as expected ✅
- Realized P&L sign (+323.02) is correct ✅ for a YES resolution.

**Validation: PASS** — the full chain (fill → latency execution → settlement → aggregation) produces directionally-correct P&L on real data.
