"""Response caching + rate limiting tests (Task 13.5).

Uses an injected fake clock so cache-expiry and rate-limit-window behavior is deterministic (no
sleeping). Covers the middleware end-to-end via TestClient plus the two helper classes directly.
"""

import sqlite3

from fastapi.testclient import TestClient

from parallax_research.api import create_app
from parallax_research.api.middleware import FixedWindowRateLimiter, TTLResponseCache
from parallax_research.storage import ensure_schema


class FakeClock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


def _seed_db(path, market_id):
    conn = sqlite3.connect(path)
    ensure_schema(conn)
    conn.execute(
        "INSERT INTO markets (market_id, platform, question_text, close_time) "
        "VALUES (?, 'manifold', 'q', '2027-01-01T00:00:00Z')",
        (market_id,),
    )
    conn.commit()
    conn.close()


# ---- middleware helper classes ------------------------------------------------------------------


def test_ttl_cache_expires_on_clock():
    clock = FakeClock()
    cache = TTLResponseCache(10.0, time_fn=clock)
    cache.set("k", "v")
    assert cache.get("k") == "v"
    clock.advance(9.0)
    assert cache.get("k") == "v"
    clock.advance(1.0)  # now 10 >= expiry(10) -> expired
    assert cache.get("k") is None


def test_rate_limiter_window_and_per_client():
    clock = FakeClock()
    limiter = FixedWindowRateLimiter(2, 60.0, time_fn=clock)
    assert limiter.allow("a")
    assert limiter.allow("a")
    assert not limiter.allow("a")   # 3rd in window -> denied
    assert limiter.allow("b")       # different client has its own budget
    clock.advance(60.0)
    assert limiter.allow("a")       # window elapsed -> reset


# ---- caching middleware end-to-end --------------------------------------------------------------


def test_cache_hit_avoids_db_requery(tmp_path):
    db = tmp_path / "p.db"
    _seed_db(db, "m1")
    clock = FakeClock()
    app = create_app(db, cache_ttl_secs=100.0, rate_limit_max=0, time_fn=clock)
    client = TestClient(app)

    r1 = client.get("/markets")
    assert r1.status_code == 200
    assert r1.headers["x-cache"] == "MISS"
    assert {m["market_id"] for m in r1.json()} == {"m1"}

    # Mutate the DB behind the cache's back.
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO markets (market_id, platform, question_text, close_time) "
        "VALUES ('m2', 'manifold', 'q2', '2027-01-01T00:00:00Z')"
    )
    conn.commit()
    conn.close()

    # Within TTL: served from cache, so the new market is NOT visible (proves no re-query).
    r2 = client.get("/markets")
    assert r2.headers["x-cache"] == "HIT"
    assert r2.json() == r1.json()

    # After TTL expiry: cache miss -> re-query -> new market appears.
    clock.advance(200.0)
    r3 = client.get("/markets")
    assert r3.headers["x-cache"] == "MISS"
    assert {m["market_id"] for m in r3.json()} == {"m1", "m2"}


def test_rate_limit_rejects_after_threshold(tmp_path):
    db = tmp_path / "p.db"
    _seed_db(db, "m1")
    clock = FakeClock()
    app = create_app(
        db, cache_ttl_secs=0, rate_limit_max=3, rate_limit_window_secs=60.0, time_fn=clock
    )
    client = TestClient(app)

    for _ in range(3):
        assert client.get("/health").status_code == 200
    rejected = client.get("/health")
    assert rejected.status_code == 429
    assert rejected.json()["detail"] == "rate limit exceeded"

    # New window -> allowed again.
    clock.advance(61.0)
    assert client.get("/health").status_code == 200
