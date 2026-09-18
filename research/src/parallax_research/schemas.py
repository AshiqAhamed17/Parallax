"""Shared pydantic schemas for the Parallax research layer.

`NormalizedMarket` is the platform-agnostic shape every source (Manifold, Metaculus) is mapped into
before market-matching (Phase 8) and cross-source divergence detection (Phase 9). Keeping one
normalized shape means the matching and divergence code never has to know which platform a row came
from — see `implementation.md` §5 (the `markets` / `cross_source_snapshots` tables) and Phase 7.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Platform = Literal["manifold", "metaculus"]


class NormalizedMarket(BaseModel):
    """A single market/question from any source, normalized to a common shape.

    `probability` is whatever that platform reports as its point estimate: Manifold's market-implied
    (CPMM) probability, or Metaculus's community-predicted probability (constraint §2.6). `volume`
    and `close_time` are optional because not every source has them — Metaculus is a forecasting
    platform with no trading volume, and some Manifold markets have no close time
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
