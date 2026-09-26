# Parallax — Logical-Constraint Arbitrage Backtest (real resolved group)

> Task 12.4: the Phase 12 detector + two-leg convergence strategy, run end-to-end through the Phase 11 backtester against a REAL, resolved correlated Manifold group (fetched live). The curated production groups (12.2) are still open, so — as in Task 11.5 — a resolved group of identical structure is used to produce real settled numbers. Read-only; no bets placed.

## Group (all by creator `HillaryClinton`, identical resolution criteria)

| Leg | Market id | Points | Resolution |
|---|---|---:|---|
| BTC >= $100k EOY2025 | `mCCutllFld7vv4n2nL3a` | 115 | YES |
| BTC >= $120k EOY2025 | `OU5Nh6QzLI` | 401 | YES |
| BTC >= $130k EOY2025 | `6E6uhtIEzC` | 773 | NO |

Constraints (higher threshold implies lower): `P(>=130k) <= P(>=120k) <= P(>=100k)` — consistent with the resolutions (2025 ATH cleared $120k, not $130k).

## Strategy

Edge-triggered: when a constraint is breached net of costs (`cost = 2 * 0.02` per two-leg trade), enter once — buy NO 100 mana on the over-priced (higher) leg and YES 100 on the under-priced (lower) leg, each filled at the Phase 11 latency-aware execution price, then settled against the real resolution.

## Actionable breaches entered (per constraint)

| Constraint | Entries |
|---|---:|
| gt_130k <= gt_120k | 4 |
| gt_120k <= gt_100k | 1 |

## Result

# Aggregated P&L (both legs of every arb)

> real resolved BTC end-of-2025 threshold group

## Run

- Range: full market history
- Trades: 10  (wins: 9)

## Results

| Metric | Value |
|---|---:|
| Hit rate | 90.0% |
| Total staked | 1000.00 |
| Total cost | 1000.00 |
| Total payout | 1733.32 |
| **Realized P&L** | **+733.32** |
| Theoretical P&L (model-expected) | +6.54 |
| ROI (P&L / cost) | +73.33% |
| Realized edge (P&L / stake) | +0.7333 |
| Theoretical edge (expected / stake) | +0.0065 |

## Reading it honestly

**Realized edge +0.7333 per unit vs theoretical +0.0065** — and that ~100x gap is the point, not a bug. The *theoretical* edge is the small convergence profit the violation size implies (net of costs); it is tiny because the breaches themselves were small. The *realized* P&L is large because the two equal-stake legs also carry directional exposure, and in this particular group that exposure paid off hard: the shorted high-threshold legs (NO on >=$130k, NO on >=$120k) mostly resolved the favorable way ($130k resolved NO). So this is high-variance outcome luck from a SINGLE resolved group (5 breaches), not evidence of a riskless edge or a performance claim. A logical-constraint breach is a *provable* internal-consistency violation, but capturing it at CPMM prices with an unhedged two-leg position is not riskless — which is exactly the detector's honest framing: a mispricing signal, never asserted free money, and never traded (§2.1). What this backtest validates is that the Phase 12 detector feeds the Phase 11 machinery end-to-end and settles against real resolutions correctly.
