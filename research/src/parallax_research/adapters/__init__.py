"""Source adapters: map each platform's API responses into `NormalizedMarket`."""

from parallax_research.adapters.poller import (
    ensure_cross_source_snapshots,
    fetch_and_store,
    poll_once,
    run_poller,
)
from parallax_research.adapters.polymarket import (
    GAMMA_API_BASE,
    fetch_markets,
    normalize_markets,
    to_normalized_market,
)

__all__ = [
    "GAMMA_API_BASE",
    "ensure_cross_source_snapshots",
    "fetch_and_store",
    "fetch_markets",
    "normalize_markets",
    "poll_once",
    "run_poller",
    "to_normalized_market",
]
