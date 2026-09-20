"""Signal detectors: cross-source divergence (Phase 9) and logical-constraint arbitrage (Phase 12)."""

from parallax_research.arbitrage.cross_source_divergence import (
    DivergenceSignal,
    detect_divergences,
    detect_for_match,
)

__all__ = [
    "DivergenceSignal",
    "detect_divergences",
    "detect_for_match",
]
