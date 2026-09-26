"""Logical-constraint arbitrage detector tests (Task 12.3).

Hand-worked violating and non-violating examples over the pure evaluator, plus the DB-backed path
reading latest probabilities from `probability_snapshots`. In-memory SQLite, no network.
"""

import sqlite3

import pytest

from parallax_research.arbitrage import (
    DEFAULT_COST_PER_LEG,
    CorrelatedMarketGroup,
    CorrelatedMarketGroupsConfig,
    detect_for_group,
    detect_violations,
    evaluate_constraint,
    evaluate_group,
)
from parallax_research.storage import ensure_probability_snapshots

STAMP = "2026-09-26T12:00:00+00:00"


def _group_le() -> CorrelatedMarketGroup:
    """Two-market group with a single `P(high) <= P(low)` constraint (magnitude nesting)."""
    return CorrelatedMarketGroup.model_validate(
        {
            "id": "btc",
            "description": "higher threshold implies lower threshold",
            "markets": [
                {"key": "low", "manifold_market_id": "mf-low"},
                {"key": "high", "manifold_market_id": "mf-high"},
            ],
            "constraints": [{"lhs": "high", "op": "<=", "rhs": "low"}],
        }
    )


def _group_ge() -> CorrelatedMarketGroup:
    return CorrelatedMarketGroup.model_validate(
        {
            "id": "ge",
            "description": "lhs must be at least rhs",
            "markets": [
                {"key": "a", "manifold_market_id": "mf-a"},
                {"key": "b", "manifold_market_id": "mf-b"},
            ],
            "constraints": [{"lhs": "a", "op": ">=", "rhs": "b"}],
        }
    )


# ---- pure evaluation: hand-worked examples --------------------------------------------------------


def test_violating_le_is_flagged_and_actionable():
    group = _group_le()
    c = group.constraints[0]
    # P(high)=0.60 > P(low)=0.45 → breached by 0.15; cost = 2*0.02 = 0.04; net = 0.11.
    v = evaluate_constraint(group, c, 0.60, 0.45, detected_at=STAMP)
    assert v is not None
    assert v.gross_violation == pytest.approx(0.15)
    assert v.cost == pytest.approx(2 * DEFAULT_COST_PER_LEG)
    assert v.net_violation == pytest.approx(0.11)
    assert v.is_actionable
    assert (v.overpriced_key, v.underpriced_key) == ("high", "low")
    assert (v.lhs_market_id, v.rhs_market_id) == ("mf-high", "mf-low")


def test_non_violating_le_returns_none():
    group = _group_le()
    c = group.constraints[0]
    # P(high)=0.40 <= P(low)=0.45 → constraint holds, no violation.
    assert evaluate_constraint(group, c, 0.40, 0.45, detected_at=STAMP) is None


def test_breach_below_cost_is_reported_but_not_actionable():
    group = _group_le()
    c = group.constraints[0]
    # Breached by only 0.03; cost 0.04 → net -0.01: a real inconsistency costs won't clear.
    v = evaluate_constraint(group, c, 0.48, 0.45, detected_at=STAMP)
    assert v is not None
    assert v.gross_violation == pytest.approx(0.03)
    assert v.net_violation == pytest.approx(-0.01)
    assert not v.is_actionable


def test_ge_violation_direction():
    group = _group_ge()
    c = group.constraints[0]
    # P(a)=0.30 < P(b)=0.50 breaches `a >= b` by 0.20; rhs (b) is the overpriced leg.
    v = evaluate_constraint(group, c, 0.30, 0.50, detected_at=STAMP)
    assert v is not None
    assert v.gross_violation == pytest.approx(0.20)
    assert (v.overpriced_key, v.underpriced_key) == ("b", "a")


def test_ge_satisfied_returns_none():
    group = _group_ge()
    c = group.constraints[0]
    assert evaluate_constraint(group, c, 0.50, 0.30, detected_at=STAMP) is None


def test_cost_per_leg_override_changes_net():
    group = _group_le()
    c = group.constraints[0]
    v = evaluate_constraint(group, c, 0.60, 0.45, cost_per_leg=0.0, detected_at=STAMP)
    assert v is not None
    assert v.cost == 0.0
    assert v.net_violation == pytest.approx(0.15)


def test_evaluate_group_skips_missing_probs_and_flags_only_breaches():
    # A three-market chain: title <= final <= semi. Feed a violation on the first, satisfied second,
    # and leave one market's probability out entirely.
    group = CorrelatedMarketGroup.model_validate(
        {
            "id": "chain",
            "description": "title <= final <= semi",
            "markets": [
                {"key": "semi", "manifold_market_id": "mf-semi"},
                {"key": "final", "manifold_market_id": "mf-final"},
                {"key": "title", "manifold_market_id": "mf-title"},
            ],
            "constraints": [
                {"lhs": "title", "rhs": "final"},  # 0.5 > 0.4 → breached by 0.1
                {"lhs": "final", "rhs": "semi"},   # semi prob missing → skipped
            ],
        }
    )
    violations = evaluate_group(
        group, {"title": 0.5, "final": 0.4}, detected_at=STAMP
    )
    assert len(violations) == 1
    assert violations[0].lhs_key == "title"
    assert violations[0].gross_violation == pytest.approx(0.1)


# ---- DB-backed path ------------------------------------------------------------------------------


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    ensure_probability_snapshots(c)
    yield c
    c.close()


def _seed(conn, market_id, probability, ts_ns):
    conn.execute(
        "INSERT INTO probability_snapshots (market_id, ts_ns, probability) VALUES (?, ?, ?)",
        (market_id, ts_ns, probability),
    )
    conn.commit()


def test_detect_for_group_uses_latest_snapshot(conn):
    group = _group_le()
    # Older consistent snapshot, then a newer breaching one — detector must use the latest.
    _seed(conn, "mf-high", 0.30, 1_000)
    _seed(conn, "mf-low", 0.45, 1_000)
    _seed(conn, "mf-high", 0.60, 2_000)
    _seed(conn, "mf-low", 0.45, 2_000)
    violations = detect_for_group(conn, group, detected_at=STAMP)
    assert len(violations) == 1
    assert violations[0].p_lhs == pytest.approx(0.60)
    assert violations[0].net_violation == pytest.approx(0.11)


def test_detect_for_group_skips_market_without_snapshot(conn):
    group = _group_le()
    _seed(conn, "mf-high", 0.60, 1_000)  # mf-low never seeded
    assert detect_for_group(conn, group, detected_at=STAMP) == []


def test_detect_violations_across_config(conn):
    config = CorrelatedMarketGroupsConfig(groups=[_group_le(), _group_ge()])
    # Group 1 breached; group 2 satisfied.
    _seed(conn, "mf-high", 0.60, 1_000)
    _seed(conn, "mf-low", 0.45, 1_000)
    _seed(conn, "mf-a", 0.50, 1_000)
    _seed(conn, "mf-b", 0.30, 1_000)
    violations = detect_violations(conn, config, detected_at=STAMP)
    assert [v.group_id for v in violations] == ["btc"]
