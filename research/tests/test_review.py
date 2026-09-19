"""Tests for the match-review loop (Task 8.4). Scripted decider, no TTY."""

import sqlite3

import pytest

from parallax_research.matching import (
    ensure_market_matches,
    get,
    insert_candidate,
    list_by_status,
    review_pending,
)
from parallax_research.matching.review import CONFIRM, QUIT, REJECT, SKIP


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    ensure_market_matches(c)
    yield c
    c.close()


def _seed(conn, n):
    return [
        insert_candidate(
            conn, manifold_market_id=f"mf-{i}", external_market_id=f"0x{i}", confidence=0.7
        )
        for i in range(n)
    ]


def test_confirm_reject_skip_are_applied(conn):
    ids = _seed(conn, 3)
    decisions = {ids[0]: CONFIRM, ids[1]: REJECT, ids[2]: SKIP}
    summary = review_pending(conn, lambda m: decisions[m.id])

    assert (summary.confirmed, summary.rejected, summary.skipped, summary.reviewed) == (1, 1, 1, 3)
    assert get(conn, ids[0]).status == "confirmed"
    assert get(conn, ids[1]).status == "rejected"
    assert get(conn, ids[2]).status == "pending"  # skipped stays pending for a later pass


def test_quit_stops_early_leaving_rest_pending(conn):
    ids = _seed(conn, 3)
    # Confirm the first, then quit — the remaining two must stay pending.
    seen = []

    def decide(match):
        seen.append(match.id)
        return CONFIRM if match.id == ids[0] else QUIT

    summary = review_pending(conn, decide)
    assert summary.confirmed == 1
    assert summary.reviewed == 1
    assert get(conn, ids[0]).status == "confirmed"
    assert {m.id for m in list_by_status(conn, "pending")} == {ids[1], ids[2]}


def test_only_pending_are_reviewed(conn):
    ids = _seed(conn, 2)
    # Pre-confirm one; it should not be offered to the decider again.
    from parallax_research.matching import confirm

    confirm(conn, ids[0])
    offered = []
    review_pending(conn, lambda m: offered.append(m.id) or SKIP)
    assert offered == [ids[1]]


def test_unknown_action_raises(conn):
    _seed(conn, 1)
    with pytest.raises(ValueError):
        review_pending(conn, lambda m: "maybe")
