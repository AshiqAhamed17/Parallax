"""Live cross-source divergence wiring (Task LD.7).

Ties together three existing-but-unwired pieces so the dashboard's cross-source panel runs on real
data: (1) confirm the hand-curated Manifold↔Polymarket matches into `market_matches`, (2) poll the
matched Polymarket markets' live prices into `cross_source_snapshots`, (3) run the divergence
detector and persist any signal above the threshold.

The Polymarket adapter keys markets on `conditionId`, so a curated numeric Gamma id is resolved to
its conditionId (and its live price) here before matching.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import httpx
import yaml

from parallax_research.adapters.poller import ensure_cross_source_snapshots, poll_once
from parallax_research.adapters.polymarket import GAMMA_API_BASE, to_normalized_market
from parallax_research.arbitrage.cross_source_divergence import (
    detect_divergences,
    persist_signal,
)
from parallax_research.matching.repository import (
    STATUS_CONFIRMED,
    confirm,
    ensure_market_matches,
    find_match,
    insert_candidate,
)
from parallax_research.schemas import NormalizedMarket

# Surface divergences of ≥1pp. Well below the 5pp default because genuine same-event gaps between two
# efficient venues are small; each is persisted with an explicit "not tradeable arbitrage" note, so
# showing modest divergences is honest (informational), not an arbitrage claim.
_THRESHOLD = 0.01


def load_matches(path: str | Path) -> list[dict]:
    raw = yaml.safe_load(Path(path).read_text())
    return raw.get("matches", []) if isinstance(raw, dict) else []


def _fetch_polymarket(client: httpx.Client, gamma_id: str) -> NormalizedMarket | None:
    resp = client.get(f"{GAMMA_API_BASE}/markets", params={"id": gamma_id})
    resp.raise_for_status()
    rows = resp.json()
    for raw in rows if isinstance(rows, list) else []:
        normalized = to_normalized_market(raw)
        if normalized is not None:
            return normalized
    return None


def sync_cross_source(
    conn: sqlite3.Connection,
    matches: list[dict],
    *,
    client: httpx.Client,
    threshold: float = _THRESHOLD,
) -> dict[str, int]:
    """Confirm matches, poll Polymarket, and persist divergence signals. Returns counts.

    Idempotent: matches are de-duplicated via `find_match`, and prior divergence signals are cleared
    before re-detecting so a refresh replaces rather than piles up.
    """
    ensure_market_matches(conn)
    ensure_cross_source_snapshots(conn)

    normalized: list[NormalizedMarket] = []
    for match in matches:
        manifold_id = match["manifold_market_id"]
        try:
            poly = _fetch_polymarket(client, str(match["polymarket_market_id"]))
        except httpx.HTTPError:
            continue
        if poly is None:
            continue
        external_id = poly.market_id  # conditionId — what the detector keys on

        existing = find_match(conn, manifold_market_id=manifold_id, external_market_id=external_id)
        if existing is None:
            new_id = insert_candidate(
                conn, manifold_market_id=manifold_id, external_market_id=external_id
            )
            confirm(conn, new_id)
        elif existing.status != STATUS_CONFIRMED:
            confirm(conn, existing.id)
        normalized.append(poly)

    poll_once(conn, normalized)

    conn.execute("DELETE FROM arbitrage_signals WHERE type = 'cross_source_divergence'")
    signals = detect_divergences(conn, threshold=threshold)
    for signal in signals:
        persist_signal(conn, signal)
    conn.commit()
    return {"matches": len(normalized), "signals": len(signals)}


__all__ = ["load_matches", "sync_cross_source"]
