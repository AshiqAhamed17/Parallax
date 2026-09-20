"""Scheduled divergence detection tests (Task 9.3). In-memory SQLite, bounded loop."""

import sqlite3

import pytest

from parallax_research.arbitrage import run_detection_loop, run_detection_once
from parallax_research.matching.repository import confirm, insert_candidate
from parallax_research.storage import ensure_schema

STAMP = "2026-09-19T12:00:00+00:00"


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    ensure_schema(c)
    yield c
    c.close()


def _seed_confirmed_divergence(conn, manifold_id, poly_id, p_manifold, p_polymarket):
    conn.execute(
        "INSERT INTO probability_snapshots (market_id, ts_ns, probability) VALUES (?, ?, ?)",
        (manifold_id, 1000, p_manifold),
    )
    conn.execute(
        "INSERT INTO cross_source_snapshots (market_id, polled_at, community_prediction) "
        "VALUES (?, ?, ?)",
        (poly_id, STAMP, p_polymarket),
    )
    confirm(conn, insert_candidate(conn, manifold_market_id=manifold_id, external_market_id=poly_id))
    conn.commit()


def _signal_count(conn):
    return conn.execute("SELECT COUNT(*) FROM arbitrage_signals").fetchone()[0]


def test_run_once_persists_signals(conn):
    _seed_confirmed_divergence(conn, "mf-a", "0xa", 0.30, 0.55)  # gap 0.25
    n = run_detection_once(conn, threshold=0.05, detected_at=STAMP)
    assert n == 1
    assert _signal_count(conn) == 1


def test_run_once_on_empty_db_writes_nothing(conn):
    # No confirmed matches -> no signals, and it must not raise (arbitrage_signals ensured).
    assert run_detection_once(conn, threshold=0.05) == 0
    assert _signal_count(conn) == 0


def test_loop_respects_max_runs_and_accumulates(conn):
    _seed_confirmed_divergence(conn, "mf-a", "0xa", 0.30, 0.55)
    runs = run_detection_loop(conn, interval_secs=0, threshold=0.05, max_runs=3)
    assert runs == 3
    # Each pass re-detects the same divergence and appends a fresh signal row (a time series).
    assert _signal_count(conn) == 3


def test_loop_writes_nothing_without_confirmed_divergences(conn):
    # A confirmed pair that agrees (within threshold) -> no signals across runs.
    _seed_confirmed_divergence(conn, "mf-c", "0xc", 0.50, 0.51)
    runs = run_detection_loop(conn, interval_secs=0, threshold=0.05, max_runs=2)
    assert runs == 2
    assert _signal_count(conn) == 0
