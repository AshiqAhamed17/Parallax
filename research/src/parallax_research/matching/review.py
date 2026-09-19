"""Reviewable core for the manual match-review CLI (Task 8.4).

`review_pending` walks the `pending` candidates and applies a caller-supplied decision to each. The
CLI (`scripts/review_matches.py`) wires the decision to interactive keyboard input; tests wire it to
a scripted function — so the review loop itself is fully covered without a TTY.

This is the human sign-off gate constraint §2.2 requires: the fuzzy matcher (8.3) only ever proposes
`pending` candidates; a person confirms or rejects each here before it can drive any signal.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from dataclasses import dataclass

from parallax_research.matching.repository import (
    MarketMatch,
    confirm,
    list_by_status,
    reject,
)

CONFIRM = "confirm"
REJECT = "reject"
SKIP = "skip"
QUIT = "quit"

#: A decider inspects a pending match and returns one of CONFIRM / REJECT / SKIP / QUIT.
Decider = Callable[[MarketMatch], str]


@dataclass
class ReviewSummary:
    confirmed: int = 0
    rejected: int = 0
    skipped: int = 0
    reviewed: int = 0  # total decided before an optional QUIT


def review_pending(conn: sqlite3.Connection, decide: Decider) -> ReviewSummary:
    """Apply `decide` to each pending match in order until they're exhausted or QUIT is returned.

    Iterates a snapshot of the pending set, so confirming/rejecting as we go is safe. Returns a
    tally. Raises ValueError on an unrecognized decision.
    """
    summary = ReviewSummary()
    for match in list_by_status(conn, "pending"):
        action = decide(match)
        if action == QUIT:
            break
        if action == CONFIRM:
            confirm(conn, match.id)
            summary.confirmed += 1
        elif action == REJECT:
            reject(conn, match.id)
            summary.rejected += 1
        elif action == SKIP:
            summary.skipped += 1
        else:
            raise ValueError(f"unknown review action: {action!r}")
        summary.reviewed += 1
    return summary
