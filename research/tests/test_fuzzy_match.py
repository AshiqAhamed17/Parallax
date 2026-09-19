"""Tests for the fuzzy match candidate generator (Task 8.3). Deterministic fake encoder, no ML dep."""

import sqlite3
from datetime import UTC, datetime

import numpy as np
import pytest

from parallax_research.matching import (
    ensure_market_matches,
    generate_candidates,
    list_by_status,
    store_candidates,
)
from parallax_research.schemas import NormalizedMarket

# A fake encoder: each known question maps to a fixed 2-D unit vector, so cosine similarity is fully
# controlled. "trump" texts point along x, "rain" along y, "unrelated" is opposite x.
_VECTORS = {
    "Will Trump win the 2028 election?": [1.0, 0.0],
    "Trump wins 2028 presidential election?": [1.0, 0.0],
    "Will it rain in Seattle tomorrow?": [0.0, 1.0],
    "Seattle rainfall tomorrow?": [0.0, 1.0],
    "Will the Lakers win the title?": [-1.0, 0.0],
}


def fake_encoder(texts: list[str]) -> np.ndarray:
    return np.array([_VECTORS[t] for t in texts], dtype=float)


def _mkt(mid: str, text: str, close: datetime | None = None) -> NormalizedMarket:
    return NormalizedMarket(
        platform="manifold" if mid.startswith("mf") else "polymarket",
        market_id=mid,
        question_text=text,
        probability=0.5,
        close_time=close,
    )


def test_clear_matches_pair_up_and_non_match_excluded():
    manifold = [
        _mkt("mf-trump", "Will Trump win the 2028 election?"),
        _mkt("mf-rain", "Will it rain in Seattle tomorrow?"),
    ]
    polymarket = [
        _mkt("0xtrump", "Trump wins 2028 presidential election?"),
        _mkt("0xrain", "Seattle rainfall tomorrow?"),
        _mkt("0xlakers", "Will the Lakers win the title?"),
    ]
    cands = generate_candidates(manifold, polymarket, encoder=fake_encoder, threshold=0.6, top_k=3)

    pairs = {(c.manifold_market_id, c.polymarket_market_id) for c in cands}
    assert ("mf-trump", "0xtrump") in pairs
    assert ("mf-rain", "0xrain") in pairs
    # The Lakers market is orthogonal/opposite to both -> never a candidate.
    assert all(c.polymarket_market_id != "0xlakers" for c in cands)


def test_results_sorted_by_score_descending():
    manifold = [_mkt("mf-trump", "Will Trump win the 2028 election?")]
    polymarket = [
        _mkt("0xtrump", "Trump wins 2028 presidential election?"),
        _mkt("0xrain", "Seattle rainfall tomorrow?"),
    ]
    cands = generate_candidates(manifold, polymarket, encoder=fake_encoder, threshold=0.0, top_k=5)
    scores = [c.score for c in cands]
    assert scores == sorted(scores, reverse=True)
    assert cands[0].polymarket_market_id == "0xtrump"  # strongest text match first


def test_date_proximity_breaks_ties():
    base = datetime(2027, 1, 1, tzinfo=UTC)
    manifold = [_mkt("mf-trump", "Will Trump win the 2028 election?", close=base)]
    polymarket = [
        _mkt("0xnear", "Trump wins 2028 presidential election?", close=base),
        _mkt("0xfar", "Trump wins 2028 presidential election?",
             close=datetime(2027, 1, 25, tzinfo=UTC)),  # 24 days off
    ]
    cands = generate_candidates(
        manifold, polymarket, encoder=fake_encoder, threshold=0.0, top_k=5, max_date_gap_days=30.0
    )
    # Identical text similarity, so the nearer close date wins.
    assert cands[0].polymarket_market_id == "0xnear"
    assert cands[0].score > cands[1].score


def test_threshold_filters_out_weak_matches():
    manifold = [_mkt("mf-trump", "Will Trump win the 2028 election?")]
    polymarket = [_mkt("0xrain", "Seattle rainfall tomorrow?")]  # orthogonal -> text sim 0
    # With text_weight 0.8 and missing dates (factor 1.0): score = 0.8*0 + 0.2*1 = 0.2 < 0.6.
    assert generate_candidates(manifold, polymarket, encoder=fake_encoder, threshold=0.6) == []


def test_top_k_limits_per_manifold_market():
    manifold = [_mkt("mf-trump", "Will Trump win the 2028 election?")]
    polymarket = [
        _mkt("0xa", "Trump wins 2028 presidential election?"),
        _mkt("0xb", "Trump wins 2028 presidential election?"),
        _mkt("0xc", "Trump wins 2028 presidential election?"),
    ]
    cands = generate_candidates(manifold, polymarket, encoder=fake_encoder, threshold=0.0, top_k=2)
    assert len(cands) == 2


def test_empty_inputs_return_no_candidates():
    m = [_mkt("mf-trump", "Will Trump win the 2028 election?")]
    assert generate_candidates([], m, encoder=fake_encoder) == []
    assert generate_candidates(m, [], encoder=fake_encoder) == []


def test_store_candidates_persists_pending_and_is_idempotent():
    conn = sqlite3.connect(":memory:")
    ensure_market_matches(conn)
    manifold = [_mkt("mf-trump", "Will Trump win the 2028 election?")]
    polymarket = [_mkt("0xtrump", "Trump wins 2028 presidential election?")]
    cands = generate_candidates(manifold, polymarket, encoder=fake_encoder, threshold=0.6)
    assert len(cands) == 1

    n1 = store_candidates(conn, cands)
    assert n1 == 1
    pending = list_by_status(conn, "pending")
    assert len(pending) == 1
    assert pending[0].status == "pending"  # machine guesses are never auto-confirmed (§2.2)
    assert pending[0].confidence == pytest.approx(cands[0].score)

    n2 = store_candidates(conn, cands)  # re-run
    assert n2 == 0  # idempotent
    assert len(list_by_status(conn, "pending")) == 1
    conn.close()
