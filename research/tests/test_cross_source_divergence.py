"""Cross-source divergence detection tests (Task 9.1). In-memory SQLite, hand-worked examples."""

import sqlite3

import pytest

from parallax_research.arbitrage import detect_divergences, detect_for_match
from parallax_research.matching.repository import MarketMatch, confirm, insert_candidate
from parallax_research.storage import ensure_schema

STAMP = "2026-09-19T12:00:00+00:00"


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    ensure_schema(c)
    yield c
    c.close()


def _seed_manifold(conn, market_id, probability, ts_ns):
    conn.execute(
        "INSERT INTO probability_snapshots (market_id, ts_ns, probability) VALUES (?, ?, ?)",
        (market_id, ts_ns, probability),
    )
    conn.commit()


def _seed_polymarket(conn, market_id, probability):
    conn.execute(
        "INSERT INTO cross_source_snapshots (market_id, polled_at, community_prediction) "
        "VALUES (?, ?, ?)",
        (market_id, STAMP, probability),
    )
    conn.commit()


def _confirmed_match(conn, manifold_id="mf", poly_id="0xpoly") -> MarketMatch:
    mid = insert_candidate(conn, manifold_market_id=manifold_id, external_market_id=poly_id)
    confirm(conn, mid)
    from parallax_research.matching.repository import get

    return get(conn, mid)


def test_flags_when_gap_exceeds_threshold(conn):
    _seed_manifold(conn, "mf", 0.30, ts_ns=1000)
    _seed_polymarket(conn, "0xpoly", 0.45)
    match = _confirmed_match(conn)

    sig = detect_for_match(conn, match, threshold=0.05, detected_at=STAMP)
    assert sig is not None
    assert sig.p_manifold == 0.30
    assert sig.p_polymarket == 0.45
    assert sig.edge == pytest.approx(-0.15)
    assert sig.magnitude == pytest.approx(0.15)
    assert sig.direction == "polymarket_higher"
    assert sig.detected_at == STAMP


def test_not_flagged_when_within_threshold(conn):
    _seed_manifold(conn, "mf", 0.50, ts_ns=1000)
    _seed_polymarket(conn, "0xpoly", 0.52)
    match = _confirmed_match(conn)
    assert detect_for_match(conn, match, threshold=0.05) is None  # 0.02 gap < 0.05


def test_uses_latest_manifold_snapshot(conn):
    _seed_manifold(conn, "mf", 0.30, ts_ns=1000)  # older
    _seed_manifold(conn, "mf", 0.62, ts_ns=2000)  # newer -> used
    _seed_polymarket(conn, "0xpoly", 0.30)
    match = _confirmed_match(conn)

    sig = detect_for_match(conn, match, threshold=0.05)
    assert sig is not None
    assert sig.p_manifold == 0.62
    assert sig.edge == pytest.approx(0.32)
    assert sig.direction == "manifold_higher"


def test_none_when_a_venue_has_no_data(conn):
    _seed_manifold(conn, "mf", 0.30, ts_ns=1000)  # no polymarket snapshot
    match = _confirmed_match(conn)
    assert detect_for_match(conn, match, threshold=0.05) is None


def test_detect_divergences_only_uses_confirmed_matches(conn):
    # A confirmed match with a big gap...
    _seed_manifold(conn, "mf-c", 0.20, ts_ns=1000)
    _seed_polymarket(conn, "0xc", 0.60)
    c_id = insert_candidate(conn, manifold_market_id="mf-c", external_market_id="0xc")
    confirm(conn, c_id)

    # ...and a PENDING match with an equally big gap that must be ignored.
    _seed_manifold(conn, "mf-p", 0.20, ts_ns=1000)
    _seed_polymarket(conn, "0xp", 0.60)
    insert_candidate(conn, manifold_market_id="mf-p", external_market_id="0xp")  # stays pending

    signals = detect_divergences(conn, threshold=0.05, detected_at=STAMP)
    assert len(signals) == 1
    assert signals[0].manifold_market_id == "mf-c"
    assert signals[0].polymarket_market_id == "0xc"


def test_no_signals_when_nothing_confirmed(conn):
    _seed_manifold(conn, "mf", 0.20, ts_ns=1000)
    _seed_polymarket(conn, "0xpoly", 0.60)
    insert_candidate(conn, manifold_market_id="mf", external_market_id="0xpoly")  # pending only
    assert detect_divergences(conn, threshold=0.05) == []
