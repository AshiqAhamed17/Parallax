# Curated correlated market groups (Task 12.2)

`correlated_market_groups.yaml` is the production input to the logical-constraint arbitrage
detector (Task 12.3). It holds real, currently-open Manifold binary markets grouped so that each
ordering constraint is **logically provable**, not merely statistically correlated. That distinction
is the whole point of the centerpiece: the detector can treat a breach as a genuine mispricing (net
of transaction costs) rather than a modelling opinion, because the constraint holds by construction
of the questions themselves.

## Curation method

1. Search live Manifold (`/v0/search-markets`) for families of related binary markets.
2. Keep only groups where an ordering constraint is **provable from the question text alone** — one
   of three structural relationships (below).
3. Verify each candidate live via `/v0/market/<id>`: binary, unresolved (open), and — critically for
   temporal/subset groups — authored so the resolution criterion is shared across the group.
4. Record the constraint and its plain-language justification in the YAML `note` fields.

The three relationship types deliberately span different constraint shapes so the detector is
exercised on more than one pattern:

- **Magnitude nesting** — one quantity sliced at rising thresholds (Group 1).
- **Temporal nesting** — one event asked at rising deadlines (Group 2).
- **Event-subset / conditional** — one event that can only occur inside another (Group 3).

## Live snapshot (verification)

Captured `2026-09-26T06:27Z` from the public Manifold API; every market was `isResolved=false`
(open). Probabilities are shown only to demonstrate the constraints currently hold — the config does
not depend on them.

### Group 1 — `btc-eoy-2026-thresholds` (magnitude nesting)

Underlying: Bitcoin's price at the end of 2026. Constraint: P must fall as the threshold rises.

| Market | id | P (2026-09-26) | close |
|---|---|---|---|
| BTC > $66,666 at EOY 2026 | `26QhQQ6hsQ` | 0.884 | 2026-12-31 |
| BTC > $77,777 at EOY 2026 | `Ophn0RNnRL` | 0.776 | 2026-12-31 |
| BTC > $88,888 at EOY 2026 | `2q2qZNLRlE` | 0.439 | 2026-12-31 |

Reasoning: if BTC finishes 2026 above $88,888 it is trivially above $77,777, which is above $66,666.
So `P(>88,888) <= P(>77,777) <= P(>66,666)`. Live: `0.439 <= 0.776 <= 0.884` — consistent. All three
resolve on the same date (end of 2026) to the same underlying, so nothing but the threshold differs.
(Finer rungs exist on Manifold — e.g. a `> $150,000` end-of-2026 close market, `0Nh2qNNuNR` ~0.015 —
and could be appended as a lower-probability top rung.)

### Group 2 — `agi-arrival-2027-deadlines` (temporal nesting)

Event: "we get AGI", identical resolution text, **all four markets authored by the same creator
(`RemNi`)** so the AGI definition is fixed across the ladder — the prerequisite that makes the
temporal nesting provable rather than a cross-definition apples-to-oranges comparison.

| Market | id | P (2026-09-26) |
|---|---|---|
| AGI before Jul 1 2027 | `ysAmD1AL7KSPxg0FAcQ3` | 0.072 |
| AGI before Aug 1 2027 | `1T9iu2LX27d6wbCrO181` | 0.104 |
| AGI before Sep 1 2027 | `nmBdKE7ODKOGMYaD7QVF` | 0.113 |
| AGI before Oct 1 2027 | `bMiXjmTvOXVkekHs8hqO` | 0.165 |

Reasoning: AGI arriving before an earlier date implies it arrived before any later date, so
`P(by Jul) <= P(by Aug) <= P(by Sep) <= P(by Oct)`. Live: `0.072 <= 0.104 <= 0.113 <= 0.165` —
consistent. (The market's `closeTime` sits after its deadline — e.g. the "before Jul 1 2027" market
closes 2027-10-01 — because the creator set a late close; the resolution criterion is the deadline
in the question, not the close time. Adjacent finer rungs the creator also made, "before Aug 15" and
"before Sep 15", currently show sub-1% inversions against their neighbours — exactly the marginal,
cost-dominated breaches the Task 12.3 detector must weigh rather than blindly flag; they are left out
here to keep the curated ladder clean.)

### Group 3 — `vance-2028-nomination-presidency` (event-subset / conditional)

Both markets authored by the same creator (`LarsDoucet`).

| Market | id | P (2026-09-26) | close |
|---|---|---|---|
| JD Vance nominated for President (2028) | `ulm6rrplx5` | 0.480 | 2028-07-02 |
| JD Vance wins the 2028 US Presidential Election | `wpdomi6nif` | 0.209 | 2028-11-08 |

Reasoning: a candidate cannot win the presidency without first being nominated, so "wins" is a strict
subset of "nominated": `P(wins presidency) <= P(nominated)`. Live: `0.209 <= 0.480` — consistent.
This is the real-world instance of the primary/general example in the constraint schema docstring.

## Notes / caveats

- These constraints hold on Manifold's **play-money** markets; Parallax never trades (constraint
  §2.1). A live breach is an informational signal about internal price consistency, weighed against
  estimated transaction costs by the detector, not an executable arb.
- Market ids are stable but a market can resolve or be N/A'd over time; re-verify against the live
  API before relying on a group. `load_constraint_groups()` validates structure, not liveness.
