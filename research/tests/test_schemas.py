"""Tests for the shared NormalizedMarket schema (Task 7.1)."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from parallax_research.schemas import NormalizedMarket


def test_round_trip_full_record():
    market = NormalizedMarket(
        platform="manifold",
        market_id="abc123",
        question_text="Will it rain tomorrow?",
        probability=0.63,
        volume=1250.0,
        close_time=datetime(2026, 1, 1, tzinfo=UTC),
    )
    # dump -> reload must reproduce an identical model (JSON mode exercises datetime serialization).
    dumped = market.model_dump(mode="json")
    assert NormalizedMarket.model_validate(dumped) == market


def test_round_trip_minimal_record():
    # volume and close_time may be absent (e.g. a perpetual market) — both default to None.
    market = NormalizedMarket(
        platform="polymarket",
        market_id="q-9999",
        question_text="Will X happen by 2030?",
        probability=0.5,
    )
    assert market.volume is None
    assert market.close_time is None
    assert NormalizedMarket.model_validate(market.model_dump()) == market


def test_probability_bounds_are_enforced():
    for bad in (-0.01, 1.01, 2.0):
        with pytest.raises(ValidationError):
            NormalizedMarket(
                platform="manifold", market_id="m", question_text="q?", probability=bad
            )


def test_unknown_platform_rejected():
    with pytest.raises(ValidationError):
        NormalizedMarket(
            platform="metaculus", market_id="m", question_text="q?", probability=0.5
        )


def test_empty_strings_rejected():
    with pytest.raises(ValidationError):
        NormalizedMarket(platform="manifold", market_id="", question_text="q?", probability=0.5)
    with pytest.raises(ValidationError):
        NormalizedMarket(platform="manifold", market_id="m", question_text="", probability=0.5)


def test_missing_required_field_rejected():
    with pytest.raises(ValidationError):
        NormalizedMarket(platform="manifold", market_id="m", question_text="q?")  # no probability


def test_negative_volume_rejected():
    with pytest.raises(ValidationError):
        NormalizedMarket(
            platform="manifold", market_id="m", question_text="q?", probability=0.5, volume=-1.0
        )


def test_extra_field_rejected():
    with pytest.raises(ValidationError):
        NormalizedMarket(
            platform="manifold",
            market_id="m",
            question_text="q?",
            probability=0.5,
            surprise="unexpected",
        )
