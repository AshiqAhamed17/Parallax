"""Response caching + rate limiting primitives for the API (Task 13.5).

Two small, dependency-free helpers wired into the app as HTTP middleware:

- `TTLResponseCache` — caches GET responses for a TTL so repeated identical requests are served from
  memory without re-querying SQLite. Keyed by (path, query string).
- `FixedWindowRateLimiter` — a per-client fixed-window counter; rejects once a client exceeds
  `max_requests` within `window_secs`.

Both take an injectable `time_fn` (defaults to `time.monotonic`) so tests can drive time
deterministically instead of sleeping.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any


class TTLResponseCache:
    """In-memory TTL cache of response payloads, keyed by an arbitrary hashable key."""

    def __init__(self, ttl_secs: float, time_fn: Callable[[], float] = time.monotonic) -> None:
        self.ttl = ttl_secs
        self._time = time_fn
        self._store: dict[Any, tuple[float, Any]] = {}

    def get(self, key: Any) -> Any | None:
        """Return the cached value for `key`, or None on miss/expiry (expired entries are evicted)."""
        entry = self._store.get(key)
        if entry is None:
            return None
        expiry, value = entry
        if self._time() >= expiry:
            del self._store[key]
            return None
        return value

    def set(self, key: Any, value: Any) -> None:
        self._store[key] = (self._time() + self.ttl, value)


class FixedWindowRateLimiter:
    """Per-client fixed-window request limiter."""

    def __init__(
        self,
        max_requests: int,
        window_secs: float,
        time_fn: Callable[[], float] = time.monotonic,
    ) -> None:
        self.max_requests = max_requests
        self.window = window_secs
        self._time = time_fn
        self._windows: dict[str, tuple[float, int]] = {}

    def allow(self, client_id: str) -> bool:
        """Record a request from `client_id`; return False if it exceeds the window's allowance."""
        now = self._time()
        start, count = self._windows.get(client_id, (now, 0))
        if now - start >= self.window:
            start, count = now, 0  # window elapsed → reset
        count += 1
        self._windows[client_id] = (start, count)
        return count <= self.max_requests
