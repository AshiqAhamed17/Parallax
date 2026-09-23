"""P&L aggregation and reporting (Task 11.4).

Settles simulated bets against real outcomes and aggregates them into the numbers that say whether a
strategy actually worked: hit rate, total simulated P&L, ROI, and **realized vs. theoretical edge**
(what the model expected to make per unit staked vs. what it actually made). Renders to Markdown for
`reports/backtest-<range>.md`.

Settlement: a bet buys `shares` of one side at `cost` (stake + fee). Each share pays 1 if that side
resolves true. So `payout = shares if won else 0`, `pnl = payout − cost`. A YES bet wins when the
market resolves YES (outcome=1); a NO bet wins when it resolves NO (outcome=0).
"""

from __future__ import annotations

from dataclasses import dataclass

from parallax_research.backtester.execution import ExecutedFill
from parallax_research.backtester.fill import NO, YES


@dataclass(frozen=True)
class SettledTrade:
    """One simulated bet settled against the market's actual resolution."""

    market_id: str
    side: str
    stake: float
    shares: float
    cost: float           # total cost incl. fee
    outcome: int          # actual YES resolution (1 = YES, 0 = NO)
    theoretical_edge: float  # model's expected profit per unit stake at signal time (e.g. EV)

    @property
    def won(self) -> bool:
        return (self.side == YES and self.outcome == 1) or (self.side == NO and self.outcome == 0)

    @property
    def payout(self) -> float:
        return self.shares if self.won else 0.0

    @property
    def pnl(self) -> float:
        return self.payout - self.cost


def settle(executed: ExecutedFill, outcome: int, *, theoretical_edge: float) -> SettledTrade:
    """Settle an `ExecutedFill` (Task 11.3) against a resolved `outcome` (0/1)."""
    if outcome not in (0, 1):
        raise ValueError("outcome must be 0 or 1")
    return SettledTrade(
        market_id=executed.market_id,
        side=executed.side,
        stake=executed.stake,
        shares=executed.fill.shares,
        cost=executed.total_cost,
        outcome=outcome,
        theoretical_edge=theoretical_edge,
    )


@dataclass(frozen=True)
class BacktestResult:
    n_trades: int
    n_wins: int
    hit_rate: float
    total_stake: float
    total_cost: float
    total_payout: float
    realized_pnl: float       # total_payout - total_cost
    theoretical_pnl: float    # sum(theoretical_edge_i * stake_i) — what the model expected
    roi: float                # realized_pnl / total_cost
    realized_edge: float      # realized_pnl / total_stake (per unit staked)
    theoretical_edge: float   # theoretical_pnl / total_stake (stake-weighted expected)

    def to_markdown(self, *, title: str, note: str, range_label: str) -> str:
        out = [f"# {title}\n", f"> {note}\n", "## Run\n", f"- Range: {range_label}",
               f"- Trades: {self.n_trades}  (wins: {self.n_wins})\n", "## Results\n",
               "| Metric | Value |", "|---|---:|",
               f"| Hit rate | {self.hit_rate:.1%} |",
               f"| Total staked | {self.total_stake:.2f} |",
               f"| Total cost | {self.total_cost:.2f} |",
               f"| Total payout | {self.total_payout:.2f} |",
               f"| **Realized P&L** | **{self.realized_pnl:+.2f}** |",
               f"| Theoretical P&L (model-expected) | {self.theoretical_pnl:+.2f} |",
               f"| ROI (P&L / cost) | {self.roi:+.2%} |",
               f"| Realized edge (P&L / stake) | {self.realized_edge:+.4f} |",
               f"| Theoretical edge (expected / stake) | {self.theoretical_edge:+.4f} |", ""]
        return "\n".join(out)


def aggregate(trades: list[SettledTrade]) -> BacktestResult:
    """Aggregate settled trades into hit rate, P&L, ROI, and realized vs. theoretical edge."""
    if not trades:
        raise ValueError("cannot aggregate an empty set of trades")

    n = len(trades)
    n_wins = sum(1 for t in trades if t.won)
    total_stake = sum(t.stake for t in trades)
    total_cost = sum(t.cost for t in trades)
    total_payout = sum(t.payout for t in trades)
    realized_pnl = total_payout - total_cost
    theoretical_pnl = sum(t.theoretical_edge * t.stake for t in trades)

    return BacktestResult(
        n_trades=n,
        n_wins=n_wins,
        hit_rate=n_wins / n,
        total_stake=total_stake,
        total_cost=total_cost,
        total_payout=total_payout,
        realized_pnl=realized_pnl,
        theoretical_pnl=theoretical_pnl,
        roi=realized_pnl / total_cost if total_cost else 0.0,
        realized_edge=realized_pnl / total_stake if total_stake else 0.0,
        theoretical_edge=theoretical_pnl / total_stake if total_stake else 0.0,
    )
