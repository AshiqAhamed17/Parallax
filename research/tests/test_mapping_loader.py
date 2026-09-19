"""Tests for the manual market-mapping loader (Task 8.2)."""

import sqlite3
from pathlib import Path

import pytest
from pydantic import ValidationError

from parallax_research.matching import (
    ensure_market_matches,
    list_by_status,
    list_confirmed,
    load_manual_mappings,
    load_mapping_file,
)

FIXTURE = Path(__file__).parent / "fixtures" / "market_mappings.yaml"


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    ensure_market_matches(c)
    yield c
    c.close()


def test_load_mapping_file_parses_entries():
    mapping = load_mapping_file(FIXTURE)
    assert len(mapping.matches) == 2
    first = mapping.matches[0]
    assert first.manifold_market_id == "mf-us-recession-2027"
    assert first.polymarket_market_id.startswith("0x5db999")
    assert first.note is not None


def test_load_inserts_confirmed_matches(conn):
    n = load_manual_mappings(conn, FIXTURE)
    assert n == 2
    confirmed = list_confirmed(conn)
    assert len(confirmed) == 2
    assert all(m.status == "confirmed" for m in confirmed)
    assert all(m.platform == "polymarket" for m in confirmed)
    assert all(m.confidence is None for m in confirmed)  # hand-curated, no score
    # Nothing left pending.
    assert list_by_status(conn, "pending") == []
    ids = {m.manifold_market_id for m in confirmed}
    assert ids == {"mf-us-recession-2027", "mf-btc-100k"}


def test_reload_is_idempotent(conn):
    load_manual_mappings(conn, FIXTURE)
    second = load_manual_mappings(conn, FIXTURE)
    assert second == 0  # nothing new on the second run
    assert len(list_confirmed(conn)) == 2  # no duplicates


def test_malformed_missing_field_rejected(conn, tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("matches:\n  - manifold_market_id: \"only-one-side\"\n")
    with pytest.raises(ValidationError):
        load_manual_mappings(conn, bad)


def test_unknown_key_rejected(conn, tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "matches:\n"
        "  - manifold_market_id: \"m\"\n"
        "    polymarket_market_id: \"0xabc\"\n"
        "    surprise: \"unexpected\"\n"
    )
    with pytest.raises(ValidationError):
        load_manual_mappings(conn, bad)


def test_empty_id_rejected(conn, tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("matches:\n  - manifold_market_id: \"\"\n    polymarket_market_id: \"0xabc\"\n")
    with pytest.raises(ValidationError):
        load_manual_mappings(conn, bad)
