"""P&L aggregation tests (Task 11.4): hand-computed settlement + report."""

import sqlite3

import pytest

from parallax_research.backtester import (
    SettledTrade,
    aggregate,
    settle,
    simulate_execution,
)
from parallax_research.storage import ensure_schema


def _trade(side, stake, shares, cost, outcome, theo=0.2, market_id="m"):
    return SettledTrade(
        market_id=market_id, side=side, stake=stake, shares=shares,
        cost=cost, outcome=outcome, theoretical_edge=theo,
    )


def test_settlement_win_and_loss_pnl():
    # YES bet, 200 shares bought for 100, resolves YES -> payout 200, pnl +100.
    win = _trade("YES", stake=100, shares=200, cost=100, outcome=1)
    assert win.won and win.payout == 200 and win.pnl == pytest.approx(100)
    # Same bet resolves NO -> payout 0, pnl -100.
    loss = _trade("YES", stake=100, shares=200, cost=100, outcome=0)
    assert not loss.won and loss.payout == 0 and loss.pnl == pytest.approx(-100)


def test_no_side_wins_when_market_resolves_no():
    t = _trade("NO", stake=50, shares=100, cost=50, outcome=0)
    assert t.won and t.payout == 100 and t.pnl == pytest.approx(50)
    t2 = _trade("NO", stake=50, shares=100, cost=50, outcome=1)
    assert not t2.won and t2.pnl == pytest.approx(-50)


def test_aggregate_known_pnl():
    # One winner (+100), one loser (-100) -> net 0, 50% hit rate.
    trades = [
        _trade("YES", 100, 200, 100, outcome=1, theo=0.2),
        _trade("YES", 100, 200, 100, outcome=0, theo=0.2),
    ]
    r = aggregate(trades)
    assert r.n_trades == 2
    assert r.n_wins == 1
    assert r.hit_rate == pytest.approx(0.5)
    assert r.total_stake == pytest.approx(200)
    assert r.total_cost == pytest.approx(200)
    assert r.total_payout == pytest.approx(200)
    assert r.realized_pnl == pytest.approx(0.0)
    assert r.roi == pytest.approx(0.0)
    assert r.realized_edge == pytest.approx(0.0)
    # theoretical: 0.2*100 + 0.2*100 = 40 -> 40/200 = 0.2 (model expected +0.2/unit; realized 0).
    assert r.theoretical_pnl == pytest.approx(40)
    assert r.theoretical_edge == pytest.approx(0.2)


def test_aggregate_all_winners_positive_pnl():
    trades = [
        _trade("YES", 100, 200, 100, outcome=1),
        _trade("NO", 100, 200, 100, outcome=0),
    ]
    r = aggregate(trades)
    assert r.hit_rate == 1.0
    assert r.realized_pnl == pytest.approx(200)  # each pays 200 for 100 cost
    assert r.roi == pytest.approx(1.0)


def test_aggregate_empty_raises():
    with pytest.raises(ValueError):
        aggregate([])


def test_to_markdown_contains_key_metrics():
    r = aggregate([_trade("YES", 100, 200, 100, outcome=1)])
    md = r.to_markdown(title="T", note="n", range_label="2026")
    assert "Hit rate" in md and "Realized P&L" in md and "Theoretical edge" in md
    assert "2026" in md


def test_settle_bridges_executed_fill():
    conn = sqlite3.connect(":memory:")
    ensure_schema(conn)
    conn.execute(
        "INSERT INTO probability_snapshots (market_id, ts_ns, probability) VALUES ('m', 1000, 0.5)"
    )
    conn.commit()
    exe = simulate_execution(
        conn, market_id="m", side="YES", stake=100.0, signal_ts_ns=1000,
        liquidity=1000.0, latency_ns=0,
    )
    settled = settle(exe, outcome=1, theoretical_edge=0.1)
    assert settled.market_id == "m"
    assert settled.side == "YES"
    assert settled.shares == pytest.approx(exe.fill.shares)
    assert settled.cost == pytest.approx(exe.total_cost)
    assert settled.won  # outcome=1, YES bet
    assert settled.pnl == pytest.approx(exe.fill.shares - exe.total_cost)
    conn.close()


def test_settle_rejects_bad_outcome():
    conn = sqlite3.connect(":memory:")
    ensure_schema(conn)
    conn.execute(
        "INSERT INTO probability_snapshots (market_id, ts_ns, probability) VALUES ('m', 1000, 0.5)"
    )
    conn.commit()
    exe = simulate_execution(
        conn, market_id="m", side="YES", stake=10.0, signal_ts_ns=1000, liquidity=100.0, latency_ns=0
    )
    with pytest.raises(ValueError):
        settle(exe, outcome=2, theoretical_edge=0.1)
    conn.close()
