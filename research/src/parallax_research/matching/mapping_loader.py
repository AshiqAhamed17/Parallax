"""Manual market-mapping loader (Task 8.2).

Reads a hand-curated YAML file of known-equivalent Manifold↔Polymarket questions and inserts each
as a **confirmed** match. Hand-curation is the trustworthy path to confirmed matches (the fuzzy
matcher in Task 8.3 only ever produces `pending` candidates); a human vouching for a pair in this
file is exactly the sign-off constraint §2.2 requires before a match can drive a divergence signal.

The loader is idempotent — re-running it skips pairs already present — so the YAML file can be
edited and re-applied safely.

Expected YAML shape:

    matches:
      - manifold_market_id: "abc123"
        polymarket_market_id: "0xdeadbeef..."
        note: "Both resolve: will <X> happen by 2027?"   # optional, human-only, not stored
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

from parallax_research.matching.repository import (
    confirm,
    ensure_market_matches,
    find_match,
    insert_candidate,
)

PLATFORM = "polymarket"


class MappingEntry(BaseModel):
    """One hand-curated Manifold↔Polymarket equivalence."""

    model_config = ConfigDict(extra="forbid")

    manifold_market_id: str = Field(min_length=1)
    polymarket_market_id: str = Field(min_length=1)
    # Free-form human documentation of *why* the two are equivalent. Not persisted (the
    # `market_matches` table has no note column) — it lives in the YAML for reviewers.
    note: str | None = None


class MappingFile(BaseModel):
    """The whole mapping file."""

    model_config = ConfigDict(extra="forbid")

    matches: list[MappingEntry]


def load_mapping_file(path: str | Path) -> MappingFile:
    """Parse and validate a mapping YAML file. Raises `pydantic.ValidationError` on a malformed
    file (missing fields, unknown keys, empty ids)."""
    raw = yaml.safe_load(Path(path).read_text())
    return MappingFile.model_validate(raw)


def load_manual_mappings(conn: sqlite3.Connection, path: str | Path) -> int:
    """Load the mapping file into `market_matches` as confirmed matches. Returns the number of
    **new** matches inserted (already-present pairs are skipped, making re-runs idempotent).
    """
    ensure_market_matches(conn)
    mapping = load_mapping_file(path)

    inserted = 0
    for entry in mapping.matches:
        existing = find_match(
            conn,
            manifold_market_id=entry.manifold_market_id,
            external_market_id=entry.polymarket_market_id,
            platform=PLATFORM,
        )
        if existing is not None:
            continue
        match_id = insert_candidate(
            conn,
            manifold_market_id=entry.manifold_market_id,
            external_market_id=entry.polymarket_market_id,
            platform=PLATFORM,
            confidence=None,  # hand-curated: no machine similarity score
        )
        confirm(conn, match_id)
        inserted += 1
    return inserted
