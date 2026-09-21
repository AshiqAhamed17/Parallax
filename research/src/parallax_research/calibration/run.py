"""Historical calibration run (Task 10.4).

Ties Tasks 10.1–10.3 together: extract the labeled training set (with the anti-lookahead guard on),
fit the `BaselineModel`, and score it (Brier, reliability, ECE) into a `CalibrationReport` that
renders to Markdown for `reports/calibration-v1.md`.

Anti-lookahead: `extract_training_dataset(before_close_only=True)` drops any feature snapshot at/after
its market's close — the model is only ever trained/scored on information that existed strictly
before the market resolved. Scoring here is *in-sample* (fit and evaluate on the same rows), which
flatters the numbers; rigorous held-out validation is the backtester's job (Phase 11). The report
says so.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from parallax_research.calibration.dataset import LABEL_COLUMN, extract_training_dataset
from parallax_research.calibration.model import BaselineModel
from parallax_research.calibration.scoring import (
    ReliabilityBin,
    brier_score,
    expected_calibration_error,
    reliability_curve,
)


@dataclass(frozen=True)
class CalibrationReport:
    n_examples: int
    n_markets: int
    base_rate: float
    brier: float
    ece: float
    reliability: list[ReliabilityBin]

    def to_markdown(self, *, title: str, note: str, command: str) -> str:
        out = [f"# {title}\n", f"> {note}\n"]
        out.append("## Run\n")
        out.append(f"- Command: `{command}`")
        out.append(f"- Training examples (feature snapshots, pre-close): {self.n_examples}")
        out.append(f"- Distinct resolved markets: {self.n_markets}")
        out.append(f"- Base rate (YES fraction): {self.base_rate:.4f}\n")
        out.append("## Calibration metrics\n")
        out.append("| Metric | Value | Meaning |")
        out.append("|---|---:|---|")
        out.append(f"| Brier score | {self.brier:.4f} | mean (p−outcome)²; lower is better, 0 perfect |")
        out.append(f"| Expected calibration error | {self.ece:.4f} | avg \\|observed−predicted\\|; 0 perfect |\n")
        out.append("## Reliability diagram data\n")
        out.append("| Bin | Count | Mean predicted | Observed frequency |")
        out.append("|---|---:|---:|---:|")
        for b in self.reliability:
            if b.count == 0:
                continue
            out.append(
                f"| [{b.lower:.2f}, {b.upper:.2f}) | {b.count} | "
                f"{b.mean_predicted:.4f} | {b.observed_frequency:.4f} |"
            )
        out.append("")
        return "\n".join(out)


def run_calibration(
    conn: sqlite3.Connection,
    *,
    n_bins: int = 10,
    before_close_only: bool = True,
) -> CalibrationReport:
    """Extract (anti-lookahead-guarded), fit, and score. Raises ValueError if there's no data."""
    df = extract_training_dataset(conn, before_close_only=before_close_only)
    if df.empty:
        raise ValueError("no resolved-market training data to calibrate on")

    model = BaselineModel().fit(df)
    y = df[LABEL_COLUMN].to_numpy(dtype=int)
    p = model.predict_proba(df)

    return CalibrationReport(
        n_examples=len(df),
        n_markets=int(df["market_id"].nunique()),
        base_rate=float(y.mean()),
        brier=brier_score(y, p),
        ece=expected_calibration_error(y, p, n_bins=n_bins),
        reliability=reliability_curve(y, p, n_bins=n_bins),
    )
