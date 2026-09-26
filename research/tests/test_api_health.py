"""API health-check test (Task 13.1). FastAPI TestClient (httpx-based), asserting 200."""

from fastapi.testclient import TestClient

from parallax_research.api import create_app


def test_health_returns_200(tmp_path):
    app = create_app(tmp_path / "parallax.db")
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
