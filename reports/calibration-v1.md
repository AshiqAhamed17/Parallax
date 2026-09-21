# Parallax — Calibration v1 (synthetic demonstration)

> SYNTHETIC DEMONSTRATION — no resolved Manifold markets have been collected yet (the collector does not backfill resolution / question text; Task 4.2 gap). These numbers come from a deterministic synthetic labeled dataset that exercises the full calibration pipeline end-to-end (extract -> fit -> score) with the anti-lookahead guard ON. Regenerate on real data with scripts/run_calibration.py once resolved markets exist (§2.3: numbers are measured, not fabricated — this run is on synthetic data and labeled as such).

## Run

- Command: `synthetic run — see scripts/run_calibration.py for the real-data command`
- Training examples (feature snapshots, pre-close): 120
- Distinct resolved markets: 120
- Base rate (YES fraction): 0.5083

## Calibration metrics

| Metric | Value | Meaning |
|---|---:|---|
| Brier score | 0.2062 | mean (p−outcome)²; lower is better, 0 perfect |
| Expected calibration error | 0.0415 | avg \|observed−predicted\|; 0 perfect |

## Reliability diagram data

| Bin | Count | Mean predicted | Observed frequency |
|---|---:|---:|---:|
| [0.10, 0.20) | 6 | 0.1856 | 0.3333 |
| [0.20, 0.30) | 21 | 0.2473 | 0.2381 |
| [0.30, 0.40) | 16 | 0.3488 | 0.2500 |
| [0.40, 0.50) | 16 | 0.4504 | 0.5000 |
| [0.50, 0.60) | 15 | 0.5529 | 0.5333 |
| [0.60, 0.70) | 16 | 0.6511 | 0.6250 |
| [0.70, 0.80) | 21 | 0.7526 | 0.7619 |
| [0.80, 0.90) | 9 | 0.8202 | 0.8889 |
