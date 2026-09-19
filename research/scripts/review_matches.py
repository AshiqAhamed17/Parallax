#!/usr/bin/env python3
"""Interactive CLI to review pending market matches (Task 8.4).

Lists each `pending` Manifold↔Polymarket candidate and lets a human confirm/reject/skip it. Only
confirmed matches ever drive a divergence signal (constraint §2.2), so this is the human gate on top
of the fuzzy matcher's suggestions.

Usage:
    uv run python scripts/review_matches.py --db data/parallax.db
"""

from __future__ import annotations

import argparse
import sqlite3
import sys

from parallax_research.matching.repository import MarketMatch, list_by_status
from parallax_research.matching.review import (
    CONFIRM,
    QUIT,
    REJECT,
    SKIP,
    review_pending,
)

_KEYMAP = {"c": CONFIRM, "r": REJECT, "s": SKIP, "q": QUIT}


def _format(match: MarketMatch) -> str:
    conf = "n/a" if match.confidence is None else f"{match.confidence:.3f}"
    return (
        f"\n#{match.id}  (score={conf})\n"
        f"  manifold : {match.manifold_market_id}\n"
        f"  {match.platform:<9}: {match.external_market_id}"
    )


def _interactive_decide(match: MarketMatch) -> str:
    print(_format(match))
    while True:
        choice = input("  [c]onfirm / [r]eject / [s]kip / [q]uit > ").strip().lower()
        if choice in _KEYMAP:
            return _KEYMAP[choice]
        print("  please enter c, r, s, or q")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Review pending Manifold↔Polymarket market matches.")
    parser.add_argument("--db", default="data/parallax.db", help="Path to the SQLite database.")
    args = parser.parse_args(argv)

    conn = sqlite3.connect(args.db)
    try:
        pending = list_by_status(conn, "pending")
        if not pending:
            print("No pending matches to review.")
            return 0
        print(f"{len(pending)} pending match(es) to review.")
        summary = review_pending(conn, _interactive_decide)
    finally:
        conn.close()

    print(
        f"\nDone: confirmed={summary.confirmed} rejected={summary.rejected} "
        f"skipped={summary.skipped} (reviewed {summary.reviewed})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
