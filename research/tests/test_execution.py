"""Cost modeling + latency-aware execution tests (Task 11.3)."""

import sqlite3

import pytest

from parallax_research.backtester import market_probability_at, simulate_execution
from parallax_research.storage import ensure_schema


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    ensure_schema(c)
    yield c
    c.close()


def _snap(conn, market_id, ts_ns, prob):
    conn.execute(
        "INSERT INTO probability_snapshots (market_id, ts_ns, probability) VALUES (?, ?, ?)",
        (market_id, ts_ns, prob),
    )
    conn.commit()


def test_market_probability_at_uses_latest_at_or_before():
    conn = sqlite3.connect(":memory:")
    ensure_schema(conn)
    _snap(conn, "m", 1000, 0.4)
    _snap(conn, "m", 2000, 0.6)
    assert market_probability_at(conn, "m", 1500) == 0.4  # before the 2000 snapshot
    assert market_probability_at(conn, "m", 2000) == 0.6  # exactly at
    assert market_probability_at(conn, "m", 5000) == 0.6  # latest known
    assert market_probability_at(conn, "m", 500) is None  # nothing yet
    conn.close()


def test_delayed_fill_uses_later_market_state_not_signal_state(conn):
    # The market moves 0.5 -> 0.7 between signal (t=1000) and execution (t=2000).
    _snap(conn, "m", 1000, 0.5)
    _snap(conn, "m", 2000, 0.7)

    exe = simulate_execution(
        conn, market_id="m", side="YES", stake=10.0, signal_ts_ns=1000,
        liquidity=200.0, latency_ns=1000,  # execution at t=2000
    )
    assert exe is not None
    assert exe.execution_ts_ns == 2000
    assert exe.p_market_signal == 0.5      # price when we decided
    assert exe.p_market_exec == 0.7        # price we ACTUALLY filled against (adverse move)
    assert exe.fill.prob_before == pytest.approx(0.7)  # pool built from the later state, not 0.5


def test_zero_latency_fills_at_signal_price(conn):
    _snap(conn, "m", 1000, 0.5)
    _snap(conn, "m", 2000, 0.7)
    exe = simulate_execution(
        conn, market_id="m", side="YES", stake=10.0, signal_ts_ns=1000,
        liquidity=200.0, latency_ns=0,
    )
    assert exe.execution_ts_ns == 1000
    assert exe.p_market_exec == 0.5  # no delay -> signal-time price


def test_no_price_by_execution_time_returns_none(conn):
    _snap(conn, "m", 5000, 0.5)  # first price only at t=5000
    exe = simulate_execution(
        conn, market_id="m", side="YES", stake=10.0, signal_ts_ns=1000,
        liquidity=200.0, latency_ns=0,  # execution at 1000, before any snapshot
    )
    assert exe is None


def test_fee_increases_total_cost_and_effective_price(conn):
    _snap(conn, "m", 1000, 0.5)
    no_fee = simulate_execution(
        conn, market_id="m", side="YES", stake=100.0, signal_ts_ns=1000,
        liquidity=1000.0, latency_ns=0, fee_fraction=0.0,
    )
    with_fee = simulate_execution(
        conn, market_id="m", side="YES", stake=100.0, signal_ts_ns=1000,
        liquidity=1000.0, latency_ns=0, fee_fraction=0.02,
    )
    assert with_fee.fee == pytest.approx(2.0)  # 2% of 100
    assert with_fee.total_cost == pytest.approx(102.0)
    assert no_fee.total_cost == pytest.approx(100.0)
    # Same shares (fee doesn't change the fill), but higher effective price with the fee.
    assert with_fee.fill.shares == pytest.approx(no_fee.fill.shares)
    assert with_fee.effective_price > no_fee.effective_price


def test_invalid_inputs_raise(conn):
    _snap(conn, "m", 1000, 0.5)
    with pytest.raises(ValueError):
        simulate_execution(conn, market_id="m", side="YES", stake=0.0, signal_ts_ns=1000, liquidity=100.0)
    with pytest.raises(ValueError):
        simulate_execution(conn, market_id="m", side="YES", stake=10.0, signal_ts_ns=1000, liquidity=100.0, latency_ns=-1)
