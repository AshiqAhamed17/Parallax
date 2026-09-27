"""Benchmarks & backtests report endpoints tests (Task 13.4). Temp report dirs + real defaults."""

import pytest
from fastapi.testclient import TestClient

from parallax_research.api import create_app


@pytest.fixture
def client(tmp_path):
    bench = tmp_path / "benchmarks"
    reps = tmp_path / "reports"
    bench.mkdir()
    reps.mkdir()
    (bench / "v1-baseline.md").write_text("# V1 baseline\nnumbers")
    (bench / "latency-report.md").write_text("# Latency report\nfloor")
    (reps / "backtest-synthetic.md").write_text("# Backtest synthetic")
    (reps / "backtest-validation.md").write_text("# Backtest validation")
    (reps / "logical-constraint-backtest.md").write_text("# Logical-constraint backtest")
    (reps / "calibration-v1.md").write_text("# Calibration")  # must NOT appear under /backtests
    return TestClient(create_app(tmp_path / "p.db", benchmarks_dir=bench, reports_dir=reps))


def test_benchmarks_serves_all_reports_with_content(client):
    resp = client.get("/benchmarks")
    assert resp.status_code == 200
    data = resp.json()
    names = {r["name"] for r in data}
    assert names == {"v1-baseline.md", "latency-report.md"}
    latency = next(r for r in data if r["name"] == "latency-report.md")
    assert latency["content"] == "# Latency report\nfloor"


def test_backtests_filters_to_backtest_reports(client):
    resp = client.get("/backtests")
    assert resp.status_code == 200
    names = {r["name"] for r in resp.json()}
    assert names == {
        "backtest-synthetic.md",
        "backtest-validation.md",
        "logical-constraint-backtest.md",
    }
    assert "calibration-v1.md" not in names  # calibration is not a backtest report


def test_missing_dir_returns_empty(tmp_path):
    client = TestClient(
        create_app(
            tmp_path / "p.db",
            benchmarks_dir=tmp_path / "does-not-exist",
            reports_dir=tmp_path / "nope",
        )
    )
    assert client.get("/benchmarks").json() == []
    assert client.get("/backtests").json() == []


def test_default_dirs_serve_real_committed_reports(tmp_path):
    # No dirs passed -> repo's committed benchmarks/ and reports/ (reality check).
    client = TestClient(create_app(tmp_path / "p.db"))
    bench = client.get("/benchmarks").json()
    bench_names = {r["name"] for r in bench}
    assert "latency-report.md" in bench_names
    assert all(r["content"].strip() for r in bench)  # every served report is non-empty

    backtests = client.get("/backtests").json()
    bt_names = {r["name"] for r in backtests}
    assert "logical-constraint-backtest.md" in bt_names
    assert "calibration-v1.md" not in bt_names
