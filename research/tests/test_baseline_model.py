"""Baseline probability model tests (Task 10.2)."""

import numpy as np
import pandas as pd
import pytest

from parallax_research.calibration import FEATURE_COLUMNS, LABEL_COLUMN, BaselineModel


def _separable_dataset(n_per_class: int = 40) -> pd.DataFrame:
    """A cleanly separable set: YES markets sit high on every feature, NO markets low."""
    rows = []
    for i in range(n_per_class):
        wiggle = (i % 5) * 0.01  # small deterministic spread so it's not degenerate
        rows.append(
            {
                "prob_velocity": 0.10 + wiggle,
                "bet_arrival_rate": 3.0 + wiggle,
                "realized_vol": 0.08 + wiggle,
                "market_prob": 0.80 + wiggle,
                LABEL_COLUMN: 1,
            }
        )
        rows.append(
            {
                "prob_velocity": -0.10 - wiggle,
                "bet_arrival_rate": 0.5 + wiggle,
                "realized_vol": 0.02 + wiggle,
                "market_prob": 0.20 - wiggle,
                LABEL_COLUMN: 0,
            }
        )
    return pd.DataFrame(rows)


def test_predicts_separable_data_with_high_accuracy():
    df = _separable_dataset()
    model = BaselineModel().fit(df)
    p = model.predict_proba(df)

    assert p.shape == (len(df),)
    assert np.all((p >= 0.0) & (p <= 1.0))
    accuracy = ((p >= 0.5).astype(int) == df[LABEL_COLUMN].to_numpy()).mean()
    assert accuracy >= 0.9, f"expected clean separation, got accuracy {accuracy}"


def test_probabilities_rank_yes_above_no():
    df = _separable_dataset()
    model = BaselineModel().fit(df)
    p = model.predict_proba(df)
    yes_mean = p[df[LABEL_COLUMN] == 1].mean()
    no_mean = p[df[LABEL_COLUMN] == 0].mean()
    assert yes_mean > no_mean
    assert yes_mean > 0.5 > no_mean


def test_single_class_falls_back_to_base_rate():
    # All-YES training set -> logistic can't fit -> predict the base rate (1.0 here).
    df = pd.DataFrame(
        [{**{c: 0.5 for c in FEATURE_COLUMNS}, LABEL_COLUMN: 1} for _ in range(10)]
    )
    model = BaselineModel().fit(df)
    assert model.base_rate == 1.0
    p = model.predict_proba(df)
    assert np.allclose(p, 1.0)


def test_base_rate_reflects_class_balance():
    # 30% YES -> base rate 0.3 when it falls back... but here both classes exist, so just check
    # base_rate is recorded correctly regardless of the fitted path.
    df = _separable_dataset()
    model = BaselineModel().fit(df)
    assert model.base_rate == pytest.approx(0.5)  # balanced dataset


def test_predict_before_fit_raises():
    with pytest.raises(RuntimeError):
        BaselineModel().predict_proba(_separable_dataset())


def test_tolerates_nan_market_prob():
    # A join-miss (Task 10.1) leaves market_prob NaN; the imputer must handle it, not crash.
    df = _separable_dataset()
    df.loc[df.index[:5], "market_prob"] = np.nan
    model = BaselineModel().fit(df)
    p = model.predict_proba(df)
    assert not np.isnan(p).any()
