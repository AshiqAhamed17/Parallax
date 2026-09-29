"""Manifold REST adapter (Task LD.1).

The Rust collector streams Manifold's live *bet* WebSocket, but it never calls the REST side — so
market metadata (question text, close time, category, resolution) and per-market bet history are
never backfilled. This adapter fills that gap from Manifold's public, unauthenticated REST API
(`api.manifold.markets/v0`, no key needed — see `.env.example`). It only *reads*; it never trades.

Used by the live-data enrichment pipeline (Phase LD) to:
  * fetch metadata + current price for curated open markets (`get_market`),
  * reconstruct a price/feature history from each market's bets (`get_bets`),
  * pull a resolved-market corpus to train the calibration model (`iter_resolved_markets`).

Everything is parsed defensively with `.get()` (Manifold returns dozens of fields we don't use), so
one unexpected row can't abort a batch.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import httpx

API_BASE = "https://api.manifold.markets/v0"
_TIMEOUT = httpx.Timeout(20.0)

# Manifold tags markets with `groupSlugs`; map the ones we care about onto the dashboard's category
# chips. First match wins, so order matters (specific sports before the generic "sports" bucket).
_CATEGORY_BY_SLUG: tuple[tuple[str, str], ...] = (
    ("f1", "F1"),
    ("formula-1", "F1"),
    ("nba", "NBA"),
    ("basketball", "NBA"),
    ("tennis", "Tennis"),
    ("premier-league", "Football"),
    ("soccer", "Football"),
    ("football", "Football"),
    ("bitcoin", "Crypto"),
    ("ethereum", "Crypto"),
    ("crypto", "Crypto"),
    ("ai", "Tech"),
    ("artificial-intelligence", "Tech"),
    ("agi", "Tech"),
    ("technology", "Tech"),
    ("us-politics", "Politics"),
    ("politics", "Politics"),
    ("elections", "Politics"),
    ("economics", "Macro"),
    ("inflation", "Macro"),
    ("business", "Macro"),
    ("finance", "Macro"),
)


def category_for(group_slugs: list[str] | None) -> str | None:
    """Best-effort dashboard category from a market's `groupSlugs` (None if nothing matches)."""
    if not group_slugs:
        return None
    lowered = [s.lower() for s in group_slugs if isinstance(s, str)]
    for needle, category in _CATEGORY_BY_SLUG:
        if any(needle in slug for slug in lowered):
            return category
    return None


@dataclass(frozen=True)
class ManifoldMarket:
    """The subset of a Manifold market we persist / train on."""

    market_id: str
    question_text: str
    probability: float
    close_time_ms: int | None
    is_resolved: bool
    # 1 if resolved YES, 0 if resolved NO, None if unresolved or resolved to a non-binary outcome.
    resolved_outcome: int | None
    category: str | None
    volume: float | None
    liquidity: float | None


@dataclass(frozen=True)
class ManifoldBet:
    """A single bet, ordered oldest→newest by the caller. `prob_after` drives the price series."""

    created_time_ms: int
    prob_before: float
    prob_after: float
    amount: float
    shares: float
    is_limit_order: bool


def _resolved_outcome(raw: dict[str, Any]) -> int | None:
    if not raw.get("isResolved"):
        return None
    res = raw.get("resolution")
    if res == "YES":
        return 1
    if res == "NO":
        return 0
    # MKT / CANCEL / multi-choice resolutions aren't a binary label we can train on.
    return None


def _market_from_raw(raw: dict[str, Any]) -> ManifoldMarket | None:
    """Normalize a raw Manifold market dict. Returns None for anything that isn't a usable binary
    market with a probability (multi-choice, numeric, or malformed rows are skipped)."""
    market_id = raw.get("id")
    question = raw.get("question")
    prob = raw.get("probability")
    if not isinstance(market_id, str) or not isinstance(question, str):
        return None
    if raw.get("outcomeType") != "BINARY" or not isinstance(prob, (int, float)):
        return None
    close_ms = raw.get("closeTime")
    vol = raw.get("volume")
    liq = raw.get("totalLiquidity")
    return ManifoldMarket(
        market_id=market_id,
        question_text=question.strip(),
        probability=max(0.0, min(1.0, float(prob))),
        close_time_ms=int(close_ms) if isinstance(close_ms, (int, float)) else None,
        is_resolved=bool(raw.get("isResolved")),
        resolved_outcome=_resolved_outcome(raw),
        category=category_for(raw.get("groupSlugs")),
        volume=float(vol) if isinstance(vol, (int, float)) else None,
        liquidity=float(liq) if isinstance(liq, (int, float)) else None,
    )


