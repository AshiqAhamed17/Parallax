"""Chronological replay tests (Task 11.1): merged, strictly time-ordered stream across sources."""

import sqlite3

import pandas as pd
import pytest

from parallax_research.backtester import replay
from parallax_research.storage import ensure_schema

T0 = "2026-01-01T00:00:00+00:00"
T1 = "2026-01-01T01:00:00+00:00"
T2 = "2026-01-01T02:00:00+00:00"


def _ns(iso: str) -> int:
    return int(pd.Timestamp(iso).value)


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    ensure_schema(c)
    yield c
    c.close()


def _seed_mixed(conn):
    # bet and model_prediction both at T0 (a timestamp tie across sources).
    conn.execute(
        "INSERT INTO bets (market_id, ts_ns, prob_before, prob_after, amount, shares, is_limit_order) "
        "VALUES ('m1', ?, 0.5, 0.55, 10, 18, 0)",
        (_ns(T0),),
    )
    conn.execute(
        "INSERT INTO model_predictions (market_id, ts_ns, p_model, p_market, edge, ev) "
        "VALUES ('m1', ?, 0.7, 0.55, 0.15, 0.15)",
        (_ns(T0),),
    )
    # feature and cross_source both at T1 (another tie, different sources).
    conn.execute(
        "INSERT INTO feature_snapshots (market_id, ts_ns, prob_velocity, bet_arrival_rate, realized_vol) "
        "VALUES ('m1', ?, 0.1, 2.0, 0.05)",
        (_ns(T1),),
    )
    conn.execute(
        "INSERT INTO cross_source_snapshots (market_id, polled_at, community_prediction) "
        "VALUES ('m2', ?, 0.42)",
        (T1,),
    )
    # probability snapshot at T2.
    conn.execute(
        "INSERT INTO probability_snapshots (market_id, ts_ns, probability) VALUES ('m1', ?, 0.6)",
        (_ns(T2),),
    )
    conn.commit()


def test_stream_is_strictly_chronological(conn):
    _seed_mixed(conn)
    events = list(replay(conn))
    ts = [e.ts_ns for e in events]
    assert ts == sorted(ts), "timestamps must be non-decreasing"
    # 5 events total across 4 source types.
    assert len(events) == 5
    assert {e.source for e in events} == {"bet", "model_prediction", "feature", "cross_source", "probability"}


def test_source_ordering_and_tie_breaks(conn):
    _seed_mixed(conn)
    order = [(e.source, e.ts_ns) for e in replay(conn)]
    assert order == [
        ("bet", _ns(T0)),            # T0 tie -> bet (rank 0) before...
        ("model_prediction", _ns(T0)),  # ...model_prediction (rank 3)
        ("feature", _ns(T1)),        # T1 tie -> feature (rank 2) before...
        ("cross_source", _ns(T1)),   # ...cross_source (rank 4)
        ("probability", _ns(T2)),
    ]


def test_cross_source_iso_is_normalized_to_ns(conn):
    _seed_mixed(conn)
    cs = next(e for e in replay(conn) if e.source == "cross_source")
    assert cs.ts_ns == _ns(T1)
    assert cs.payload["community_prediction"] == 0.42
    assert cs.market_id == "m2"


def test_range_filter_is_inclusive(conn):
    _seed_mixed(conn)
    # Only the two T1 events fall in [T1, T1].
    windowed = list(replay(conn, start_ns=_ns(T1), end_ns=_ns(T1)))
    assert [e.source for e in windowed] == ["feature", "cross_source"]


def test_payload_carries_row_fields(conn):
    _seed_mixed(conn)
    bet = next(e for e in replay(conn) if e.source == "bet")
    assert bet.payload["prob_after"] == 0.55
    assert bet.payload["amount"] == 10
    assert bet.market_id == "m1"


def test_empty_db_yields_nothing(conn):
    assert list(replay(conn)) == []


def test_monotonic_over_many_interleaved_events(conn):
    # Interleave many events across sources at pseudo-random (but deterministic) times.
    base = _ns(T0)
    for i in range(50):
        conn.execute(
            "INSERT INTO bets (market_id, ts_ns, prob_before, prob_after, amount, shares, is_limit_order) "
            "VALUES ('m', ?, 0.5, 0.5, 1, 1, 0)",
            (base + (i * 2654435761) % 1_000_000,),
        )
        conn.execute(
            "INSERT INTO probability_snapshots (market_id, ts_ns, probability) VALUES ('m', ?, 0.5)",
            (base + (i * 40503) % 1_000_000,),
        )
    conn.commit()
    ts = [e.ts_ns for e in replay(conn)]
    assert len(ts) == 100
    assert all(ts[i] <= ts[i + 1] for i in range(len(ts) - 1))
