"""Signal detectors: cross-source divergence (Phase 9) and logical-constraint arbitrage (Phase 12)."""

from parallax_research.arbitrage.cross_source_divergence import (
    SIGNAL_TYPE,
    DivergenceSignal,
    detect_and_persist,
    detect_divergences,
    detect_for_match,
    persist_signal,
)

__all__ = [
    "SIGNAL_TYPE",
    "DivergenceSignal",
    "detect_and_persist",
    "detect_divergences",
    "detect_for_match",
    "persist_signal",
]
