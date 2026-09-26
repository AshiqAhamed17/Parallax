"""Logical-constraint arbitrage detector (Task 12.3).

The centerpiece (doc 01). A `CorrelatedMarketGroup` (Task 12.1/12.2) declares ordering constraints
that must hold *by construction* of the questions — e.g. `P(win presidency) <= P(nominated)` because
you can't win without being nominated. Given the current probabilities for a group, this module
computes, per constraint, how far it is breached and whether that breach survives estimated
transaction costs.

For a constraint `P(lhs) op P(rhs)`:

- `op == "<="` is breached when `P(lhs) > P(rhs)`; the **gross violation** is `P(lhs) - P(rhs)`.
- `op == ">="` is breached when `P(lhs) < P(rhs)`; the gross violation is `P(rhs) - P(lhs)`.

Capturing a breach needs a position on *both* markets (one leg per market), so the estimated cost is
`2 * cost_per_leg`. The **net violation** is `gross - 2*cost_per_leg`; only a positive net is
actionable — a tiny logical inconsistency that slippage would eat is real but not worth flagging.

**Honest framing (constraint §2.1):** these are Manifold *play-money* markets and Parallax never
trades. A net-positive violation is an informational signal about internal price *consistency*, not
executable free money. Unlike the cross-source divergence signal, though, this one rests on a
*provable* relationship, so a breach is a genuine mispricing rather than a difference of opinion.

- Task 12.3: detection (`evaluate_constraint`, `evaluate_group`, `detect_for_group`,
  `detect_violations`).
- Task 12.4 (later): persistence into `arbitrage_signals` + scheduler wiring + backtest.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime

from parallax_research.arbitrage.constraints import (
    CorrelatedMarketGroup,
    CorrelatedMarketGroupsConfig,
    OrderingConstraint,
)
from parallax_research.storage import ensure_arbitrage_signals

#: `arbitrage_signals.type` value for this detector (used by the Task 12.4 persistence layer).
SIGNAL_TYPE = "logical_constraint"

#: Estimated per-leg transaction cost. Manifold CPMM bets are fee-free, so this is a slippage
#: estimate; capturing a violation trades two legs, so the round-trip cost is `2 * cost_per_leg`.
DEFAULT_COST_PER_LEG = 0.02


@dataclass(frozen=True)
class ConstraintViolation:
    """A breached ordering constraint within a group, with its cost-adjusted size."""

    group_id: str
    lhs_key: str
    op: str
    rhs_key: str
    lhs_market_id: str
    rhs_market_id: str
    p_lhs: float
    p_rhs: float
    #: Amount the constraint is breached by, before costs (> 0 for a real breach).
    gross_violation: float
    #: Estimated total transaction cost across both legs (`2 * cost_per_leg`).
    cost: float
    #: `gross_violation - cost`; can be negative when costs swamp a marginal breach.
    net_violation: float
    detected_at: str

    @property
    def is_actionable(self) -> bool:
        """Whether the breach survives estimated transaction costs."""
        return self.net_violation > 0.0

    @property
    def overpriced_key(self) -> str:
        """The market that is too high relative to the other (the leg you'd sell)."""
        # `<=` breached → lhs is too high; `>=` breached → rhs is too high.
        return self.lhs_key if self.op == "<=" else self.rhs_key

    @property
    def underpriced_key(self) -> str:
        """The market that is too low relative to the other (the leg you'd buy)."""
        return self.rhs_key if self.op == "<=" else self.lhs_key


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _gross_violation(op: str, p_lhs: float, p_rhs: float) -> float:
    """How far `P(lhs) op P(rhs)` is breached (0.0 if it holds)."""
    if op == "<=":
        return max(0.0, p_lhs - p_rhs)
    # op == ">="  (schema restricts `op` to these two)
    return max(0.0, p_rhs - p_lhs)


def evaluate_constraint(
    group: CorrelatedMarketGroup,
    constraint: OrderingConstraint,
    p_lhs: float,
    p_rhs: float,
    *,
    cost_per_leg: float = DEFAULT_COST_PER_LEG,
    detected_at: str | None = None,
) -> ConstraintViolation | None:
    """Evaluate one constraint against a pair of probabilities.

    Returns a `ConstraintViolation` if the constraint is breached (gross violation > 0), else None.
    The returned violation carries its net (cost-adjusted) size and `is_actionable` flag; a breach
    that costs more to capture than it's worth is still returned (gross > 0) but not actionable.
    """
    gross = _gross_violation(constraint.op, p_lhs, p_rhs)
    if gross <= 0.0:
        return None

    markets = {m.key: m.manifold_market_id for m in group.markets}
    cost = 2.0 * cost_per_leg
    return ConstraintViolation(
        group_id=group.id,
        lhs_key=constraint.lhs,
        op=constraint.op,
        rhs_key=constraint.rhs,
        lhs_market_id=markets[constraint.lhs],
        rhs_market_id=markets[constraint.rhs],
        p_lhs=p_lhs,
        p_rhs=p_rhs,
        gross_violation=gross,
        cost=cost,
        net_violation=gross - cost,
        detected_at=detected_at or _utc_now_iso(),
    )


def evaluate_group(
    group: CorrelatedMarketGroup,
    probabilities: Mapping[str, float | None],
    *,
    cost_per_leg: float = DEFAULT_COST_PER_LEG,
    detected_at: str | None = None,
) -> list[ConstraintViolation]:
    """Evaluate every constraint in `group` against a `{market key -> probability}` mapping.

    Constraints whose lhs or rhs probability is missing/None are skipped (nothing to compare).
    Returns one `ConstraintViolation` per breached constraint (gross > 0); satisfied constraints
    produce nothing. Filter the result by `is_actionable` for the cost-clearing subset.
    """
    stamp = detected_at or _utc_now_iso()
    violations: list[ConstraintViolation] = []
    for constraint in group.constraints:
        p_lhs = probabilities.get(constraint.lhs)
        p_rhs = probabilities.get(constraint.rhs)
        if p_lhs is None or p_rhs is None:
            continue
        violation = evaluate_constraint(
            group,
            constraint,
            float(p_lhs),
            float(p_rhs),
            cost_per_leg=cost_per_leg,
            detected_at=stamp,
        )
        if violation is not None:
            violations.append(violation)
    return violations


def latest_probabilities(
    conn: sqlite3.Connection, group: CorrelatedMarketGroup
) -> dict[str, float | None]:
    """Latest Manifold probability per market key in the group (from `probability_snapshots`).

    A market with no snapshot yet maps to None so `evaluate_group` skips its constraints.
    """
    probs: dict[str, float | None] = {}
    for market in group.markets:
        row = conn.execute(
            "SELECT probability FROM probability_snapshots WHERE market_id = ? "
            "ORDER BY ts_ns DESC LIMIT 1",
            (market.manifold_market_id,),
        ).fetchone()
        probs[market.key] = None if row is None else float(row[0])
    return probs


def detect_for_group(
    conn: sqlite3.Connection,
    group: CorrelatedMarketGroup,
    *,
    cost_per_leg: float = DEFAULT_COST_PER_LEG,
    detected_at: str | None = None,
) -> list[ConstraintViolation]:
    """Read the group's current probabilities from storage and evaluate its constraints."""
    probs = latest_probabilities(conn, group)
    return evaluate_group(
        group, probs, cost_per_leg=cost_per_leg, detected_at=detected_at
    )


def detect_violations(
    conn: sqlite3.Connection,
    config: CorrelatedMarketGroupsConfig,
    *,
    cost_per_leg: float = DEFAULT_COST_PER_LEG,
    detected_at: str | None = None,
) -> list[ConstraintViolation]:
    """Evaluate every group in a curated config against current storage. Returns all breaches
    (actionable or not); the caller decides what to persist/surface."""
    stamp = detected_at or _utc_now_iso()
    violations: list[ConstraintViolation] = []
    for group in config.groups:
        violations.extend(
            detect_for_group(conn, group, cost_per_leg=cost_per_leg, detected_at=stamp)
        )
    return violations


def persist_violation(conn: sqlite3.Connection, violation: ConstraintViolation) -> int:
    """Write one logical-constraint violation into `arbitrage_signals` (Task 12.4). Returns row id.

    `type='logical_constraint'`; `edge` stores the signed *net* violation (size after costs);
    `market_refs` is the JSON `[lhs_market_id, rhs_market_id]` pair; `details_json` carries the
    constraint, both probabilities, gross/cost/net, the over/underpriced legs, and the honest
    "not tradeable arbitrage" note so a downstream reader (API/dashboard) can render it faithfully.
    """
    ensure_arbitrage_signals(conn)
    details = json.dumps(
        {
            "group_id": violation.group_id,
            "constraint": f"{violation.lhs_key} {violation.op} {violation.rhs_key}",
            "p_lhs": violation.p_lhs,
            "p_rhs": violation.p_rhs,
            "gross_violation": violation.gross_violation,
            "cost": violation.cost,
            "net_violation": violation.net_violation,
            "overpriced": violation.overpriced_key,
            "underpriced": violation.underpriced_key,
            "note": "logical-constraint violation, not tradeable arbitrage",
        }
    )
    cur = conn.execute(
        "INSERT INTO arbitrage_signals (type, market_refs, edge, detected_at, details_json) "
        "VALUES (?, ?, ?, ?, ?)",
        (
            SIGNAL_TYPE,
            json.dumps([violation.lhs_market_id, violation.rhs_market_id]),
            violation.net_violation,
            violation.detected_at,
            details,
        ),
    )
    conn.commit()
    return int(cur.lastrowid)


def detect_and_persist_violations(
    conn: sqlite3.Connection,
    config: CorrelatedMarketGroupsConfig,
    *,
    cost_per_leg: float = DEFAULT_COST_PER_LEG,
    detected_at: str | None = None,
    actionable_only: bool = True,
) -> int:
    """Detect constraint violations across a config and persist them. Returns the number written.

    By default only *actionable* breaches (net > 0 after costs) are persisted — a breach costs would
    eat is real but not worth surfacing. Pass `actionable_only=False` to record every breach.
    """
    violations = detect_violations(
        conn, config, cost_per_leg=cost_per_leg, detected_at=detected_at
    )
    written = 0
    for violation in violations:
        if actionable_only and not violation.is_actionable:
            continue
        persist_violation(conn, violation)
        written += 1
    return written