def get_market(market_id: str, *, client: httpx.Client | None = None) -> ManifoldMarket | None:
    """Fetch a single market by id. Returns None if it isn't a usable binary market."""
    owned = client is None
    client = client or httpx.Client(timeout=_TIMEOUT)
    try:
        resp = client.get(f"{API_BASE}/market/{market_id}")
        resp.raise_for_status()
        return _market_from_raw(resp.json())
    finally:
        if owned:
            client.close()


def get_bets(
    market_id: str, *, limit: int = 1000, client: httpx.Client | None = None
) -> list[ManifoldBet]:
    """Fetch up to `limit` most-recent bets for a market, returned oldest→newest.

    Manifold returns bets newest-first; we reverse so a caller can fold them into a forward-in-time
    price/feature series. Limit orders (rows carrying `limitProb`) are flagged, not dropped.
    """
    owned = client is None
    client = client or httpx.Client(timeout=_TIMEOUT)
    try:
        resp = client.get(f"{API_BASE}/bets", params={"contractId": market_id, "limit": limit})
        resp.raise_for_status()
        rows = resp.json()
    finally:
        if owned:
            client.close()

    bets: list[ManifoldBet] = []
    for raw in rows if isinstance(rows, list) else []:
        created = raw.get("createdTime")
        p_before = raw.get("probBefore")
        p_after = raw.get("probAfter")
        if not isinstance(created, (int, float)):
            continue
        if not isinstance(p_before, (int, float)) or not isinstance(p_after, (int, float)):
            continue
        bets.append(
            ManifoldBet(
                created_time_ms=int(created),
                prob_before=float(p_before),
                prob_after=float(p_after),
                amount=float(raw.get("amount") or 0.0),
                shares=float(raw.get("shares") or 0.0),
                is_limit_order=raw.get("limitProb") is not None,
            )
        )
    bets.sort(key=lambda b: b.created_time_ms)
    return bets


def search_markets(
    term: str,
    *,
    limit: int = 20,
    filter: str = "open",
    sort: str = "liquidity",
    client: httpx.Client | None = None,
) -> list[ManifoldMarket]:
    """Search live binary markets (default: open, ranked by liquidity)."""
    owned = client is None
    client = client or httpx.Client(timeout=_TIMEOUT)
    try:
        resp = client.get(
            f"{API_BASE}/search-markets",
            params={
                "term": term,
                "limit": limit,
                "filter": filter,
                "sort": sort,
                "contractType": "BINARY",
            },
        )
        resp.raise_for_status()
        rows = resp.json()
    finally:
        if owned:
            client.close()
    out = []
    for raw in rows if isinstance(rows, list) else []:
        market = _market_from_raw(raw)
        if market is not None:
            out.append(market)
    return out


def iter_resolved_markets(
    terms: list[str],
    *,
    per_term: int = 60,
    client: httpx.Client | None = None,
) -> Iterator[ManifoldMarket]:
    """Yield resolved (binary) markets across several search terms, de-duplicated by id.

    Used to assemble the calibration model's training corpus — markets whose YES/NO outcome is
    known, so `resolved_outcome` gives a real label.
    """
    owned = client is None
    client = client or httpx.Client(timeout=_TIMEOUT)
    seen: set[str] = set()
    try:
        for term in terms:
            for market in search_markets(
                term, limit=per_term, filter="resolved", sort="liquidity", client=client
            ):
                if market.resolved_outcome is None or market.market_id in seen:
                    continue
                seen.add(market.market_id)
                yield market
    finally:
        if owned:
            client.close()


__all__ = [
    "API_BASE",
    "ManifoldBet",
    "ManifoldMarket",
    "category_for",
    "get_bets",
    "get_market",
    "iter_resolved_markets",
    "search_markets",
]
