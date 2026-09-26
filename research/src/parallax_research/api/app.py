"""FastAPI application for the public read-only dashboard API (Phase 13).

Serves the data the dashboard renders, reading the shared SQLite database the Rust collector and the
Python research layer write (`implementation.md` §5). It is strictly read-only: there are no write or
bet-placement endpoints, ever (constraint §2.1).

- Task 13.1: app scaffold + `/health`.
- Task 13.2: `GET /markets` and `GET /markets/{market_id}` — market metadata + latest probability
  state + latest model prediction.

The app is built by `create_app(db_path)` so tests can point it at a temporary seeded database; the
top-level `api/main.py` entrypoint and `parallax_research.api.app` (default DB from `PARALLAX_DB`)
use the production database path.
"""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request

from parallax_research.api.models import HealthResponse, MarketOut, ModelPredictionOut
from parallax_research.storage import ensure_schema

#: Default database path when none is supplied (overridable via the `PARALLAX_DB` env var).
DEFAULT_DB_PATH = "../data/parallax.db"


def _default_db_path() -> str:
    return os.environ.get("PARALLAX_DB", DEFAULT_DB_PATH)


def get_conn(request: Request) -> Iterator[sqlite3.Connection]:
    """Per-request read connection to the app's configured database (`app.state.db_path`).

    Self-ensures the schema so queries don't error before the collector has created any tables.
    """
    conn = sqlite3.connect(request.app.state.db_path)
    conn.row_factory = sqlite3.Row
    ensure_schema(conn)
    try:
        yield conn
    finally:
        conn.close()


#: Module-level dependency alias (must be module-level so FastAPI resolves it under
#: `from __future__ import annotations`, where a local closure alias would not resolve).
ConnDep = Annotated[sqlite3.Connection, Depends(get_conn)]


def _latest_prediction(conn: sqlite3.Connection, market_id: str) -> ModelPredictionOut | None:
    row = conn.execute(
        "SELECT ts_ns, p_model, p_market, edge, ev FROM model_predictions "
        "WHERE market_id = ? ORDER BY ts_ns DESC, id DESC LIMIT 1",
        (market_id,),
    ).fetchone()
    if row is None:
        return None
    return ModelPredictionOut(
        ts_ns=int(row["ts_ns"]),
        p_model=float(row["p_model"]),
        p_market=float(row["p_market"]),
        edge=float(row["edge"]),
        ev=float(row["ev"]),
    )


def _market_from_row(conn: sqlite3.Connection, row: sqlite3.Row) -> MarketOut:
    return MarketOut(
        market_id=row["market_id"],
        platform=row["platform"],
        question_text=row["question_text"],
        close_time=row["close_time"],
        resolved_outcome=row["resolved_outcome"],
        probability=None if row["probability"] is None else float(row["probability"]),
        volume_24h=None if row["volume_24h"] is None else float(row["volume_24h"]),
        last_updated_ns=None if row["last_updated_ns"] is None else int(row["last_updated_ns"]),
        prediction=_latest_prediction(conn, row["market_id"]),
    )


# Each market joined to its single most-recent probability snapshot (LEFT JOIN so markets with no
# snapshot yet still appear, with null probability/last_updated_ns).
_MARKET_SELECT = """
SELECT m.market_id, m.platform, m.question_text, m.close_time, m.resolved_outcome,
       ps.probability AS probability, ps.volume_24h AS volume_24h, ps.ts_ns AS last_updated_ns
FROM markets m
LEFT JOIN probability_snapshots ps ON ps.id = (
    SELECT id FROM probability_snapshots
    WHERE market_id = m.market_id ORDER BY ts_ns DESC, id DESC LIMIT 1
)
"""


def create_app(db_path: str | Path | None = None) -> FastAPI:
    """Build the FastAPI app reading from `db_path` (defaults to `PARALLAX_DB`/`DEFAULT_DB_PATH`)."""
    resolved_db = str(db_path) if db_path is not None else _default_db_path()

    app = FastAPI(
        title="Parallax API",
        description="Read-only API for the Parallax dashboard. Observes markets; never trades.",
        version="0.1.0",
    )
    app.state.db_path = resolved_db

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(status="ok")

    @app.get("/markets", response_model=list[MarketOut])
    def list_markets(conn: ConnDep) -> list[MarketOut]:
        rows = conn.execute(
            _MARKET_SELECT
            + " ORDER BY (last_updated_ns IS NULL), last_updated_ns DESC, m.market_id"
        ).fetchall()
        return [_market_from_row(conn, row) for row in rows]

    @app.get("/markets/{market_id}", response_model=MarketOut)
    def get_market(market_id: str, conn: ConnDep) -> MarketOut:
        row = conn.execute(
            _MARKET_SELECT + " WHERE m.market_id = ?", (market_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail=f"market {market_id!r} not found")
        return _market_from_row(conn, row)

    return app


#: Module-level app for `uvicorn parallax_research.api.app:app` / the top-level `api/main.py` shim.
app = create_app()
