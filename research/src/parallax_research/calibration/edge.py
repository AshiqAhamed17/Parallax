"""Live edge & expected-value computation (Task 10.5).

Turns "model vs market" into an actionable number for open markets:

- **Edge** = `P_model − P_market` (signed; positive → model thinks YES more likely than the market).
- **EV** of a unit bet on the model-favored side, using the task's formula
  `EV = P(win)·profit − P(lose)·loss − fees − slippage`. For a share priced at the market
  probability, the gross term works out to `|edge|`, so net `EV = |edge| − fees − slippage`.

Only positive-EV predictions (edge big enough to clear costs) are actionable; negative-EV ones are
filtered out (a small edge that fees/slippage eat is not a bet worth flagging). This never places a
bet (constraint §2.1) — it writes `model_predictions` rows for the read-only dashboard.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

import pandas as pd

from parallax_research.storage import ensure_model_predictions


@dataclass(frozen=True)
class EdgeEV:
    """Edge/EV for one (p_model, p_market) pair on the model-favored side."""

    p_model: float
    p_market: float
    edge: float          # p_model - p_market (signed)
    side: str            # "YES" or "NO" — the side the model favors
    p_win: float
    profit: float        # payoff per unit stake if the bet wins
    p_lose: float
    loss: float          # loss per unit stake if the bet loses
    gross_ev: float      # P(win)*profit - P(lose)*loss  (== |edge|)
    ev: float            # gross_ev - fees - slippage

    @property
    def is_actionable(self) -> bool:
        """A bet worth flagging: positive EV after costs."""
        return self.ev > 0.0


def compute_edge_ev(
    p_model: float,
    p_market: float,
    *,
    fee: float = 0.0,
    slippage: float = 0.0,
) -> EdgeEV:
    """Edge and expected value of a unit bet on the model-favored side.

    A YES share costs `p_market` and pays 1 if YES; a NO share costs `1 - p_market` and pays 1 if
    NO. We bet whichever side the model favors (`edge >= 0` → YES, else NO). `fee`/`slippage` are
    per-unit cost estimates subtracted from the gross EV.
    """
    edge = p_model - p_market
    if edge >= 0.0:
        side, p_win, profit, p_lose, loss = "YES", p_model, 1.0 - p_market, 1.0 - p_model, p_market
    else:
        side, p_win, profit, p_lose, loss = "NO", 1.0 - p_model, p_market, p_model, 1.0 - p_market

    gross_ev = p_win * profit - p_lose * loss
    ev = gross_ev - fee - slippage
    return EdgeEV(
        p_model=p_model,
        p_market=p_market,
        edge=edge,
        side=side,
        p_win=p_win,
        profit=profit,
        p_lose=p_lose,
        loss=loss,
        gross_ev=gross_ev,
        ev=ev,
    )


@dataclass(frozen=True)
class OpenMarketPrediction:
    market_id: str
    ts_ns: int
    edge_ev: EdgeEV


# Latest feature snapshot per OPEN Manifold market, with the market-implied prob at that instant.
_OPEN_QUERY = """
SELECT
    f.market_id        AS market_id,
    f.ts_ns            AS ts_ns,
    f.prob_velocity    AS prob_velocity,
    f.bet_arrival_rate AS bet_arrival_rate,
    f.realized_vol     AS realized_vol,
    p.probability      AS market_prob
FROM feature_snapshots f
JOIN markets m ON m.market_id = f.market_id
LEFT JOIN probability_snapshots p ON p.market_id = f.market_id AND p.ts_ns = f.ts_ns
WHERE m.platform = 'manifold'
  AND m.resolved_outcome IS NULL
  AND f.ts_ns = (SELECT MAX(ts_ns) FROM feature_snapshots f2 WHERE f2.market_id = f.market_id)
ORDER BY f.market_id
"""


def evaluate_open_markets(
    conn: sqlite3.Connection,
    model,
    *,
    fee: float = 0.0,
    slippage: float = 0.0,
) -> list[OpenMarketPrediction]:
    """Compute edge/EV for every open Manifold market that has a latest snapshot and a market price.

    `model` is any fitted object with `predict_proba(df) -> array of P(YES)` (e.g. `BaselineModel`).
    Markets with no market price (join-miss) are skipped — edge is undefined without one.
    """
    df = pd.read_sql_query(_OPEN_QUERY, conn)
    if df.empty:
        return []
    df = df.dropna(subset=["market_prob"]).reset_index(drop=True)
    if df.empty:
        return []

    p_models = model.predict_proba(df)
    predictions = []
    for p_model, row in zip(p_models, df.itertuples(index=False), strict=True):
        ee = compute_edge_ev(
            float(p_model), float(row.market_prob), fee=fee, slippage=slippage
        )
        predictions.append(OpenMarketPrediction(str(row.market_id), int(row.ts_ns), ee))
    return predictions


def store_predictions(
    conn: sqlite3.Connection,
    predictions: list[OpenMarketPrediction],
    *,
    min_ev: float = 0.0,
) -> int:
    """Write predictions with `ev > min_ev` into `model_predictions`. Returns rows written.

    The `min_ev` filter is where negative-EV (cost-losing) predictions are dropped — only bets worth
    flagging are persisted for the dashboard.
    """
    ensure_model_predictions(conn)
    written = 0
    for pred in predictions:
        if pred.edge_ev.ev <= min_ev:
            continue
        conn.execute(
            "INSERT INTO model_predictions (market_id, ts_ns, p_model, p_market, edge, ev) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                pred.market_id,
                pred.ts_ns,
                pred.edge_ev.p_model,
                pred.edge_ev.p_market,
                pred.edge_ev.edge,
                pred.edge_ev.ev,
            ),
        )
        written += 1
    conn.commit()
    return written


def evaluate_and_store(
    conn: sqlite3.Connection,
    model,
    *,
    fee: float = 0.0,
    slippage: float = 0.0,
    min_ev: float = 0.0,
) -> int:
    """Evaluate open markets and persist the actionable (positive-EV) predictions. Returns count."""
    predictions = evaluate_open_markets(conn, model, fee=fee, slippage=slippage)
    return store_predictions(conn, predictions, min_ev=min_ev)
