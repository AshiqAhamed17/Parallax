"""Calibration & probability model (Phase 10): training-set extraction, model, scoring."""

from parallax_research.calibration.dataset import (
    FEATURE_COLUMNS,
    LABEL_COLUMN,
    extract_training_dataset,
)
from parallax_research.calibration.model import BaselineModel
from parallax_research.calibration.run import CalibrationReport, run_calibration
from parallax_research.calibration.scoring import (
    ReliabilityBin,
    brier_score,
    expected_calibration_error,
    reliability_curve,
)

__all__ = [
    "FEATURE_COLUMNS",
    "LABEL_COLUMN",
    "BaselineModel",
    "CalibrationReport",
    "ReliabilityBin",
    "brier_score",
    "expected_calibration_error",
    "extract_training_dataset",
    "reliability_curve",
    "run_calibration",
]
