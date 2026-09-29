"""Curated live-market registry (Task LD.2).

Manifold's global bet firehose is mostly random low-quality markets, so the public dashboard tracks
a *curated* set instead: the most-liquid open binary markets in a handful of topic buckets, plus the
specific markets the correlated-group ladders need. Every price we then show is real — we only
choose *which* real markets to watch.

Honest coverage note: Manifold has deep liquidity in politics / AI / crypto and thin liquidity in
sports (F1, football, tennis). The buckets reflect that reality rather than faking rich sports
coverage — a bucket simply yields fewer markets when the platform has fewer.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from parallax_research.adapters.manifold import (
    ManifoldMarket,
    get_market,
    search_markets,
)

# Fetched by topic slug (clean, on-topic) and ranked by liquidity; `category` is authoritative here
# (it labels the dashboard chip), overriding the adapter's slug-guess.
_BUCKETS: tuple[tuple[str, str, int], ...] = (
    # (topic_slug, category, count)
    ("us-politics", "Politics", 6),
    ("ai", "Tech", 4),
    ("technology-default", "Tech", 3),
    ("bitcoin", "Crypto", 3),
    ("ethereum", "Crypto", 2),
    ("finance", "Macro", 4),
    ("f1", "F1", 4),
    ("nba", "NBA", 4),
    ("soccer", "Football", 3),
    ("tennis", "Tennis", 2),
    ("culture-default", "Culture", 3),
)

# Specific markets the correlated-group ladders reference (config/correlated_market_groups.yaml).
# Pinned so `/groups` always has real data even if they drop out of the liquidity-ranked buckets.
_PINNED: tuple[tuple[str, str], ...] = (
    # BTC end-of-2026 thresholds
    ("26QhQQ6hsQ", "Crypto"),
    ("Ophn0RNnRL", "Crypto"),
    ("2q2qZNLRlE", "Crypto"),
    # AGI arrival deadlines
    ("ysAmD1AL7KSPxg0FAcQ3", "Tech"),
    ("1T9iu2LX27d6wbCrO181", "Tech"),
    ("nmBdKE7ODKOGMYaD7QVF", "Tech"),
    ("bMiXjmTvOXVkekHs8hqO", "Tech"),
    # JD Vance 2028
    ("ulm6rrplx5", "Politics"),
    ("wpdomi6nif", "Politics"),
)

# Skip obvious junk that liquidity ranking can still surface (meme/scam-token markets, etc.).
_MIN_LIQUIDITY = 100.0


@dataclass(frozen=True)
class RegistryEntry:
    """A curated market plus the category it should display under."""

    market: ManifoldMarket
    category: str


def resolve_registry(*, client: httpx.Client | None = None) -> list[RegistryEntry]:
    """Resolve the registry against the live API: top-N liquid open markets per bucket, plus the
    pinned group markets. De-duplicated by market id (first occurrence wins its category).

    Network failures on a single bucket are skipped rather than aborting the whole registry.
    """
    owned = client is None
    client = client or httpx.Client(timeout=20.0)
    entries: list[RegistryEntry] = []
    seen: set[str] = set()
    try:
        for topic, category, count in _BUCKETS:
            try:
                found = search_markets(
                    topic_slug=topic,
                    limit=count * 3,
                    filter="open",
                    sort="liquidity",
                    client=client,
                )
            except httpx.HTTPError:
                continue
            taken = 0
            for market in found:
                if taken >= count or market.market_id in seen:
                    continue
                if (market.liquidity or 0.0) < _MIN_LIQUIDITY:
                    continue
                seen.add(market.market_id)
                entries.append(RegistryEntry(market=market, category=category))
                taken += 1

        for market_id, category in _PINNED:
            if market_id in seen:
                continue
            try:
                market = get_market(market_id, client=client)
            except httpx.HTTPError:
                continue
            if market is None:
                continue
            seen.add(market_id)
            entries.append(RegistryEntry(market=market, category=category))
    finally:
        if owned:
            client.close()
    return entries


__all__ = ["RegistryEntry", "resolve_registry"]
