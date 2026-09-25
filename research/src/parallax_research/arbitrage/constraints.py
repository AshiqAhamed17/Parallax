"""Correlated-market-group constraint schema (Task 12.1).

The logical-constraint arbitrage centerpiece (doc 01) rests on *provable* relationships between
related Manifold markets — e.g. "P(win the general) ≤ P(win the primary)", because you can't win the
general without first winning the primary. This module defines the config schema for such groups and
their ordering constraints; the violation detector (Task 12.3) consumes it.

Schema (YAML), validated with pydantic:

    groups:
      - id: candidate-x-2028
        description: "You can't win the general without winning the primary."
        markets:
          - {key: primary, manifold_market_id: "mf-x-primary", label: "X wins primary"}
          - {key: general, manifold_market_id: "mf-x-general", label: "X wins general"}
        constraints:
          - {lhs: general, op: "<=", rhs: primary, note: "general implies primary"}

A constraint means `P(lhs) op P(rhs)` must hold; a live probability set that breaks it is a
mispricing. Constraints reference markets by their group-local `key`; validation enforces that those
keys exist, are unique, and that a constraint never compares a market to itself.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator


class CorrelatedMarket(BaseModel):
    """One market in a group, addressed by a group-local `key` in constraints."""

    model_config = ConfigDict(extra="forbid")

    key: str = Field(min_length=1)
    manifold_market_id: str = Field(min_length=1)
    label: str | None = None


class OrderingConstraint(BaseModel):
    """`P(lhs) op P(rhs)` must hold, where `lhs`/`rhs` are market keys and `op` is `<=` or `>=`."""

    model_config = ConfigDict(extra="forbid")

    lhs: str = Field(min_length=1)
    op: Literal["<=", ">="] = "<="
    rhs: str = Field(min_length=1)
    note: str | None = None


class CorrelatedMarketGroup(BaseModel):
    """A set of logically-linked markets plus the ordering constraints their prices must obey."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    markets: list[CorrelatedMarket] = Field(min_length=2)
    constraints: list[OrderingConstraint] = Field(min_length=1)

    @model_validator(mode="after")
    def _check_references(self) -> CorrelatedMarketGroup:
        keys = [m.key for m in self.markets]
        if len(keys) != len(set(keys)):
            raise ValueError(f"group {self.id!r} has duplicate market keys")
        keyset = set(keys)
        for c in self.constraints:
            if c.lhs == c.rhs:
                raise ValueError(f"group {self.id!r} constraint compares {c.lhs!r} to itself")
            missing = {c.lhs, c.rhs} - keyset
            if missing:
                raise ValueError(f"group {self.id!r} constraint references unknown key(s): {missing}")
        return self


class CorrelatedMarketGroupsConfig(BaseModel):
    """Top-level config: a list of correlated market groups."""

    model_config = ConfigDict(extra="forbid")

    groups: list[CorrelatedMarketGroup] = Field(min_length=1)


def load_constraint_groups(path: str | Path) -> CorrelatedMarketGroupsConfig:
    """Parse and validate a correlated-market-groups YAML file. Raises `pydantic.ValidationError`
    on any malformed config (unknown keys, self-referential/dangling constraints, too few markets)."""
    raw = yaml.safe_load(Path(path).read_text())
    return CorrelatedMarketGroupsConfig.model_validate(raw)
