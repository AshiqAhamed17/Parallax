"""Calibration scoring tests (Task 10.3): hand-computed Brier + reliability + ECE."""

import pytest

from parallax_research.calibration import (
    brier_score,
    expected_calibration_error,
    reliability_curve,
)


def test_brier_score_hand_computed():
    # errors: (0.8-1)^2=0.04, (0.3-0)^2=0.09, (0.6-1)^2=0.16 -> mean = 0.29/3
    y_true = [1, 0, 1]
    y_prob = [0.8, 0.3, 0.6]
    assert brier_score(y_true, y_prob) == pytest.approx(0.29 / 3)


def test_brier_perfect_and_worst():
    assert brier_score([1, 0], [1.0, 0.0]) == pytest.approx(0.0)  # perfect
    assert brier_score([1, 0], [0.0, 1.0]) == pytest.approx(1.0)  # maximally wrong


def test_brier_shape_and_empty_errors():
    with pytest.raises(ValueError):
        brier_score([1, 0], [0.5])
    with pytest.raises(ValueError):
        brier_score([], [])


def test_reliability_curve_two_bins():
    # preds 0.1,0.2 -> bin0 (both NO); preds 0.7,0.9 -> bin1 (both YES).
    y_true = [0, 0, 1, 1]
    y_prob = [0.1, 0.2, 0.7, 0.9]
    bins = reliability_curve(y_true, y_prob, n_bins=2)

    assert len(bins) == 2
    b0, b1 = bins
    assert b0.count == 2 and b0.mean_predicted == pytest.approx(0.15) and b0.observed_frequency == 0.0
    assert b1.count == 2 and b1.mean_predicted == pytest.approx(0.8) and b1.observed_frequency == 1.0


def test_reliability_empty_bins_reported_with_none():
    # All predictions land in the top bin; the lower bin is empty.
    bins = reliability_curve([1, 1], [0.9, 0.95], n_bins=2)
    assert bins[0].count == 0 and bins[0].mean_predicted is None
    assert bins[1].count == 2


def test_reliability_top_bin_captures_one():
    bins = reliability_curve([1], [1.0], n_bins=10)
    assert bins[-1].count == 1  # p == 1.0 falls in the last bin, not out of range


def test_expected_calibration_error_hand_computed():
    # From the two-bin example: |0 - 0.15|*2/4 + |1 - 0.8|*2/4 = 0.075 + 0.10 = 0.175
    y_true = [0, 0, 1, 1]
    y_prob = [0.1, 0.2, 0.7, 0.9]
    assert expected_calibration_error(y_true, y_prob, n_bins=2) == pytest.approx(0.175)


def test_perfectly_calibrated_has_zero_ece():
    # Half the "0.5" predictions are YES -> observed 0.5 matches predicted 0.5.
    y_prob = [0.5] * 10
    y_true = [1, 0] * 5
    assert expected_calibration_error(y_true, y_prob, n_bins=1) == pytest.approx(0.0)
