"""Baseline probability model (Task 10.2).

A deliberately simple, honest baseline: logistic regression over the Phase-3 features + the
market-implied probability, wrapped so it consumes the labeled DataFrame from Task 10.1 directly.
"Baseline" is the point — the goal (Task 10.3–10.4) is to show whether even a simple model is
*calibrated*, not to win an accuracy contest. A confident-but-miscalibrated model is worse than
useless (doc 01), so we start simple and measure.

Pipeline: impute missing values (e.g. a `market_prob` join-miss from Task 10.1) → standardize →
`LogisticRegression`. If the training labels are all one class (can't fit logistic), the model
falls back to predicting the historical **base rate** — the other baseline the task allows, and a
sane degenerate default.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from parallax_research.calibration.dataset import FEATURE_COLUMNS, LABEL_COLUMN


class BaselineModel:
    """Logistic-regression baseline with a base-rate fallback.

    Fit on a DataFrame shaped like `extract_training_dataset`'s output; `predict_proba` returns the
    probability of outcome=1 (YES) as a 1-D array, one entry per row.
    """

    def __init__(self, feature_columns: list[str] | None = None) -> None:
        self.feature_columns = list(feature_columns or FEATURE_COLUMNS)
        self._pipeline: Pipeline | None = None
        self._base_rate: float | None = None
        self._fitted = False

    def fit(self, df: pd.DataFrame) -> BaselineModel:
        """Fit on `df` (must contain `feature_columns` and the label column). Returns self."""
        y = df[LABEL_COLUMN].to_numpy(dtype=int)
        self._base_rate = float(y.mean()) if len(y) else 0.5

        if len(np.unique(y)) < 2:
            # Only one class present -> logistic regression is undefined; predict the base rate.
            self._pipeline = None
        else:
            x = df[self.feature_columns].to_numpy(dtype=float)
            self._pipeline = Pipeline(
                [
                    ("impute", SimpleImputer(strategy="mean")),
                    ("scale", StandardScaler()),
                    ("clf", LogisticRegression(max_iter=1000)),
                ]
            ).fit(x, y)

        self._fitted = True
        return self

    def predict_proba(self, df: pd.DataFrame) -> np.ndarray:
        """P(outcome=1) for each row of `df`, as a 1-D float array in [0, 1]."""
        if not self._fitted:
            raise RuntimeError("BaselineModel.predict_proba called before fit()")
        n = len(df)
        if self._pipeline is None:
            return np.full(n, float(self._base_rate), dtype=float)
        x = df[self.feature_columns].to_numpy(dtype=float)
        return self._pipeline.predict_proba(x)[:, 1]

    @property
    def base_rate(self) -> float | None:
        """The training-set YES rate (also the prediction when the model falls back)."""
        return self._base_rate
