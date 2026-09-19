"""Market-matching layer: link Manifold markets to their second-source (Polymarket) equivalents."""

from parallax_research.matching.repository import (
    MarketMatch,
    confirm,
    ensure_market_matches,
    get,
    insert_candidate,
    list_by_status,
    list_confirmed,
    reject,
)

__all__ = [
    "MarketMatch",
    "confirm",
    "ensure_market_matches",
    "get",
    "insert_candidate",
    "list_by_status",
    "list_confirmed",
    "reject",
]
