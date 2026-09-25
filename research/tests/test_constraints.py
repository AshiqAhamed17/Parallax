"""Correlated-market-group constraint schema tests (Task 12.1)."""

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from parallax_research.arbitrage import (
    CorrelatedMarketGroupsConfig,
    load_constraint_groups,
)

FIXTURE = Path(__file__).parent / "fixtures" / "correlated_market_groups.yaml"


def _cfg(data: dict) -> CorrelatedMarketGroupsConfig:
    return CorrelatedMarketGroupsConfig.model_validate(data)


def test_loads_fixture():
    cfg = load_constraint_groups(FIXTURE)
    assert [g.id for g in cfg.groups] == ["candidate-x-2028", "team-a-tournament"]
    g0 = cfg.groups[0]
    assert {m.key for m in g0.markets} == {"primary", "general"}
    c = g0.constraints[0]
    assert (c.lhs, c.op, c.rhs) == ("general", "<=", "primary")  # op present, default too
    # Second group has two chained constraints and defaults op to "<=".
    assert all(c.op == "<=" for c in cfg.groups[1].constraints)


def _valid_group():
    return {
        "id": "g",
        "description": "d",
        "markets": [
            {"key": "a", "manifold_market_id": "mf-a"},
            {"key": "b", "manifold_market_id": "mf-b"},
        ],
        "constraints": [{"lhs": "a", "rhs": "b"}],
    }


def test_valid_minimal_group_parses():
    cfg = _cfg({"groups": [_valid_group()]})
    assert cfg.groups[0].constraints[0].op == "<="  # default


def test_constraint_referencing_unknown_key_rejected():
    g = _valid_group()
    g["constraints"] = [{"lhs": "a", "rhs": "ZZZ"}]  # ZZZ not a market key
    with pytest.raises(ValidationError):
        _cfg({"groups": [g]})


def test_self_referential_constraint_rejected():
    g = _valid_group()
    g["constraints"] = [{"lhs": "a", "rhs": "a"}]
    with pytest.raises(ValidationError):
        _cfg({"groups": [g]})


def test_duplicate_market_keys_rejected():
    g = _valid_group()
    g["markets"][1]["key"] = "a"  # duplicate key
    with pytest.raises(ValidationError):
        _cfg({"groups": [g]})


def test_too_few_markets_rejected():
    g = _valid_group()
    g["markets"] = g["markets"][:1]  # only one market
    with pytest.raises(ValidationError):
        _cfg({"groups": [g]})


def test_no_constraints_rejected():
    g = _valid_group()
    g["constraints"] = []
    with pytest.raises(ValidationError):
        _cfg({"groups": [g]})


def test_bad_op_rejected():
    g = _valid_group()
    g["constraints"] = [{"lhs": "a", "op": "==", "rhs": "b"}]  # unsupported op
    with pytest.raises(ValidationError):
        _cfg({"groups": [g]})


def test_unknown_field_rejected():
    g = _valid_group()
    g["surprise"] = True
    with pytest.raises(ValidationError):
        _cfg({"groups": [g]})


def test_malformed_yaml_file_rejected(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text(yaml.safe_dump({"groups": [{"id": "x"}]}))  # missing description/markets/constraints
    with pytest.raises(ValidationError):
        load_constraint_groups(bad)
