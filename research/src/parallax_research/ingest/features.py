"""Feature reconstruction from Manifold bet history (Task LD.3).

The Rust feature-engine (Phase 3) computes these live from the bet stream; here we recompute the
same three features from a market's REST bet history so backfilled markets carry real features for
the calibration model — one consistent definition used for both open markets (prediction) and
resolved markets (training).
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass

from parallax_research.adapters.manifold import ManifoldBet

# How many trailing bets define the "recent" window the features summarize.
_WINDOW = 25


@dataclass(frozen=True)
class Features:
    prob_velocity: float  # change in probability per second over the window
    bet_arrival_rate: float  # bets per second over the window
    realized_vol: float  # std of consecutive probability changes in the window


def compute_features(bets: list[ManifoldBet], *, window: int = _WINDOW) -> Features:
    """Summarize the most recent `window` bets (bets must be sorted oldest→newest).

    All zeros when there aren't enough bets or they share a timestamp (no time span to divide by) —
    a defensible neutral prior rather than a divide-by-zero.
    """
    if len(bets) < 2:
        return Features(0.0, 0.0, 0.0)
    recent = bets[-window:]
    probs = [b.prob_after for b in recent]
    times_s = [b.created_time_ms / 1000.0 for b in recent]
    span = times_s[-1] - times_s[0]

    if span > 0:
        prob_velocity = (probs[-1] - probs[0]) / span
        bet_arrival_rate = len(recent) / span
    else:
        prob_velocity = 0.0
        bet_arrival_rate = 0.0

    diffs = [probs[i + 1] - probs[i] for i in range(len(probs) - 1)]
    realized_vol = statistics.pstdev(diffs) if len(diffs) >= 2 else 0.0

    return Features(prob_velocity, bet_arrival_rate, realized_vol)


__all__ = ["Features", "compute_features"]
