"""Polymarket adapter (Task 7.2).

Maps Polymarket's public Gamma API (`gamma-api.polymarket.com/markets`) into `NormalizedMarket`.
The Gamma API is open and unauthenticated; per Polymarket's ToS the meaningful data restrictions
apply to capital-markets firms / data distributors, not a non-commercial informational project — see
`implementation.md` §7-Polymarket. This adapter only *reads and normalizes*; it never trades
(constraint §2.1).

Only live, binary (2-outcome) markets are normalized — those are what the cross-source divergence
panel can compare against a Manifold YES probability. Multi-outcome markets, closed/inactive markets,
and rows with unparseable prices are skipped rather than raising, so a single bad row in a live poll
can't abort the whole batch.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
from pydantic import ValidationError

from parallax_research.schemas import NormalizedMarket

GAMMA_API_BASE = "https://gamma-api.polymarket.com"


def _parse_json_list(value: Any) -> list[Any] | None:
    """Gamma encodes `outcomes`/`outcomePrices` as JSON *strings* (e.g. '["Yes","No"]'). Decode
    defensively — return None on anything that isn't a JSON array."""
    if isinstance(value, list):
        return value
    if not isinstance(value, str):
        return None
    try:
        parsed = json.loads(value)
    except (json.JSONDecodeError, ValueError):
        return None
    return parsed if isinstance(parsed, list) else None


def _binary_probability(outcomes: list[Any], prices: list[Any]) -> float | None:
    """The reference probability for a 2-outcome market.

    For a Yes/No market that's the YES price; for any other 2-outcome market it's the price of the
    first outcome (`outcomes[0]`) — the market-matching layer (Phase 8) aligns semantics later.
    Returns None if the market isn't 2-outcome or the price won't parse.
    """
    if len(outcomes) != 2 or len(prices) != 2:
        return None
    idx = 0
    for i, name in enumerate(outcomes):
        if isinstance(name, str) and name.strip().lower() == "yes":
            idx = i
            break
    try:
        return float(prices[idx])
    except (TypeError, ValueError):
        return None


def _volume(raw: dict[str, Any]) -> float | None:
    for key in ("volumeNum", "volume"):
        v = raw.get(key)
        if v is None:
            continue
        try:
            return float(v)
        except (TypeError, ValueError):
            continue
    return None


def to_normalized_market(raw: dict[str, Any]) -> NormalizedMarket | None:
    """Map one Gamma market dict to a `NormalizedMarket`, or None if it can't/shouldn't be mapped.

    Skips markets that are closed or inactive (no live probability to compare), non-binary, or whose
    fields fail validation.
    """
    if raw.get("closed") is True or raw.get("active") is False:
        return None

    market_id = raw.get("conditionId") or raw.get("id")
    question = raw.get("question")
    if not market_id or not question:
        return None

    outcomes = _parse_json_list(raw.get("outcomes"))
    prices = _parse_json_list(raw.get("outcomePrices"))
    if outcomes is None or prices is None:
        return None

    probability = _binary_probability(outcomes, prices)
    if probability is None:
        return None

    try:
        return NormalizedMarket(
            platform="polymarket",
            market_id=str(market_id),
            question_text=str(question),
            probability=probability,
            volume=_volume(raw),
            close_time=raw.get("endDate"),  # ISO 8601 str or None; pydantic parses it
        )
    except ValidationError:
        # e.g. a price outside [0, 1] — skip the row rather than failing the whole poll.
        return None


def normalize_markets(raw_markets: list[dict[str, Any]]) -> list[NormalizedMarket]:
    """Normalize a batch of raw Gamma markets, dropping any that can't be mapped."""
    normalized = (to_normalized_market(m) for m in raw_markets)
    return [m for m in normalized if m is not None]


def fetch_markets(
    client: httpx.Client,
    *,
    limit: int = 100,
    order: str = "volumeNum",
    ascending: bool = False,
) -> list[NormalizedMarket]:
    """Fetch live markets from the Gamma API and return them as `NormalizedMarket`s.

    Requests only active, open markets, highest-volume first by default (the most liquid markets are
    the ones worth comparing). The caller owns the `httpx.Client` so polling cadence, timeouts, and
    retries live in the scheduler (Task 7.3) — this stays a thin, testable mapping over one request.
    """
    resp = client.get(
        f"{GAMMA_API_BASE}/markets",
        params={
            "limit": limit,
            "active": "true",
            "closed": "false",
            "order": order,
            "ascending": str(ascending).lower(),
        },
    )
    resp.raise_for_status()
    return normalize_markets(resp.json())
