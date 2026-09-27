"""CORS middleware tests for the dashboard (Task 14 enabling work)."""

from fastapi.testclient import TestClient

from parallax_research.api import create_app


def test_cors_allows_configured_origin(tmp_path):
    app = create_app(tmp_path / "p.db", cors_origins=["http://localhost:3000"])
    client = TestClient(app)
    resp = client.get("/health", headers={"Origin": "http://localhost:3000"})
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_cors_preflight(tmp_path):
    app = create_app(tmp_path / "p.db", cors_origins=["http://localhost:3000"])
    client = TestClient(app)
    resp = client.options(
        "/markets",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.status_code in (200, 204)
    assert resp.headers["access-control-allow-origin"] == "http://localhost:3000"
