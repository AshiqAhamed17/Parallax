"""Tests for the market_matches repository (Task 8.1). In-memory SQLite."""

import sqlite3

import pytest

from parallax_research.matching import (
    confirm,
    ensure_market_matches,
    get,
    insert_candidate,
    list_by_status,
    list_confirmed,
    reject,
)


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    ensure_market_matches(c)
    yield c
    c.close()


def test_ensure_schema_is_idempotent(conn):
    ensure_market_matches(conn)  # second call must not error
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='market_matches'"
    ).fetchall()
    assert tables == [("market_matches",)]


def test_insert_candidate_defaults_to_pending(conn):
    mid = insert_candidate(
        conn,
        manifold_market_id="mf-1",
        external_market_id="0xpoly1",
        confidence=0.91,
    )
    m = get(conn, mid)
    assert m is not None
    assert m.manifold_market_id == "mf-1"
    assert m.external_market_id == "0xpoly1"
    assert m.platform == "polymarket"  # explicit default, not the legacy DB default
    assert m.confidence == 0.91
    assert m.status == "pending"


def test_insert_candidate_allows_null_confidence(conn):
    mid = insert_candidate(conn, manifold_market_id="mf-2", external_market_id="0xpoly2")
    assert get(conn, mid).confidence is None


def test_confirm_moves_candidate_into_list_confirmed(conn):
    mid = insert_candidate(conn, manifold_market_id="mf-3", external_market_id="0xpoly3")
    assert confirm(conn, mid) is True
    assert get(conn, mid).status == "confirmed"
    confirmed = list_confirmed(conn)
    assert [m.id for m in confirmed] == [mid]


def test_reject_keeps_it_out_of_list_confirmed(conn):
    mid = insert_candidate(conn, manifold_market_id="mf-4", external_market_id="0xpoly4")
    assert reject(conn, mid) is True
    assert get(conn, mid).status == "rejected"
    assert list_confirmed(conn) == []


def test_list_confirmed_returns_only_confirmed(conn):
    pending = insert_candidate(conn, manifold_market_id="mf-p", external_market_id="0xp")
    confirmed = insert_candidate(conn, manifold_market_id="mf-c", external_market_id="0xc")
    rejected = insert_candidate(conn, manifold_market_id="mf-r", external_market_id="0xr")
    confirm(conn, confirmed)
    reject(conn, rejected)

    ids = {m.id for m in list_confirmed(conn)}
    assert ids == {confirmed}
    assert pending not in ids and rejected not in ids
    assert {m.id for m in list_by_status(conn, "pending")} == {pending}
    assert {m.id for m in list_by_status(conn, "rejected")} == {rejected}


def test_confirm_reject_on_missing_id_returns_false(conn):
    assert confirm(conn, 999) is False
    assert reject(conn, 999) is False
    assert get(conn, 999) is None
