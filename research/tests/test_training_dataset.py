"""Historical training-dataset extraction tests (Task 10.1). Synthetic in-memory DB."""

import sqlite3

import pandas as pd
import pytest

from parallax_research.calibration import (
    FEATURE_COLUMNS,
    LABEL_COLUMN,
    extract_training_dataset,
)
from parallax_research.storage import ensure_schema


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    ensure_schema(c)
    yield c
    c.close()


def _add_market(conn, market_id, *, platform="manifold", outcome=None):
    conn.execute(
        "INSERT INTO markets (market_id, platform, question_text, close_time, resolved_outcome) "
        "VALUES (?, ?, ?, ?, ?)",
        (market_id, platform, f"Q for {market_id}?", "2026-01-01T00:00:00Z", outcome),
    )
    conn.commit()


def _add_snapshot(conn, market_id, ts_ns, *, vel, rate, vol, prob):
    conn.execute(
        "INSERT INTO feature_snapshots (market_id, ts_ns, prob_velocity, bet_arrival_rate, realized_vol) "
        "VALUES (?, ?, ?, ?, ?)",
        (market_id, ts_ns, vel, rate, vol),
    )
    conn.execute(
        "INSERT INTO probability_snapshots (market_id, ts_ns, probability) VALUES (?, ?, ?)",
        (market_id, ts_ns, prob),
    )
    conn.commit()


def test_extracts_only_resolved_manifold_markets(conn):
    # Resolved YES manifold market with two snapshots.
    _add_market(conn, "mf-yes", outcome=1)
    _add_snapshot(conn, "mf-yes", 1000, vel=0.1, rate=2.0, vol=0.05, prob=0.7)
    _add_snapshot(conn, "mf-yes", 2000, vel=-0.2, rate=1.0, vol=0.03, prob=0.8)
    # Resolved NO manifold market with one snapshot.
    _add_market(conn, "mf-no", outcome=0)
    _add_snapshot(conn, "mf-no", 1500, vel=0.0, rate=0.5, vol=0.01, prob=0.2)
    # Unresolved manifold market — must be excluded.
    _add_market(conn, "mf-open", outcome=None)
    _add_snapshot(conn, "mf-open", 1000, vel=0.3, rate=3.0, vol=0.1, prob=0.5)
    # Resolved but NON-manifold market — must be excluded.
    _add_market(conn, "poly-x", platform="polymarket", outcome=1)
    _add_snapshot(conn, "poly-x", 1000, vel=0.1, rate=1.0, vol=0.02, prob=0.6)

    df = extract_training_dataset(conn)

    assert set(df["market_id"]) == {"mf-yes", "mf-no"}
    assert len(df) == 3  # 2 snapshots for mf-yes + 1 for mf-no
    assert list(df.columns) == [
        "market_id", "ts_ns", "prob_velocity", "bet_arrival_rate", "realized_vol",
        "market_prob", "outcome",
    ]


def test_labels_match_market_outcome(conn):
    _add_market(conn, "mf-yes", outcome=1)
    _add_snapshot(conn, "mf-yes", 1000, vel=0.1, rate=2.0, vol=0.05, prob=0.7)
    _add_market(conn, "mf-no", outcome=0)
    _add_snapshot(conn, "mf-no", 1000, vel=0.0, rate=0.5, vol=0.01, prob=0.2)

    df = extract_training_dataset(conn).set_index("market_id")
    assert df.loc["mf-yes", LABEL_COLUMN] == 1
    assert df.loc["mf-no", LABEL_COLUMN] == 0
    assert df[LABEL_COLUMN].dtype == int


def test_features_and_market_prob_joined_correctly(conn):
    _add_market(conn, "mf-yes", outcome=1)
    _add_snapshot(conn, "mf-yes", 1000, vel=0.15, rate=2.5, vol=0.05, prob=0.73)

    row = extract_training_dataset(conn).iloc[0]
    assert row["prob_velocity"] == 0.15
    assert row["bet_arrival_rate"] == 2.5
    assert row["realized_vol"] == 0.05
    assert row["market_prob"] == 0.73
    assert set(FEATURE_COLUMNS) <= set(extract_training_dataset(conn).columns)


def test_missing_probability_snapshot_yields_nan_market_prob(conn):
    _add_market(conn, "mf-yes", outcome=1)
    # feature snapshot with NO matching probability_snapshots row (ts mismatch).
    conn.execute(
        "INSERT INTO feature_snapshots (market_id, ts_ns, prob_velocity, bet_arrival_rate, realized_vol) "
        "VALUES ('mf-yes', 1000, 0.1, 1.0, 0.02)",
    )
    conn.commit()
    row = extract_training_dataset(conn).iloc[0]
    assert pd.isna(row["market_prob"])  # left-join miss -> null market_prob


def test_empty_db_returns_empty_frame_with_columns(conn):
    df = extract_training_dataset(conn)
    assert df.empty
    assert LABEL_COLUMN in df.columns
    assert "market_prob" in df.columns
