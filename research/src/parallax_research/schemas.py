"""Shared pydantic schemas for the Parallax research layer.

`NormalizedMarket` is the platform-agnostic shape every source (Manifold, Polymarket) is mapped into
before market-matching (Phase 8) and cross-source divergence detection (Phase 9). Keeping one
normalized shape means the matching and divergence code never has to know which platform a row came
from — see `implementation.md` §5 (the `markets` / `cross_source_snapshots` tables) and Phase 7.

(The second source pivoted from Metaculus to Polymarket in Phase 7 — Metaculus's ToS forbids
AI/ML/algorithmic use and public redistribution of its data without written permission, and exposes
its community prediction on only ~50 questions; Polymarket's public data API is open, unauthenticated,
and its ToS restrictions target capital-markets firms / data distributors, not a non-commercial
informational project. See `implementation.md` §7-Polymarket and `docs/metaculus-tos-check.md`.)
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Platform = Literal["manifold", "polymarket"]


class NormalizedMarket(BaseModel):
    """A single market/question from any source, normalized to a common shape.

    `probability` is whatever that platform reports as its point estimate: Manifold's market-implied
    (CPMM) probability, or Polymarket's market-implied probability (its YES `outcomePrice`).
    `volume` and `close_time` are optional because not every market has them — a Polymarket market
    may have no close date (perpetual), and some Manifold markets have no close time
    (`Market.close_time` is nullable on the wire, see the Rust client).
    """

    # `extra="forbid"` so an unexpected field from a changed API surface is a loud validation error,
    # not a silently-dropped value; `frozen=True` because a normalized record is an immutable
    # snapshot once built.
    model_config = ConfigDict(extra="forbid", frozen=True)

    platform: Platform
    market_id: str = Field(min_length=1)
    question_text: str = Field(min_length=1)
    probability: float = Field(ge=0.0, le=1.0)
    volume: float | None = Field(default=None, ge=0.0)
    close_time: datetime | None = None
