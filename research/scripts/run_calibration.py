#!/usr/bin/env python3
"""Run the historical calibration and write `reports/calibration-v1.md` (Task 10.4).

Reads resolved Manifold markets from the SQLite DB, fits the baseline model with the anti-lookahead
guard on, scores calibration (Brier / reliability / ECE), and writes a Markdown report.

Usage:
    uv run python scripts/run_calibration.py --db data/parallax.db --out ../reports/calibration-v1.md
"""

from __future__ import annotations

import argparse
import sqlite3
import sys

from parallax_research.calibration.run import run_calibration


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Historical calibration run.")
    parser.add_argument("--db", default="data/parallax.db", help="SQLite database path.")
    parser.add_argument("--out", default=None, help="Write the Markdown report here (else stdout).")
    parser.add_argument("--bins", type=int, default=10, help="Reliability-diagram bin count.")
    args = parser.parse_args(argv)

    conn = sqlite3.connect(args.db)
    try:
        report = run_calibration(conn, n_bins=args.bins)
    except ValueError as exc:
        print(f"calibration skipped: {exc}", file=sys.stderr)
        return 1
    finally:
        conn.close()

    md = report.to_markdown(
        title="Parallax — Calibration v1",
        note="Historical calibration of the baseline model against resolved Manifold markets "
        "(anti-lookahead guard on; in-sample scoring).",
        command=f"uv run python scripts/run_calibration.py --db {args.db} --bins {args.bins}",
    )
    if args.out:
        with open(args.out, "w") as fh:
            fh.write(md)
        print(f"wrote {args.out}", file=sys.stderr)
    else:
        print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
