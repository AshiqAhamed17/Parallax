"""Arbitrage/divergence endpoint tests (Task 13.3). Seeded temp SQLite DB, FastAPI TestClient."""

import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from parallax_research.api import create_app
from parallax_research.storage import ensure_schema


def _insert_signal(conn, type_, refs, edge, detected_at, details):
    conn.execute(
        "INSERT INTO arbitrage_signals (type, market_refs, edge, detected_at, details_json) "
        "VALUES (?, ?, ?, ?, ?)",
        (type_, json.dumps(refs), edge, detected_at, json.dumps(details)),
    )


@pytest.fixture
def client(tmp_path):
    db = tmp_path / "parallax.db"
    conn = sqlite3.connect(db)
    ensure_schema(conn)
    # Three signals across both detectors, at increasing timestamps.
    _insert_signal(
        conn, "cross_source_divergence", ["mf-a", "0xa"], 0.20,
        "2026-09-20T10:00:00+00:00", {"note": "divergence signal, not tradeable arbitrage"},
    )
    _insert_signal(
        conn, "logical_constraint", ["mf-high", "mf-low"], 0.11,
        "2026-09-21T10:00:00+00:00", {"constraint": "high <= low", "overpriced": "high"},
    )
    _insert_signal(
        conn, "cross_source_divergence", ["mf-b", "0xb"], 0.30,
        "2026-09-22T10:00:00+00:00", {"note": "divergence signal, not tradeable arbitrage"},
    )
    conn.commit()
    conn.close()
    return TestClient(create_app(db))


def test_returns_both_types_newest_first(client):
    resp = client.get("/arbitrage")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    assert body["limit"] == 50
    assert body["offset"] == 0
    items = body["items"]
    assert [it["type"] for it in items] == [
        "cross_source_divergence",  # 09-22, newest
        "logical_constraint",       # 09-21
        "cross_source_divergence",  # 09-20, oldest
    ]
    # market_refs and details are parsed back into structured JSON, not raw strings.
    newest = items[0]
    assert newest["market_refs"] == ["mf-b", "0xb"]
    assert newest["edge"] == 0.30
    lc = items[1]
    assert lc["details"]["constraint"] == "high <= low"


def test_filter_by_type(client):
    resp = client.get("/arbitrage", params={"type": "logical_constraint"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0]["type"] == "logical_constraint"


def test_pagination_limit_and_offset(client):
    page1 = client.get("/arbitrage", params={"limit": 2, "offset": 0}).json()
    assert page1["total"] == 3
    assert [it["edge"] for it in page1["items"]] == [0.30, 0.11]  # newest two
    page2 = client.get("/arbitrage", params={"limit": 2, "offset": 2}).json()
    assert page2["total"] == 3
    assert [it["edge"] for it in page2["items"]] == [0.20]  # remaining oldest


def test_invalid_type_rejected(client):
    resp = client.get("/arbitrage", params={"type": "not_a_real_type"})
    assert resp.status_code == 422


def test_limit_bounds_enforced(client):
    assert client.get("/arbitrage", params={"limit": 0}).status_code == 422
    assert client.get("/arbitrage", params={"limit": 999}).status_code == 422
    assert client.get("/arbitrage", params={"offset": -1}).status_code == 422


def test_empty_db_returns_empty_page(tmp_path):
    client = TestClient(create_app(tmp_path / "empty.db"))
    body = client.get("/arbitrage").json()
    assert body == {"items": [], "total": 0, "limit": 50, "offset": 0}
