"""Tests for the Polymarket adapter (Task 7.2). No live network — fixture + mocked transport."""

import json
from pathlib import Path

import httpx

from parallax_research.adapters import (
    GAMMA_API_BASE,
    fetch_markets,
    normalize_markets,
    to_normalized_market,
)

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "polymarket_markets.json").read_text())


def _by_question(markets):
    return {m.question_text: m for m in markets}


def test_normalizes_live_binary_markets_and_skips_the_rest():
    markets = normalize_markets(FIXTURE)
    # 2 real Yes/No + 1 two-team + 1 perpetual Yes/No = 4 kept; closed + malformed dropped.
    assert len(markets) == 4
    by_q = _by_question(markets)
    assert "Already resolved market" not in by_q  # closed=true -> skipped
    assert "Malformed market with no prices" not in by_q  # empty prices -> skipped


def test_yes_no_market_maps_yes_price_and_fields():
    m = _by_question(normalize_markets(FIXTURE))["Will the U.S. invade Iran before 2027?"]
    assert m.platform == "polymarket"
    assert m.market_id == "0x5db999fad322cea2914535aae5517060c3f80ad6d8c0231cde2124a434d16846"
    assert m.probability == 0.155  # YES outcome price
    assert m.volume == 67023102.11519498
    assert m.close_time is not None and m.close_time.year == 2027


def test_two_outcome_non_yes_no_uses_first_outcome_price():
    m = _by_question(normalize_markets(FIXTURE))["Spread: Nagoya Grampus (-2.5)"]
    # outcomes ["Nagoya Grampus", "FC Tōkyō"] -> price of outcomes[0].
    assert m.probability == 0.015


def test_perpetual_market_has_no_close_time():
    m = _by_question(normalize_markets(FIXTURE))["Perpetual market with no close date"]
    assert m.close_time is None
    assert m.probability == 0.5
    assert m.volume == 1234.0


def test_closed_market_is_skipped():
    closed = next(r for r in FIXTURE if r["question"] == "Already resolved market")
    assert to_normalized_market(closed) is None


def test_malformed_prices_skipped():
    bad = next(r for r in FIXTURE if r["question"] == "Malformed market with no prices")
    assert to_normalized_market(bad) is None


def test_missing_question_or_id_skipped():
    assert to_normalized_market({"conditionId": "0xabc", "outcomes": "[\"Yes\",\"No\"]",
                                 "outcomePrices": "[\"0.5\",\"0.5\"]"}) is None  # no question
    assert to_normalized_market({"question": "q?", "outcomes": "[\"Yes\",\"No\"]",
                                 "outcomePrices": "[\"0.5\",\"0.5\"]"}) is None  # no id


def test_fetch_markets_uses_the_api_without_live_network():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(200, json=FIXTURE)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    markets = fetch_markets(client, limit=100)

    assert captured["url"].startswith(f"{GAMMA_API_BASE}/markets")
    assert "active=true" in captured["url"] and "closed=false" in captured["url"]
    assert len(markets) == 4
    assert all(m.platform == "polymarket" for m in markets)
