"""Calibration scoring (Task 10.3): Brier score + reliability-diagram data.

These measure whether a probabilistic model is *calibrated* — i.e. whether events it calls "70%"
actually happen ~70% of the time — which (doc 01) is the whole point of the model: a confident but
miscalibrated model is worse than useless.

- `brier_score`: mean squared error of probabilistic predictions (lower is better; 0 is perfect).
- `reliability_curve`: bins predictions and reports, per bin, the mean predicted probability vs the
  observed outcome frequency — the (x, y) points of a reliability diagram.
- `expected_calibration_error`: a single summary — the count-weighted average gap between predicted
  and observed across bins (0 is perfectly calibrated).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike


@dataclass(frozen=True)
class ReliabilityBin:
    """One bin of a reliability diagram. `mean_predicted`/`observed_frequency` are None when empty."""

    lower: float
    upper: float
    count: int
    mean_predicted: float | None
    observed_frequency: float | None


def _as_pair(y_true: ArrayLike, y_prob: ArrayLike) -> tuple[np.ndarray, np.ndarray]:
    yt = np.asarray(y_true, dtype=float)
    yp = np.asarray(y_prob, dtype=float)
    if yt.shape != yp.shape:
        raise ValueError(f"y_true and y_prob shape mismatch: {yt.shape} vs {yp.shape}")
    if yt.size == 0:
        raise ValueError("cannot score an empty set")
    return yt, yp


def brier_score(y_true: ArrayLike, y_prob: ArrayLike) -> float:
    """Mean of `(p - outcome)^2`. `y_true` in {0,1}, `y_prob` in [0,1]. Lower is better."""
    yt, yp = _as_pair(y_true, y_prob)
    return float(np.mean((yp - yt) ** 2))


def reliability_curve(
    y_true: ArrayLike, y_prob: ArrayLike, *, n_bins: int = 10
) -> list[ReliabilityBin]:
    """Bin predictions into `n_bins` equal-width buckets over [0, 1] and summarize each.

    Bins are lower-inclusive; the top bin captures p == 1.0. Empty bins are returned with count 0
    and `None` means so a plotter can skip them.
    """
    if n_bins < 1:
        raise ValueError("n_bins must be >= 1")
    yt, yp = _as_pair(y_true, y_prob)
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    idx = np.clip((yp * n_bins).astype(int), 0, n_bins - 1)

    bins: list[ReliabilityBin] = []
    for b in range(n_bins):
        sel = idx == b
        count = int(sel.sum())
        if count == 0:
            bins.append(ReliabilityBin(float(edges[b]), float(edges[b + 1]), 0, None, None))
        else:
            bins.append(
                ReliabilityBin(
                    lower=float(edges[b]),
                    upper=float(edges[b + 1]),
                    count=count,
                    mean_predicted=float(yp[sel].mean()),
                    observed_frequency=float(yt[sel].mean()),
                )
            )
    return bins


def expected_calibration_error(
    y_true: ArrayLike, y_prob: ArrayLike, *, n_bins: int = 10
) -> float:
    """Count-weighted average `|observed - predicted|` across non-empty bins (0 = calibrated)."""
    bins = reliability_curve(y_true, y_prob, n_bins=n_bins)
    total = sum(b.count for b in bins)
    if total == 0:
        raise ValueError("cannot compute ECE on an empty set")
    ece = 0.0
    for b in bins:
        if b.count and b.observed_frequency is not None and b.mean_predicted is not None:
            ece += (b.count / total) * abs(b.observed_frequency - b.mean_predicted)
    return ece
