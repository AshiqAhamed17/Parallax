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
from parallax_research.arbitrage.logical_constraint import (
    DEFAULT_COST_PER_LEG,
    ConstraintViolation,
    detect_for_group,
    detect_violations,
    evaluate_constraint,
    evaluate_group,
    latest_probabilities,
)
from parallax_research.arbitrage.logical_constraint import (
    SIGNAL_TYPE as LOGICAL_CONSTRAINT_SIGNAL_TYPE,
)
from parallax_research.arbitrage.scheduler import (
    run_detection_loop,
    run_detection_once,
)

__all__ = [
    "DEFAULT_COST_PER_LEG",
    "LOGICAL_CONSTRAINT_SIGNAL_TYPE",
    "SIGNAL_TYPE",
    "ConstraintViolation",
    "CorrelatedMarket",
    "CorrelatedMarketGroup",
    "CorrelatedMarketGroupsConfig",
    "DivergenceSignal",
    "OrderingConstraint",
    "detect_and_persist",
    "detect_divergences",
    "detect_for_group",
    "detect_for_match",
    "detect_violations",
    "evaluate_constraint",
    "evaluate_group",
    "latest_probabilities",
    "load_constraint_groups",
    "persist_signal",
    "run_detection_loop",
    "run_detection_once",
]
