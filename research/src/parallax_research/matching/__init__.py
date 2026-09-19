"""Market-matching layer: link Manifold markets to their second-source (Polymarket) equivalents."""

from parallax_research.matching.fuzzy_match import (
    Candidate,
    Encoder,
    SentenceTransformerEncoder,
    generate_candidates,
    store_candidates,
)
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
from parallax_research.matching.review import (
    ReviewSummary,
    review_pending,
)

__all__ = [
    "Candidate",
    "Encoder",
    "MappingEntry",
    "MappingFile",
    "MarketMatch",
    "ReviewSummary",
    "SentenceTransformerEncoder",
    "confirm",
    "ensure_market_matches",
    "find_match",
    "generate_candidates",
    "get",
    "insert_candidate",
    "list_by_status",
    "list_confirmed",
    "load_manual_mappings",
    "load_mapping_file",
    "reject",
    "review_pending",
    "store_candidates",
]
