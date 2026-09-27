"""Market replay endpoint tests (Task 14.6 enabling work)."""

import sqlite3

import pytest
from fastapi.testclient import TestClient

from parallax_research.api import create_app
from parallax_research.storage import ensure_schema


@pytest.fixture
def client(tmp_path):
    db = tmp_path / "p.db"
    conn = sqlite3.connect(db)
    ensure_schema(conn)
    conn.execute(
        "INSERT INTO markets (market_id, platform, question_text, close_time) "
        "VALUES ('m1','manifold','q','2027-01-01T00:00:00Z')"
    )
    conn.executemany(
        "INSERT INTO probability_snapshots (market_id, ts_ns, probability) VALUES (?,?,?)",
        [("m1", 3000, 0.7), ("m1", 1000, 0.4), ("m1", 2000, 0.55)],
    )
    conn.commit()
    conn.close()
    return TestClient(create_app(db))


def test_replay_returns_points_in_time_order(client):
    resp = client.get("/markets/m1/replay")
    assert resp.status_code == 200
    body = resp.json()
    assert body["market_id"] == "m1"
    assert [p["ts_ns"] for p in body["points"]] == [1000, 2000, 3000]
    assert body["points"][0]["probability"] == 0.4


def test_replay_unknown_market_404(client):
    assert client.get("/markets/nope/replay").status_code == 404
