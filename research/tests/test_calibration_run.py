"""Anti-lookahead guard + historical calibration run tests (Task 10.4)."""

import sqlite3

import pandas as pd
import pytest

from parallax_research.calibration import extract_training_dataset, run_calibration
from parallax_research.storage import ensure_schema

CLOSE_ISO = "2026-01-01T00:00:00Z"
CLOSE_NS = int(pd.Timestamp(CLOSE_ISO).value)  # ns since epoch (UTC)
BEFORE_NS = CLOSE_NS - 3_600_000_000_000  # 1 hour before close
AFTER_NS = CLOSE_NS + 3_600_000_000_000  # 1 hour after close


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    ensure_schema(c)
    yield c
    c.close()


def _resolved_market(conn, market_id, outcome, close_time=CLOSE_ISO):
    conn.execute(
        "INSERT INTO markets (market_id, platform, question_text, close_time, resolved_outcome) "
        "VALUES (?, 'manifold', 'Q?', ?, ?)",
        (market_id, close_time, outcome),
    )


def _snapshot(conn, market_id, ts_ns, *, vel=0.1, rate=1.0, vol=0.02, prob=0.6):
    conn.execute(
        "INSERT INTO feature_snapshots (market_id, ts_ns, prob_velocity, bet_arrival_rate, realized_vol) "
        "VALUES (?, ?, ?, ?, ?)",
        (market_id, ts_ns, vel, rate, vol),
    )
    conn.execute(
        "INSERT INTO probability_snapshots (market_id, ts_ns, probability) VALUES (?, ?, ?)",
        (market_id, ts_ns, prob),
    )


# --- Anti-lookahead guard (the required 10.4 test) -------------------------------------------------

def test_feature_after_close_is_excluded_by_default(conn):
    _resolved_market(conn, "mf", outcome=1)
    _snapshot(conn, "mf", BEFORE_NS)  # legitimate: before close
    _snapshot(conn, "mf", AFTER_NS)   # look-ahead: at/after close -> must be dropped
    conn.commit()

    df = extract_training_dataset(conn)  # before_close_only=True by default
    assert list(df["ts_ns"]) == [BEFORE_NS]


def test_guard_can_be_disabled_for_diagnostics(conn):
    _resolved_market(conn, "mf", outcome=1)
    _snapshot(conn, "mf", BEFORE_NS)
    _snapshot(conn, "mf", AFTER_NS)
    conn.commit()

    df = extract_training_dataset(conn, before_close_only=False)
    assert sorted(df["ts_ns"]) == sorted([BEFORE_NS, AFTER_NS])


def test_snapshot_exactly_at_close_is_excluded(conn):
    # "strictly before close" -> a snapshot exactly at close_time is look-ahead and dropped.
    _resolved_market(conn, "mf", outcome=1)
    _snapshot(conn, "mf", CLOSE_NS)
    conn.commit()
    assert extract_training_dataset(conn).empty


def test_unparseable_close_time_keeps_rows(conn):
    _resolved_market(conn, "mf", outcome=1, close_time="not-a-date")
    _snapshot(conn, "mf", BEFORE_NS)
    conn.commit()
    # No usable cutoff -> keep the row rather than silently dropping data.
    assert len(extract_training_dataset(conn)) == 1


# --- Historical calibration run --------------------------------------------------------------------

def test_run_calibration_produces_sane_metrics(conn):
    # A well-separated synthetic set -> low Brier, sensible reliability.
    for i in range(20):
        _resolved_market(conn, f"yes-{i}", outcome=1)
        _snapshot(conn, f"yes-{i}", BEFORE_NS, vel=0.2, rate=3.0, vol=0.08, prob=0.85)
        _resolved_market(conn, f"no-{i}", outcome=0)
        _snapshot(conn, f"no-{i}", BEFORE_NS, vel=-0.2, rate=0.5, vol=0.02, prob=0.15)
    conn.commit()

    report = run_calibration(conn, n_bins=10)
    assert report.n_examples == 40
    assert report.n_markets == 40
    assert report.base_rate == pytest.approx(0.5)
    assert 0.0 <= report.brier <= 0.25  # separable -> comfortably better than 0.25 (always-0.5)
    assert 0.0 <= report.ece <= 1.0
    md = report.to_markdown(title="T", note="n", command="c")
    assert "Brier score" in md and "Reliability diagram" in md


def test_run_calibration_raises_without_data(conn):
    with pytest.raises(ValueError):
        run_calibration(conn)
