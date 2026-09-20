"""End-to-end divergence persistence tests (Task 9.2): synthetic snapshots -> arbitrage_signals."""

import json
import sqlite3

import pytest

from parallax_research.arbitrage import SIGNAL_TYPE, detect_and_persist, persist_signal
from parallax_research.arbitrage.cross_source_divergence import DivergenceSignal
from parallax_research.matching.repository import confirm, insert_candidate
from parallax_research.storage import ensure_schema

STAMP = "2026-09-19T12:00:00+00:00"


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    ensure_schema(c)
    yield c
    c.close()


def _seed_pair(conn, manifold_id, poly_id, p_manifold, p_polymarket, *, confirmed=True):
    conn.execute(
        "INSERT INTO probability_snapshots (market_id, ts_ns, probability) VALUES (?, ?, ?)",
        (manifold_id, 1000, p_manifold),
    )
    conn.execute(
        "INSERT INTO cross_source_snapshots (market_id, polled_at, community_prediction) "
        "VALUES (?, ?, ?)",
        (poly_id, STAMP, p_polymarket),
    )
    mid = insert_candidate(conn, manifold_market_id=manifold_id, external_market_id=poly_id)
    if confirmed:
        confirm(conn, mid)
    conn.commit()


def _signals(conn):
    return conn.execute(
        "SELECT type, market_refs, edge, detected_at, details_json FROM arbitrage_signals ORDER BY id"
    ).fetchall()


def test_detect_and_persist_end_to_end(conn):
    # Two confirmed pairs diverge; one confirmed pair agrees; one big-gap pair is only pending.
    _seed_pair(conn, "mf-a", "0xa", 0.30, 0.50)  # gap 0.20 -> signal
    _seed_pair(conn, "mf-b", "0xb", 0.80, 0.60)  # gap 0.20 -> signal
    _seed_pair(conn, "mf-c", "0xc", 0.50, 0.52)  # gap 0.02 -> no signal
    _seed_pair(conn, "mf-p", "0xp", 0.10, 0.90, confirmed=False)  # pending -> ignored

    written = detect_and_persist(conn, threshold=0.05, detected_at=STAMP)
    assert written == 2

    rows = _signals(conn)
    assert len(rows) == 2
    assert all(r[0] == SIGNAL_TYPE for r in rows)
    # Confirm the pending pair never produced a signal.
    all_refs = [json.loads(r[1]) for r in rows]
    assert ["mf-p", "0xp"] not in all_refs
    assert ["mf-a", "0xa"] in all_refs and ["mf-b", "0xb"] in all_refs


def test_persisted_row_shape(conn):
    _seed_pair(conn, "mf-a", "0xa", 0.30, 0.50)
    detect_and_persist(conn, threshold=0.05, detected_at=STAMP)

    row = _signals(conn)[0]
    sig_type, market_refs, edge, detected_at, details_json = row
    assert sig_type == "cross_source_divergence"
    assert json.loads(market_refs) == ["mf-a", "0xa"]
    assert edge == pytest.approx(-0.20)  # p_manifold - p_polymarket
    assert detected_at == STAMP

    details = json.loads(details_json)
    assert details["p_manifold"] == 0.30
    assert details["p_polymarket"] == 0.50
    assert details["divergence"] == pytest.approx(0.20)
    assert details["direction"] == "polymarket_higher"
    assert "not tradeable arbitrage" in details["note"]


def test_persist_signal_returns_row_id(conn):
    sig = DivergenceSignal(
        manifold_market_id="mf",
        polymarket_market_id="0x",
        p_manifold=0.7,
        p_polymarket=0.4,
        edge=0.3,
        detected_at=STAMP,
    )
    rid = persist_signal(conn, sig)
    assert rid == 1
    assert len(_signals(conn)) == 1


def test_nothing_persisted_when_no_confirmed_divergences(conn):
    _seed_pair(conn, "mf-c", "0xc", 0.50, 0.51)  # confirmed but within threshold
    assert detect_and_persist(conn, threshold=0.05, detected_at=STAMP) == 0
    assert _signals(conn) == []
