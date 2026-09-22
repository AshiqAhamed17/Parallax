"""Chronological replay loop (Task 11.1).

Streams the stored history — bets, probability/feature snapshots, model predictions, and the
cross-source (Polymarket) snapshots — for a time range in ONE strictly time-ordered sequence,
merged across all sources. This is the spine of the backtester: everything downstream (fill
simulation, cost/latency modeling, P&L) consumes events in the exact order they would have arrived
live, so nothing can accidentally "see the future" (the cardinal backtesting sin).

Design: each source is queried already sorted by its timestamp, then a **k-way merge**
(`heapq.merge`) interleaves them by a total order `(ts_ns, source_rank, row_id)` — streaming, so we
never materialize the whole history at once (except the small cross-source series, which stores its
timestamp as ISO text and is normalized + sorted in Python). Ties are broken deterministically by a
fixed per-source rank then row id, so a given DB always replays in exactly the same order.
"""

from __future__ import annotations

import heapq
import sqlite3
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)

# Deterministic tie-break when two events share a timestamp.
_SOURCE_RANK = {
    "bet": 0,
    "probability": 1,
    "feature": 2,
    "model_prediction": 3,
    "cross_source": 4,
}


@dataclass(frozen=True)
class ReplayEvent:
    """One event in the merged replay stream, with its timestamp normalized to epoch nanoseconds."""

    ts_ns: int
    source: str
    market_id: str
    row_id: int
    payload: dict[str, Any]


def _iso_to_ns(value: str) -> int | None:
    """ISO 8601 timestamp -> epoch nanoseconds (integer math, no float precision loss). None if
    unparseable."""
    try:
        dt = datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    delta = dt - _EPOCH
    return (delta.days * 86_400 + delta.seconds) * 1_000_000_000 + delta.microseconds * 1_000


def _sort_key(event: ReplayEvent) -> tuple[int, int, int]:
    return (event.ts_ns, _SOURCE_RANK[event.source], event.row_id)


def _stream_ns_table(
    conn: sqlite3.Connection,
    *,
    table: str,
    source: str,
    payload_cols: list[str],
    start_ns: int | None,
    end_ns: int | None,
) -> Iterator[ReplayEvent]:
    """Stream a table whose timestamp column is `ts_ns` (integer ns), sorted by (ts_ns, id)."""
    cols = ["id", "market_id", "ts_ns", *payload_cols]
    sql = f"SELECT {', '.join(cols)} FROM {table}"
    clauses, params = [], []
    if start_ns is not None:
        clauses.append("ts_ns >= ?")
        params.append(start_ns)
    if end_ns is not None:
        clauses.append("ts_ns <= ?")
        params.append(end_ns)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY ts_ns, id"

    for row in conn.execute(sql, params):
        payload = dict(zip(payload_cols, row[3:], strict=True))
        yield ReplayEvent(int(row[2]), source, str(row[1]), int(row[0]), payload)


def _stream_cross_source(
    conn: sqlite3.Connection, *, start_ns: int | None, end_ns: int | None
) -> Iterator[ReplayEvent]:
    """Stream `cross_source_snapshots` (ISO `polled_at`): normalize to ns and sort in Python.

    Materialized because the series is small (hourly polls) and its text timestamp needs parsing to
    guarantee a correct numeric order regardless of ISO formatting quirks.
    """
    events: list[ReplayEvent] = []
    for rid, mid, polled_at, cp in conn.execute(
        "SELECT id, market_id, polled_at, community_prediction FROM cross_source_snapshots"
    ):
        ns = _iso_to_ns(polled_at)
        if ns is None:
            continue
        if (start_ns is not None and ns < start_ns) or (end_ns is not None and ns > end_ns):
            continue
        events.append(
            ReplayEvent(
                ns, "cross_source", str(mid), int(rid),
                {"community_prediction": cp, "polled_at": polled_at},
            )
        )
    events.sort(key=_sort_key)
    return iter(events)


def replay(
    conn: sqlite3.Connection,
    *,
    start_ns: int | None = None,
    end_ns: int | None = None,
) -> Iterator[ReplayEvent]:
    """Yield every stored event in `[start_ns, end_ns]` (inclusive; None = unbounded) in strict
    chronological order across all sources.

    The output is non-decreasing in `ts_ns`; same-timestamp events are ordered deterministically by
    source then row id.
    """
    sources = [
        _stream_ns_table(
            conn, table="bets", source="bet",
            payload_cols=["prob_before", "prob_after", "amount", "shares", "is_limit_order"],
            start_ns=start_ns, end_ns=end_ns,
        ),
        _stream_ns_table(
            conn, table="probability_snapshots", source="probability",
            payload_cols=["probability", "volume_24h"], start_ns=start_ns, end_ns=end_ns,
        ),
        _stream_ns_table(
            conn, table="feature_snapshots", source="feature",
            payload_cols=["prob_velocity", "bet_arrival_rate", "realized_vol"],
            start_ns=start_ns, end_ns=end_ns,
        ),
        _stream_ns_table(
            conn, table="model_predictions", source="model_prediction",
            payload_cols=["p_model", "p_market", "edge", "ev"], start_ns=start_ns, end_ns=end_ns,
        ),
        _stream_cross_source(conn, start_ns=start_ns, end_ns=end_ns),
    ]
    yield from heapq.merge(*sources, key=_sort_key)
