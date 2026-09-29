"""Response models for the public API (Phase 13).

These are the read-only shapes the dashboard consumes. Everything is derived from the shared SQLite
storage contract (`implementation.md` §5); the API only reads — it never places a bet or mutates
market data (constraint §2.1).
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

#: The two detector families recorded in `arbitrage_signals.type`.
SignalType = Literal["logical_constraint", "cross_source_divergence"]


class HealthResponse(BaseModel):
    """Liveness probe payload."""

    status: str


class ModelPredictionOut(BaseModel):
    """Latest calibrated-model prediction for a market (from `model_predictions`)."""

    ts_ns: int
    p_model: float
    p_market: float
    edge: float
    ev: float


class MarketOut(BaseModel):
    """A tracked market: its metadata, latest probability state, and latest model prediction."""

    market_id: str
    platform: str
    question_text: str
    close_time: str
    category: str | None = None
    resolved_outcome: int | None = None
    #: Latest market-implied probability from `probability_snapshots` (None if none collected yet).
    probability: float | None = None
    volume_24h: float | None = None
    #: `ts_ns` of the latest probability snapshot (None if none collected yet).
    last_updated_ns: int | None = None
    prediction: ModelPredictionOut | None = None
    #: Recent probability series (oldest→newest, up to 24 points) for inline sparklines.
    recent: list[float] = []


class ArbitrageSignalOut(BaseModel):
    """One row from `arbitrage_signals`, from either detector (Phase 9 or Phase 12)."""

    id: int
    type: SignalType
    #: Market ids involved (parsed from the stored JSON array).
    market_refs: list[str]
    #: Signed edge/violation size the detector recorded.
    edge: float
    detected_at: str
    #: Detector-specific payload (parsed from the stored `details_json`).
    details: dict[str, Any]


class PaginatedSignals(BaseModel):
    """A page of arbitrage/divergence signals plus the total available (for the dashboard pager)."""

    items: list[ArbitrageSignalOut]
    total: int
    limit: int
    offset: int


class ReportOut(BaseModel):
    """One committed static report (Markdown), served for the dashboard to render."""

    #: File name, e.g. `latency-report.md` or `backtest-validation.md`.
    name: str
    #: Full Markdown content of the report.
    content: str


class ReplayPoint(BaseModel):
    """One point in a market's probability history (for the replay scrubber)."""

    ts_ns: int
    probability: float


class ReplayOut(BaseModel):
    """A market's full probability history, oldest-first, for time-scrubbed replay."""

    market_id: str
    points: list[ReplayPoint]
