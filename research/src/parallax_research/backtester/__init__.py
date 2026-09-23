"""Backtester (Phase 11): replay stored history as if live to validate strategies safely."""

from parallax_research.backtester.execution import (
    DEFAULT_EXECUTION_LATENCY_NS,
    ExecutedFill,
    market_probability_at,
    simulate_execution,
)
from parallax_research.backtester.fill import CpmmPool, Fill, simulate_fill
from parallax_research.backtester.pnl import (
    BacktestResult,
    SettledTrade,
    aggregate,
    settle,
)
from parallax_research.backtester.replay import ReplayEvent, replay

__all__ = [
    "DEFAULT_EXECUTION_LATENCY_NS",
    "BacktestResult",
    "CpmmPool",
    "ExecutedFill",
    "Fill",
    "ReplayEvent",
    "SettledTrade",
    "aggregate",
    "market_probability_at",
    "replay",
    "settle",
    "simulate_execution",
    "simulate_fill",
]
