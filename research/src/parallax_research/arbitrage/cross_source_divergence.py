"""Cross-source divergence detector (Phase 9).

For each **confirmed** Manifold↔Polymarket match, compare Manifold's latest market-implied
probability against Polymarket's latest market-implied probability and flag pairs whose gap exceeds a
threshold.

**Honest framing (constraint §2.2 / doc 01):** this is a *divergence signal*, NOT asserted tradeable
arbitrage. Both venues are tradeable, but exploiting a gap has real frictions — fees, latency,
geo-restrictions, and Manifold is *play money* while Polymarket is *real money* (not even the same
unit). We surface the disagreement as information; we never claim it's free money, and we never trade
(constraint §2.1). Only `confirmed` matches can produce a signal — enforced by reading through
`matching.list_confirmed`.

- Task 9.1: detection (`detect_for_match`, `detect_divergences`).
- Task 9.2: persistence into `arbitrage_signals` (`persist_signal`, `detect_and_persist`).
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime

from parallax_research.matching.repository import MarketMatch, list_confirmed
from parallax_research.storage import ensure_arbitrage_signals

#: `arbitrage_signals.type` value for this detector.
SIGNAL_TYPE = "cross_source_divergence"

#: Default flag threshold: a 5-percentage-point gap between the two venues.
DEFAULT_THRESHOLD = 0.05


@dataclass(frozen=True)
class DivergenceSignal:
    """A flagged disagreement between the two venues for one confirmed match."""

    manifold_market_id: str
    polymarket_market_id: str
    p_manifold: float
    p_polymarket: float
    #: Signed gap, `p_manifold - p_polymarket` (positive → Manifold is higher).
    edge: float
    detected_at: str

    @property
    def magnitude(self) -> float:
        """Absolute size of the disagreement (what the threshold is applied to)."""
        return abs(self.edge)

    @property
    def direction(self) -> str:
        return "manifold_higher" if self.edge > 0 else "polymarket_higher"


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _latest_manifold_probability(conn: sqlite3.Connection, market_id: str) -> float | None:
    """Manifold's most recent probability for `market_id` (from `probability_snapshots`)."""
    row = conn.execute(
        "SELECT probability FROM probability_snapshots WHERE market_id = ? "
        "ORDER BY ts_ns DESC LIMIT 1",
        (market_id,),
    ).fetchone()
    return None if row is None else float(row[0])


def _latest_polymarket_probability(conn: sqlite3.Connection, market_id: str) -> float | None:
    """Polymarket's most recent probability for `market_id` (from `cross_source_snapshots`)."""
    row = conn.execute(
        "SELECT community_prediction FROM cross_source_snapshots WHERE market_id = ? "
        "ORDER BY id DESC LIMIT 1",
        (market_id,),
    ).fetchone()
    return None if row is None else float(row[0])


def detect_for_match(
    conn: sqlite3.Connection,
    match: MarketMatch,
    *,
    threshold: float = DEFAULT_THRESHOLD,
    detected_at: str | None = None,
) -> DivergenceSignal | None:
    """Compare the two venues' latest probabilities for one match.

    Returns a `DivergenceSignal` if the absolute gap is >= `threshold`, else None. Also returns None
    if either venue has no probability yet (nothing to compare).
    """
    p_manifold = _latest_manifold_probability(conn, match.manifold_market_id)
    p_polymarket = _latest_polymarket_probability(conn, match.external_market_id)
    if p_manifold is None or p_polymarket is None:
        return None

    edge = p_manifold - p_polymarket
    if abs(edge) < threshold:
        return None

    return DivergenceSignal(
        manifold_market_id=match.manifold_market_id,
        polymarket_market_id=match.external_market_id,
        p_manifold=p_manifold,
        p_polymarket=p_polymarket,
        edge=edge,
        detected_at=detected_at or _utc_now_iso(),
    )


def detect_divergences(
    conn: sqlite3.Connection,
    *,
    threshold: float = DEFAULT_THRESHOLD,
    detected_at: str | None = None,
) -> list[DivergenceSignal]:
    """Run the detector across all **confirmed** matches. Never reads pending/rejected matches — it
    goes through `list_confirmed`, the §2.2 boundary."""
    stamp = detected_at or _utc_now_iso()
    signals = []
    for match in list_confirmed(conn):
        signal = detect_for_match(conn, match, threshold=threshold, detected_at=stamp)
        if signal is not None:
            signals.append(signal)
    return signals


def persist_signal(conn: sqlite3.Connection, signal: DivergenceSignal) -> int:
    """Write one divergence signal into `arbitrage_signals` (Task 9.2). Returns the new row id.

    `edge` stores the signed gap; `market_refs` is the JSON pair of market ids; `details_json`
    carries both probabilities, the magnitude/direction, and the honest "not tradeable arbitrage"
    note so a downstream reader (API/dashboard) can render it faithfully.
    """
    ensure_arbitrage_signals(conn)
    details = json.dumps(
        {
            "p_manifold": signal.p_manifold,
            "p_polymarket": signal.p_polymarket,
            "divergence": signal.magnitude,
            "direction": signal.direction,
            "note": "divergence signal, not tradeable arbitrage",
        }
    )
    cur = conn.execute(
        "INSERT INTO arbitrage_signals (type, market_refs, edge, detected_at, details_json) "
        "VALUES (?, ?, ?, ?, ?)",
        (
            SIGNAL_TYPE,
            json.dumps([signal.manifold_market_id, signal.polymarket_market_id]),
            signal.edge,
            signal.detected_at,
            details,
        ),
    )
    conn.commit()
    return int(cur.lastrowid)


def detect_and_persist(
    conn: sqlite3.Connection,
    *,
    threshold: float = DEFAULT_THRESHOLD,
    detected_at: str | None = None,
) -> int:
    """Detect divergences across confirmed matches and persist each. Returns the number written."""
    signals = detect_divergences(conn, threshold=threshold, detected_at=detected_at)
    for signal in signals:
        persist_signal(conn, signal)
    return len(signals)
