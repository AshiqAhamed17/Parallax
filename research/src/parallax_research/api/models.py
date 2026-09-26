"""Response models for the public API (Phase 13).

These are the read-only shapes the dashboard consumes. Everything is derived from the shared SQLite
storage contract (`implementation.md` §5); the API only reads — it never places a bet or mutates
market data (constraint §2.1).
"""

from __future__ import annotations

from pydantic import BaseModel


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
    resolved_outcome: int | None = None
    #: Latest market-implied probability from `probability_snapshots` (None if none collected yet).
    probability: float | None = None
    volume_24h: float | None = None
    #: `ts_ns` of the latest probability snapshot (None if none collected yet).
    last_updated_ns: int | None = None
    prediction: ModelPredictionOut | None = None
