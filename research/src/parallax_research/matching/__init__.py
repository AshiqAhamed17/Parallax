"""Market-matching layer: link Manifold markets to their second-source (Polymarket) equivalents."""

from parallax_research.matching.mapping_loader import (
    MappingEntry,
    MappingFile,
    load_manual_mappings,
    load_mapping_file,
)
from parallax_research.matching.repository import (
    MarketMatch,
    confirm,
    ensure_market_matches,
    find_match,
    get,
    insert_candidate,
    list_by_status,
    list_confirmed,
    reject,
)

__all__ = [
    "MappingEntry",
    "MappingFile",
    "MarketMatch",
    "confirm",
    "ensure_market_matches",
    "find_match",
    "get",
    "insert_candidate",
    "list_by_status",
    "list_confirmed",
    "load_manual_mappings",
    "load_mapping_file",
    "reject",
]
