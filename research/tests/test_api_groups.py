"""Correlated-groups endpoint tests (dashboard showcase)."""

import sqlite3

import pytest
from fastapi.testclient import TestClient

from parallax_research.api import create_app
from parallax_research.storage import ensure_schema

CONFIG = """
groups:
  - id: g1
    description: "a implies b"
    markets:
      - {key: a, manifold_market_id: "m-a", label: "A"}
      - {key: b, manifold_market_id: "m-b", label: "B"}
    constraints:
      - {lhs: a, op: "<=", rhs: b, note: "a <= b"}
"""


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "p.db"
    conn = sqlite3.connect(path)
    ensure_schema(conn)
    conn.execute(
        "INSERT INTO markets (market_id, platform, question_text, close_time, category) "
        "VALUES ('m-a','manifold','A?','2027-01-01T00:00:00Z','Crypto')"
    )
    conn.execute(
        "INSERT INTO markets (market_id, platform, question_text, close_time, category) "
        "VALUES ('m-b','manifold','B?','2027-01-01T00:00:00Z','Crypto')"
    )
    conn.executemany(
        "INSERT INTO probability_snapshots (market_id, ts_ns, probability) VALUES (?,?,?)",
        [("m-a", 1000, 0.40), ("m-a", 2000, 0.60), ("m-b", 2000, 0.40)],
    )
    conn.commit()
    conn.close()
    return path


def test_groups_reports_live_probs_and_violation(db, tmp_path, monkeypatch):
    cfg = tmp_path / "groups.yaml"
    cfg.write_text(CONFIG)
    monkeypatch.setenv("PARALLAX_GROUPS_CONFIG", str(cfg))
    client = TestClient(create_app(db))
    groups = client.get("/groups").json()
    assert len(groups) == 1
    g = groups[0]
    assert g["category"] == "Crypto"
    # latest a=0.60 > b=0.40 → the constraint a<=b is violated.
    assert g["consistent"] is False
    a = next(m for m in g["markets"] if m["key"] == "a")
    assert a["probability"] == 0.60
    assert a["question_text"] == "A?"
    c = g["constraints"][0]
    assert c["holds"] is False
    assert c["gross_violation"] == pytest.approx(0.20)


def test_groups_empty_without_config(db, tmp_path, monkeypatch):
    monkeypatch.setenv("PARALLAX_GROUPS_CONFIG", str(tmp_path / "missing.yaml"))
    client = TestClient(create_app(db))
    assert client.get("/groups").json() == []
