"""Cost modeling + latency-aware execution timing (Task 11.3).

A backtest that fills a signal instantly at the signal-time price is subtly cheating: in reality
there's a delay between deciding to bet and the order landing, during which the market moves. This
module executes a signal against the market state at **signal_time + latency**, not at signal_time —
so a delayed fill can suffer adverse movement, exactly as it would live. That's an anti-lookahead
guarantee: you can only trade on prices that existed by the time you could actually act.

The latency default is wired to the pipeline's own measured detect-latency (Phase 5/6 — see
`benchmarks/v3-results.md`); it's a floor and is configurable (real-world network latency to Manifold
would be larger).

Cost model: Manifold's CPMM bets carry no percentage trading fee — the real cost is the AMM
slippage already captured by `simulate_fill` (effective price vs. marginal). A configurable
`fee_fraction` (default 0) is still applied on top so the model can represent any fee/rebate a venue
imposes. This never places a real bet (constraint §2.1).
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from parallax_research.backtester.fill import CpmmPool, Fill, simulate_fill

#: Modeled signal->execution delay. Default = v3 paced end-to-end p50 (~94µs, benchmarks/v3-results.md):
#: the fastest the pipeline could detect-and-act. Configurable per run.
DEFAULT_EXECUTION_LATENCY_NS = 94_207


def market_probability_at(
    conn: sqlite3.Connection, market_id: str, at_ns: int
) -> float | None:
    """The most recent market probability known at time `at_ns` (latest snapshot with ts_ns <= at_ns).

    None if no snapshot exists yet — i.e. we'd have no price to trade against at that instant.
    """
    row = conn.execute(
        "SELECT probability FROM probability_snapshots "
        "WHERE market_id = ? AND ts_ns <= ? ORDER BY ts_ns DESC LIMIT 1",
        (market_id, at_ns),
    ).fetchone()
    return None if row is None else float(row[0])


@dataclass(frozen=True)
class ExecutedFill:
    """A fill executed after a latency delay, with the price that actually applied and total cost."""

    market_id: str
    side: str
    stake: float
    signal_ts_ns: int
    execution_ts_ns: int
    p_market_signal: float | None  # price when the signal fired (for adverse-move analysis)
    p_market_exec: float           # price we actually filled against (at execution time)
    fill: Fill                     # the CPMM fill at the execution price
    fee: float
    total_cost: float              # stake + fee
    effective_price: float         # total_cost / shares (includes fee)


def simulate_execution(
    conn: sqlite3.Connection,
    *,
    market_id: str,
    side: str,
    stake: float,
    signal_ts_ns: int,
    liquidity: float,
    p: float = 0.5,
    latency_ns: int = DEFAULT_EXECUTION_LATENCY_NS,
    fee_fraction: float = 0.0,
) -> ExecutedFill | None:
    """Execute a `stake`-mana `side` bet signalled at `signal_ts_ns`, filled `latency_ns` later.

    Looks up the market probability at `signal_ts_ns + latency_ns`, reconstructs the CPMM pool at
    that price (with the caller-supplied `liquidity`), simulates the fill, and applies the fee.
    Returns None if no price is available by execution time.
    """
    if stake <= 0:
        raise ValueError("stake must be positive")
    if latency_ns < 0:
        raise ValueError("latency_ns must be non-negative")

    execution_ts = signal_ts_ns + latency_ns
    p_exec = market_probability_at(conn, market_id, execution_ts)
    if p_exec is None:
        return None  # nothing to trade against yet

    pool = CpmmPool.from_probability(p_exec, liquidity=liquidity, p=p)
    fill = simulate_fill(pool, side, stake)

    fee = fee_fraction * stake
    total_cost = stake + fee
    return ExecutedFill(
        market_id=market_id,
        side=side,
        stake=stake,
        signal_ts_ns=signal_ts_ns,
        execution_ts_ns=execution_ts,
        p_market_signal=market_probability_at(conn, market_id, signal_ts_ns),
        p_market_exec=p_exec,
        fill=fill,
        fee=fee,
        total_cost=total_cost,
        effective_price=total_cost / fill.shares,
    )
