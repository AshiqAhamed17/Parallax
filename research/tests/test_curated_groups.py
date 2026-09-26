"""Tests for the curated production correlated-market-groups config (Task 12.2).

These assert the hand-curated `config/correlated_market_groups.yaml` parses and validates against the
Task 12.1 schema, and that its documented constraints point at real, distinct markets. They do NOT
hit the network — liveness of the market ids is verified by hand at curation time (see
config/README.md), not in CI.
"""

from pathlib import Path

from parallax_research.arbitrage import load_constraint_groups

CONFIG = Path(__file__).parents[1] / "config" / "correlated_market_groups.yaml"


def test_curated_config_validates():
    cfg = load_constraint_groups(CONFIG)
    assert [g.id for g in cfg.groups] == [
        "btc-eoy-2026-thresholds",
        "agi-arrival-2027-deadlines",
        "vance-2028-nomination-presidency",
    ]


def test_every_constraint_references_existing_keys_and_is_documented():
    cfg = load_constraint_groups(CONFIG)
    for group in cfg.groups:
        keys = {m.key for m in group.markets}
        assert len(keys) == len(group.markets), f"{group.id} has duplicate keys"
        assert group.constraints, f"{group.id} has no constraints"
        for c in group.constraints:
            assert {c.lhs, c.rhs} <= keys
            assert c.lhs != c.rhs
            assert c.note, f"{group.id} constraint {c.lhs}{c.op}{c.rhs} lacks documented reasoning"


def test_market_ids_are_present_and_unique():
    cfg = load_constraint_groups(CONFIG)
    ids = [m.manifold_market_id for g in cfg.groups for m in g.markets]
    assert all(mid.strip() for mid in ids)
    assert len(ids) == len(set(ids)), "a market id is reused across the curated config"
