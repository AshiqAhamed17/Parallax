"""FastAPI application for the public read-only dashboard API (Phase 13).

Serves the data the dashboard renders, reading the shared SQLite database the Rust collector and the
Python research layer write (`implementation.md` §5). It is strictly read-only: there are no write or
bet-placement endpoints, ever (constraint §2.1).

- Task 13.1: app scaffold + `/health`.
- Task 13.2: `GET /markets` and `GET /markets/{market_id}` — market metadata + latest probability
  state + latest model prediction.
- Task 13.3: `GET /arbitrage` — recent signals from both detectors (logical-constraint +
  cross-source divergence), newest first, paginated, optionally filtered by `type`.
- Task 13.4: `GET /benchmarks` and `GET /backtests` — the committed static Markdown reports from
  Phases 5/6 (latency) and Phases 11/12 (backtests) respectively.
- Task 13.5: TTL response caching + fixed-window rate limiting, added as HTTP middleware.

The app is built by `create_app(db_path)` so tests can point it at a temporary seeded database; the
top-level `api/main.py` entrypoint and `parallax_research.api.app` (default DB from `PARALLAX_DB`)
use the production database path.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from parallax_research.api.middleware import FixedWindowRateLimiter, TTLResponseCache
from parallax_research.api.models import (
    ArbitrageSignalOut,
    HealthResponse,
    MarketOut,
    ModelPredictionOut,
    PaginatedSignals,
    ReplayOut,
    ReplayPoint,
    ReportOut,
    SignalType,
)
from parallax_research.storage import ensure_schema

#: Default database path when none is supplied (overridable via the `PARALLAX_DB` env var).
DEFAULT_DB_PATH = "../data/parallax.db"

#: Repo root (…/Parallax), from which the committed `benchmarks/` and `reports/` dirs are served.
_REPO_ROOT = Path(__file__).resolve().parents[4]

#: Default response-cache TTL and rate-limit settings (all overridable via `create_app`).
DEFAULT_CACHE_TTL_SECS = 5.0
DEFAULT_RATE_LIMIT_MAX = 600
DEFAULT_RATE_LIMIT_WINDOW_SECS = 60.0

#: Default browser origins allowed to call the API (overridable via `PARALLAX_CORS_ORIGINS`).
DEFAULT_CORS_ORIGINS = ["http://localhost:3000"]


def _default_db_path() -> str:
    return os.environ.get("PARALLAX_DB", DEFAULT_DB_PATH)


def _default_cors_origins() -> list[str]:
    raw = os.environ.get("PARALLAX_CORS_ORIGINS")
    return [o.strip() for o in raw.split(",") if o.strip()] if raw else DEFAULT_CORS_ORIGINS


def _default_rate_limit_max() -> int:
    # Server-side rendering fans out several requests per page from one IP, so the limit is
    # generous by default and can be raised or disabled (0) via env for trusted-SSR deployments.
    raw = os.environ.get("PARALLAX_RATE_LIMIT_MAX")
    return int(raw) if raw is not None else DEFAULT_RATE_LIMIT_MAX


def _default_benchmarks_dir() -> Path:
    return Path(os.environ.get("PARALLAX_BENCHMARKS_DIR", str(_REPO_ROOT / "benchmarks")))


def _default_reports_dir() -> Path:
    return Path(os.environ.get("PARALLAX_REPORTS_DIR", str(_REPO_ROOT / "reports")))


def _read_reports(directory: Path, predicate: Callable[[str], bool]) -> list[ReportOut]:
    """Read every `*.md` file in `directory` matching `predicate`, sorted by name. Missing dir → []."""
    if not directory.is_dir():
        return []
    reports = []
    for path in sorted(directory.glob("*.md")):
        if predicate(path.name):
            reports.append(ReportOut(name=path.name, content=path.read_text()))
    return reports


def _is_backtest_report(name: str) -> bool:
    return "backtest" in name or "logical-constraint" in name


def get_conn(request: Request) -> Iterator[sqlite3.Connection]:
    """Per-request read connection to the app's configured database (`app.state.db_path`).

    Self-ensures the schema so queries don't error before the collector has created any tables.
    """
    # check_same_thread=False: FastAPI runs sync endpoints in a threadpool, so the connection
    # created here may be used on a different worker thread. Safe: each request gets its own
    # connection, created and closed within the request, never shared concurrently.
    conn = sqlite3.connect(request.app.state.db_path, check_same_thread=False)
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


def _recent_probs(conn: sqlite3.Connection, market_id: str, n: int = 24) -> list[float]:
    """Last `n` probabilities for a market, returned oldest→newest (for inline sparklines)."""
    rows = conn.execute(
        "SELECT probability FROM probability_snapshots WHERE market_id = ? "
        "ORDER BY ts_ns DESC LIMIT ?",
        (market_id, n),
    ).fetchall()
    return [float(r[0]) for r in reversed(rows)]


def _market_from_row(conn: sqlite3.Connection, row: sqlite3.Row) -> MarketOut:
    return MarketOut(
        market_id=row["market_id"],
        platform=row["platform"],
        question_text=row["question_text"],
        close_time=row["close_time"],
        category=row["category"],
        resolved_outcome=row["resolved_outcome"],
        probability=None if row["probability"] is None else float(row["probability"]),
        volume_24h=None if row["volume_24h"] is None else float(row["volume_24h"]),
        last_updated_ns=None if row["last_updated_ns"] is None else int(row["last_updated_ns"]),
        prediction=_latest_prediction(conn, row["market_id"]),
        recent=_recent_probs(conn, row["market_id"]),
    )


def _signal_from_row(row: sqlite3.Row) -> ArbitrageSignalOut:
    return ArbitrageSignalOut(
        id=int(row["id"]),
        type=row["type"],
        market_refs=json.loads(row["market_refs"]),
        edge=float(row["edge"]),
        detected_at=row["detected_at"],
        details=json.loads(row["details_json"]),
    )


# Each market joined to its single most-recent probability snapshot (LEFT JOIN so markets with no
# snapshot yet still appear, with null probability/last_updated_ns).
_MARKET_SELECT = """
SELECT m.market_id, m.platform, m.question_text, m.close_time, m.category, m.resolved_outcome,
       ps.probability AS probability, ps.volume_24h AS volume_24h, ps.ts_ns AS last_updated_ns
