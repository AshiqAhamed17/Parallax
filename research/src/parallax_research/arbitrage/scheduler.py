"""Scheduled signal detection (Task 9.3 + Task 12.4).

Runs the detectors on an interval and persists any flagged signals. The cadence is matched to the
Polymarket poller (Phase 7.3): the Polymarket side only updates ~hourly, so detecting more often
would just re-scan unchanged data. Like the poller, `run_detection_loop` takes a `max_runs` bound so
tests and one-shot/bounded runs are easy, and it never trades — it only reads snapshots and writes
`arbitrage_signals`.

Two detectors share the scheduled pass:
- **cross-source divergence** (Phase 9) — always runs, over confirmed matches.
- **logical-constraint arbitrage** (Phase 12) — runs when a curated `constraint_config` is supplied,
  persisting actionable violations with `type='logical_constraint'`.
"""

from __future__ import annotations

import logging
import sqlite3
import time

from parallax_research.arbitrage.constraints import CorrelatedMarketGroupsConfig
from parallax_research.arbitrage.cross_source_divergence import (
    DEFAULT_THRESHOLD,
    detect_and_persist,
)
from parallax_research.arbitrage.logical_constraint import (
    DEFAULT_COST_PER_LEG,
    detect_and_persist_violations,
)
from parallax_research.storage import ensure_arbitrage_signals

logger = logging.getLogger(__name__)

#: Match the Polymarket poller's cadence (Phase 7.3) — hourly.
DEFAULT_INTERVAL_SECS = 3600.0


def run_detection_once(
    conn: sqlite3.Connection,
    *,
    threshold: float = DEFAULT_THRESHOLD,
    detected_at: str | None = None,
    constraint_config: CorrelatedMarketGroupsConfig | None = None,
    cost_per_leg: float = DEFAULT_COST_PER_LEG,
) -> int:
    """One detection pass; returns the total number of signals persisted across both detectors.

    Always runs cross-source divergence over confirmed matches. If `constraint_config` is supplied,
    also runs the logical-constraint detector and persists its actionable violations.
    """
    ensure_arbitrage_signals(conn)
    written = detect_and_persist(conn, threshold=threshold, detected_at=detected_at)
    logger.info("divergence detection: persisted %d signal(s)", written)
    if constraint_config is not None:
        constraint_written = detect_and_persist_violations(
            conn,
            constraint_config,
            cost_per_leg=cost_per_leg,
            detected_at=detected_at,
        )
        logger.info(
            "logical-constraint detection: persisted %d signal(s)", constraint_written
        )
        written += constraint_written
    return written


def run_detection_loop(
    conn: sqlite3.Connection,
    *,
    interval_secs: float = DEFAULT_INTERVAL_SECS,
    threshold: float = DEFAULT_THRESHOLD,
    max_runs: int | None = None,
    constraint_config: CorrelatedMarketGroupsConfig | None = None,
    cost_per_leg: float = DEFAULT_COST_PER_LEG,
) -> int:
    """Run detection every `interval_secs`. Returns the number of passes run.

    `max_runs` bounds the loop (tests / bounded runs); None runs forever. A SQL error in one pass is
    logged and retried next interval rather than killing the loop.
    """
    runs = 0
    while max_runs is None or runs < max_runs:
        try:
            run_detection_once(
                conn,
                threshold=threshold,
                constraint_config=constraint_config,
                cost_per_leg=cost_per_leg,
            )
        except sqlite3.Error:
            logger.exception("detection pass failed; will retry next interval")
        runs += 1
        if max_runs is not None and runs >= max_runs:
            break
        time.sleep(interval_secs)
    return runs
