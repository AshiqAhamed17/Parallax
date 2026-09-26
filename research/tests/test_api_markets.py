"""Markets endpoints tests (Task 13.2). Seeded temp SQLite DB, FastAPI TestClient."""

import sqlite3

import pytest
from fastapi.testclient import TestClient

from parallax_research.api import create_app
from parallax_research.storage import ensure_schema


@pytest.fixture
def client(tmp_path):
    db = tmp_path / "parallax.db"
    conn = sqlite3.connect(db)
    ensure_schema(conn)

    # m1: has probability snapshots (two — newest must win) and model predictions (two).
    conn.execute(
        "INSERT INTO markets (market_id, platform, question_text, close_time, resolved_outcome) "
        "VALUES ('m1', 'manifold', 'Will X happen?', '2027-01-01T00:00:00Z', NULL)"
    )
    conn.executemany(
        "INSERT INTO probability_snapshots (market_id, ts_ns, probability, volume_24h) VALUES (?,?,?,?)",
        [("m1", 1000, 0.30, 111.0), ("m1", 2000, 0.42, 222.0)],
    )
    conn.executemany(
        "INSERT INTO model_predictions (market_id, ts_ns, p_model, p_market, edge, ev) VALUES (?,?,?,?,?,?)",
        [("m1", 1500, 0.50, 0.30, 0.20, 0.15), ("m1", 2500, 0.55, 0.42, 0.13, 0.08)],
    )
    # m2: metadata only — no snapshots, no predictions (nulls in the response).
    conn.execute(
        "INSERT INTO markets (market_id, platform, question_text, close_time, resolved_outcome) "
        "VALUES ('m2', 'manifold', 'Will Y happen?', '2027-06-01T00:00:00Z', 1)"
    )
    conn.commit()
    conn.close()
    return TestClient(create_app(db))


def test_list_markets_returns_both_with_latest_state(client):
    resp = client.get("/markets")
    assert resp.status_code == 200
    data = resp.json()
    assert {m["market_id"] for m in data} == {"m1", "m2"}
    # Market with a snapshot sorts before the one without.
    assert data[0]["market_id"] == "m1"

    m1 = next(m for m in data if m["market_id"] == "m1")
    assert m1["probability"] == 0.42  # latest snapshot, not the older 0.30
    assert m1["volume_24h"] == 222.0
    assert m1["last_updated_ns"] == 2000
    assert m1["prediction"]["ts_ns"] == 2500  # latest prediction
    assert m1["prediction"]["edge"] == 0.13

    m2 = next(m for m in data if m["market_id"] == "m2")
    assert m2["probability"] is None
    assert m2["last_updated_ns"] is None
    assert m2["prediction"] is None
    assert m2["resolved_outcome"] == 1


def test_get_market_detail(client):
    resp = client.get("/markets/m1")
    assert resp.status_code == 200
    body = resp.json()
    assert body["market_id"] == "m1"
    assert body["question_text"] == "Will X happen?"
    assert body["probability"] == 0.42
    assert body["prediction"]["p_model"] == 0.55


def test_get_market_without_data(client):
    resp = client.get("/markets/m2")
    assert resp.status_code == 200
    body = resp.json()
    assert body["probability"] is None
    assert body["prediction"] is None


def test_get_unknown_market_404(client):
    resp = client.get("/markets/does-not-exist")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"]


def test_empty_db_returns_empty_list(tmp_path):
    # No markets seeded; endpoint must still work (schema self-ensured) and return [].
    client = TestClient(create_app(tmp_path / "empty.db"))
    resp = client.get("/markets")
    assert resp.status_code == 200
    assert resp.json() == []
