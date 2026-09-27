"""Demo-data seed script tests (Task 14 enabling work)."""

import importlib.util
import sqlite3
from pathlib import Path

SPEC = Path(__file__).parents[1] / "scripts" / "seed_demo_db.py"


def _load():
    spec = importlib.util.spec_from_file_location("seed_demo_db", SPEC)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_seed_populates_all_tables(tmp_path):
    mod = _load()
    db = tmp_path / "demo.db"
    counts = mod.seed_demo_db(db)
    conn = sqlite3.connect(db)
    for table in ["markets", "probability_snapshots", "model_predictions", "arbitrage_signals"]:
        n = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        assert n > 0, f"{table} is empty"
        assert counts[table] == n
    markets = [r[0] for r in conn.execute("SELECT market_id FROM markets").fetchall()]
    for m in markets:
        pts = conn.execute(
            "SELECT COUNT(*) FROM probability_snapshots WHERE market_id=?", (m,)
        ).fetchone()[0]
        assert pts >= 10, f"{m} has too few snapshots"
    types = {r[0] for r in conn.execute("SELECT DISTINCT type FROM arbitrage_signals").fetchall()}
    assert types == {"logical_constraint", "cross_source_divergence"}
    conn.close()


def test_seed_is_deterministic(tmp_path):
    mod = _load()
    a, b = tmp_path / "a.db", tmp_path / "b.db"
    assert mod.seed_demo_db(a, seed=7) == mod.seed_demo_db(b, seed=7)
