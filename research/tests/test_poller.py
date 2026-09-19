"""Tests for the Polymarket polling scheduler (Task 7.3). In-memory SQLite, mocked HTTP."""

import json
import sqlite3
from pathlib import Path

import httpx
import pytest

from parallax_research.adapters import (
    ensure_cross_source_snapshots,
    fetch_and_store,
    poll_once,
    run_poller,
)
from parallax_research.schemas import NormalizedMarket

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "polymarket_markets.json").read_text())


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    ensure_cross_source_snapshots(c)
    yield c
    c.close()


def _mock_client() -> httpx.Client:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=FIXTURE)

    return httpx.Client(transport=httpx.MockTransport(handler))


def _rows(conn):
    return conn.execute(
        "SELECT market_id, polled_at, community_prediction FROM cross_source_snapshots ORDER BY id"
    ).fetchall()


def test_ensure_schema_is_idempotent(conn):
    # Calling again must not error or drop data.
    ensure_cross_source_snapshots(conn)
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='cross_source_snapshots'"
    ).fetchall()
    assert tables == [("cross_source_snapshots",)]


def test_poll_once_writes_one_row_per_market(conn):
    markets = [
        NormalizedMarket(platform="polymarket", market_id="0xaaa", question_text="Q1?", probability=0.2),
        NormalizedMarket(platform="polymarket", market_id="0xbbb", question_text="Q2?", probability=0.8),
    ]
    n = poll_once(conn, markets, polled_at="2026-09-19T12:00:00+00:00")
    assert n == 2
    rows = _rows(conn)
    assert rows == [
        ("0xaaa", "2026-09-19T12:00:00+00:00", 0.2),
        ("0xbbb", "2026-09-19T12:00:00+00:00", 0.8),
    ]


def test_fetch_and_store_persists_normalized_markets(conn):
    with _mock_client() as client:
        n = fetch_and_store(conn, client, polled_at="2026-09-19T12:00:00+00:00")
    # The fixture normalizes to 4 live binary markets (closed + malformed skipped).
    assert n == 4
    rows = _rows(conn)
    assert len(rows) == 4
    # The Iran market's YES price landed as community_prediction.
    iran = [r for r in rows if r[0] == "0x5db999fad322cea2914535aae5517060c3f80ad6d8c0231cde2124a434d16846"]
    assert iran and iran[0][2] == 0.155
    assert all(r[1] == "2026-09-19T12:00:00+00:00" for r in rows)


def test_repeated_polls_accumulate_a_time_series(conn):
    with _mock_client() as client:
        fetch_and_store(conn, client, polled_at="2026-09-19T12:00:00+00:00")
        fetch_and_store(conn, client, polled_at="2026-09-19T13:00:00+00:00")
    rows = _rows(conn)
    assert len(rows) == 8  # 4 markets × 2 polls
    stamps = {r[1] for r in rows}
    assert stamps == {"2026-09-19T12:00:00+00:00", "2026-09-19T13:00:00+00:00"}


def test_run_poller_respects_max_polls(conn):
    with _mock_client() as client:
        polls = run_poller(conn, client, interval_secs=0, max_polls=3)
    assert polls == 3
    assert len(_rows(conn)) == 12  # 4 markets × 3 polls
