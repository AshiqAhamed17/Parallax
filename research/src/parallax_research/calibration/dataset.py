"""Historical training-dataset extraction (Task 10.1).

Joins `feature_snapshots` with `markets` (and the market-implied probability from
`probability_snapshots`) for **resolved Manifold markets**, producing a labeled DataFrame: one row
per feature snapshot, labeled with the market's eventual `resolved_outcome` (0/1). This is the
supervised training set the calibrated model (Task 10.2) fits on.

Scope choices:
- **Resolved Manifold markets only** — calibration trains/validates against real Manifold outcomes
  (`implementation.md` §6). Rows for unresolved markets (`resolved_outcome IS NULL`) or non-Manifold
  markets are excluded.
- **One row per feature snapshot** — each snapshot at time `t` becomes a training example "given the
  features at `t`, did the market resolve YES?". Using the eventual outcome as the *label* is
  correct supervised learning; the strict guard against using features computed *after close* is a
  separate concern handled in Task 10.4 (anti-lookahead), not here.
- `market_prob` (the market-implied probability at that snapshot) is joined in as a feature — it's
  the natural baseline the model's own estimate is compared against (the "edge", Task 10.5).
"""

from __future__ import annotations

import sqlite3

import pandas as pd

#: Feature columns of the training set (model inputs).
FEATURE_COLUMNS = ["prob_velocity", "bet_arrival_rate", "realized_vol", "market_prob"]

#: The supervised label (0 = resolved NO, 1 = resolved YES).
LABEL_COLUMN = "outcome"

_QUERY = """
SELECT
    f.market_id                    AS market_id,
    f.ts_ns                        AS ts_ns,
    f.prob_velocity                AS prob_velocity,
    f.bet_arrival_rate             AS bet_arrival_rate,
    f.realized_vol                 AS realized_vol,
    p.probability                  AS market_prob,
    m.resolved_outcome             AS outcome
FROM feature_snapshots f
JOIN markets m ON m.market_id = f.market_id
LEFT JOIN probability_snapshots p
    ON p.market_id = f.market_id AND p.ts_ns = f.ts_ns
WHERE m.platform = 'manifold'
  AND m.resolved_outcome IS NOT NULL
ORDER BY f.market_id, f.ts_ns
"""


def extract_training_dataset(conn: sqlite3.Connection) -> pd.DataFrame:
    """Return the labeled training set for resolved Manifold markets.

    Columns: ``market_id, ts_ns, prob_velocity, bet_arrival_rate, realized_vol, market_prob,
    outcome``. Empty (with those columns) if there are no resolved markets yet.
    """
    df = pd.read_sql_query(_QUERY, conn)
    # Guarantee a stable dtype/shape even when empty, so downstream code can rely on the columns.
    if df.empty:
        return pd.DataFrame(
            columns=["market_id", "ts_ns", *FEATURE_COLUMNS[:-1], "market_prob", LABEL_COLUMN]
        )
    df[LABEL_COLUMN] = df[LABEL_COLUMN].astype(int)
    return df