FROM markets m
LEFT JOIN probability_snapshots ps ON ps.id = (
    SELECT id FROM probability_snapshots
    WHERE market_id = m.market_id ORDER BY ts_ns DESC, id DESC LIMIT 1
)
"""


def create_app(
    db_path: str | Path | None = None,
    *,
    benchmarks_dir: str | Path | None = None,
    reports_dir: str | Path | None = None,
    cache_ttl_secs: float = DEFAULT_CACHE_TTL_SECS,
    rate_limit_max: int | None = None,
    rate_limit_window_secs: float = DEFAULT_RATE_LIMIT_WINDOW_SECS,
    cors_origins: list[str] | None = None,
    time_fn: Callable[[], float] = time.monotonic,
) -> FastAPI:
    """Build the FastAPI app.

    `db_path` defaults to `PARALLAX_DB`/`DEFAULT_DB_PATH`; `benchmarks_dir`/`reports_dir` default to
    the repo's committed dirs. Caching/rate-limiting are enabled by default; pass `cache_ttl_secs=0`
    or `rate_limit_max=0` to disable either. `time_fn` is injectable for deterministic tests.
    """
    resolved_db = str(db_path) if db_path is not None else _default_db_path()
    resolved_benchmarks = (
        Path(benchmarks_dir) if benchmarks_dir is not None else _default_benchmarks_dir()
    )
    resolved_reports = Path(reports_dir) if reports_dir is not None else _default_reports_dir()
    resolved_rate_limit = rate_limit_max if rate_limit_max is not None else _default_rate_limit_max()

    app = FastAPI(
        title="Parallax API",
        description="Read-only API for the Parallax dashboard. Observes markets; never trades.",
        version="0.1.0",
    )
    app.state.db_path = resolved_db

    # --- Task 13.5: rate limiting + response caching (inner) middleware ---------------------------
    # Added in this order so the rate limiter wraps the cache and is checked first (Starlette applies
    # the last-added middleware outermost).
    if cache_ttl_secs > 0:
        cache = TTLResponseCache(cache_ttl_secs, time_fn=time_fn)

        @app.middleware("http")
        async def cache_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
            if request.method != "GET":
                return await call_next(request)
            key = (request.url.path, request.url.query)
            cached = cache.get(key)
            if cached is not None:
                status, body, content_type = cached
                return Response(
                    content=body, status_code=status, media_type=content_type,
                    headers={"X-Cache": "HIT"},
                )
            response = await call_next(request)
            body = b"".join([chunk async for chunk in response.body_iterator])
            content_type = response.headers.get("content-type")
            cache.set(key, (response.status_code, body, content_type))
            return Response(
                content=body, status_code=response.status_code, media_type=content_type,
                headers={"X-Cache": "MISS"},
            )

    if resolved_rate_limit > 0:
        limiter = FixedWindowRateLimiter(resolved_rate_limit, rate_limit_window_secs, time_fn=time_fn)

        @app.middleware("http")
        async def rate_limit_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
            client_id = request.client.host if request.client else "unknown"
            if not limiter.allow(client_id):
                return JSONResponse(
                    {"detail": "rate limit exceeded"},
                    status_code=429,
                    headers={"Retry-After": str(int(rate_limit_window_secs))},
                )
            return await call_next(request)

    # CORS registered LAST so it is the OUTERMOST layer — it adds its headers after the cache
    # middleware reconstructs a response, otherwise those headers would be stripped.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins if cors_origins is not None else _default_cors_origins(),
        allow_methods=["GET", "OPTIONS"],
        allow_headers=["*"],
    )

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

    @app.get("/markets/{market_id}/replay", response_model=ReplayOut)
    def get_market_replay(market_id: str, conn: ConnDep) -> ReplayOut:
        exists = conn.execute(
            "SELECT 1 FROM markets WHERE market_id = ?", (market_id,)
        ).fetchone()
        if exists is None:
            raise HTTPException(status_code=404, detail=f"market {market_id!r} not found")
        rows = conn.execute(
            "SELECT ts_ns, probability FROM probability_snapshots "
            "WHERE market_id = ? ORDER BY ts_ns ASC",
            (market_id,),
        ).fetchall()
        return ReplayOut(
            market_id=market_id,
            points=[
                ReplayPoint(ts_ns=int(r["ts_ns"]), probability=float(r["probability"]))
                for r in rows
            ],
        )

    @app.get("/arbitrage", response_model=PaginatedSignals)
    def list_arbitrage_signals(
        conn: ConnDep,
        limit: Annotated[int, Query(ge=1, le=200)] = 50,
        offset: Annotated[int, Query(ge=0)] = 0,
        signal_type: Annotated[SignalType | None, Query(alias="type")] = None,
    ) -> PaginatedSignals:
        where, params = "", []
        if signal_type is not None:
            where = " WHERE type = ?"
            params.append(signal_type)

        total = conn.execute(
            "SELECT COUNT(*) FROM arbitrage_signals" + where, params
        ).fetchone()[0]
        rows = conn.execute(
            "SELECT id, type, market_refs, edge, detected_at, details_json "
            "FROM arbitrage_signals" + where
            + " ORDER BY detected_at DESC, id DESC LIMIT ? OFFSET ?",
            [*params, limit, offset],
        ).fetchall()
        return PaginatedSignals(
            items=[_signal_from_row(row) for row in rows],
            total=int(total),
            limit=limit,
            offset=offset,
        )

    @app.get("/benchmarks", response_model=list[ReportOut])
    def list_benchmarks() -> list[ReportOut]:
        # All committed latency/perf reports (Phases 5/6): v1/v2/v3 + profile + latency-report.
        return _read_reports(resolved_benchmarks, lambda _name: True)

    @app.get("/backtests", response_model=list[ReportOut])
    def list_backtests() -> list[ReportOut]:
        # Backtest reports (Phases 11/12); calibration and other reports are excluded by the filter.
        return _read_reports(resolved_reports, _is_backtest_report)

    return app


#: Module-level app for `uvicorn parallax_research.api.app:app` / the top-level `api/main.py` shim.
app = create_app()
