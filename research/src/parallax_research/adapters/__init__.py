"""Source adapters: map each platform's API responses into `NormalizedMarket`."""

from parallax_research.adapters.polymarket import (
    GAMMA_API_BASE,
    fetch_markets,
    normalize_markets,
    to_normalized_market,
)

__all__ = [
    "GAMMA_API_BASE",
    "fetch_markets",
    "normalize_markets",
    "to_normalized_market",
]
