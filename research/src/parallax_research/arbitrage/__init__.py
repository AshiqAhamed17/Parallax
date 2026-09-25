"""Signal detectors: cross-source divergence (Phase 9) and logical-constraint arbitrage (Phase 12)."""

from parallax_research.arbitrage.constraints import (
    CorrelatedMarket,
    CorrelatedMarketGroup,
    CorrelatedMarketGroupsConfig,
    OrderingConstraint,
    load_constraint_groups,
)
from parallax_research.arbitrage.cross_source_divergence import (
    SIGNAL_TYPE,
    DivergenceSignal,
    detect_and_persist,
    detect_divergences,
    detect_for_match,
    persist_signal,
)
from parallax_research.arbitrage.scheduler import (
    run_detection_loop,
    run_detection_once,
)

__all__ = [
    "SIGNAL_TYPE",
    "CorrelatedMarket",
    "CorrelatedMarketGroup",
    "CorrelatedMarketGroupsConfig",
    "DivergenceSignal",
    "OrderingConstraint",
    "detect_and_persist",
    "detect_divergences",
    "detect_for_match",
    "load_constraint_groups",
    "persist_signal",
    "run_detection_loop",
    "run_detection_once",
]
