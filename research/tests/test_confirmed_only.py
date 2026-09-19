"""Confirmed-only read enforcement (Task 8.5) — the §2.2 boundary."""

import sqlite3

import pytest

from parallax_research.matching import (
    confirm,
    ensure_market_matches,
    insert_candidate,
    is_confirmed,
    list_confirmed,
    reject,
)


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    ensure_market_matches(c)
    yield c
    c.close()


def test_list_confirmed_returns_only_the_confirmed_row(conn):
    # The task's core case: one pending, one confirmed -> only the confirmed is returned.
    pending_id = insert_candidate(conn, manifold_market_id="mf-p", external_market_id="0xp")
    confirmed_id = insert_candidate(conn, manifold_market_id="mf-c", external_market_id="0xc")
    confirm(conn, confirmed_id)

    result = list_confirmed(conn)
    assert [m.id for m in result] == [confirmed_id]
    assert all(m.status == "confirmed" for m in result)
    assert pending_id not in {m.id for m in result}


def test_rejected_rows_are_also_excluded(conn):
    rejected_id = insert_candidate(conn, manifold_market_id="mf-r", external_market_id="0xr")
    reject(conn, rejected_id)
    assert list_confirmed(conn) == []


def test_is_confirmed_gates_each_status(conn):
    pending_id = insert_candidate(conn, manifold_market_id="mf-p", external_market_id="0xp")
    confirmed_id = insert_candidate(conn, manifold_market_id="mf-c", external_market_id="0xc")
    rejected_id = insert_candidate(conn, manifold_market_id="mf-r", external_market_id="0xr")
    confirm(conn, confirmed_id)
    reject(conn, rejected_id)

    assert is_confirmed(conn, confirmed_id) is True
    assert is_confirmed(conn, pending_id) is False
    assert is_confirmed(conn, rejected_id) is False
    assert is_confirmed(conn, 999999) is False  # nonexistent


def test_confirmed_only_after_full_lifecycle(conn):
    # A candidate confirmed then later rejected must drop back out of the confirmed read.
    mid = insert_candidate(conn, manifold_market_id="mf-x", external_market_id="0xx")
    confirm(conn, mid)
    assert [m.id for m in list_confirmed(conn)] == [mid]
    reject(conn, mid)
    assert list_confirmed(conn) == []
    assert is_confirmed(conn, mid) is False
