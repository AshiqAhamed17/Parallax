"""Fuzzy market-match candidate generator (Task 8.3).

Proposes Manifold↔Polymarket equivalences by combining **question-text embedding similarity** with
**close-date proximity**, emitting the top-K pairs above a threshold as `pending` candidates for
human review (Task 8.4). Nothing here ever confirms a match — machine guesses are always `pending`
(constraint §2.2); only a human (via the review CLI or the manual YAML loader) promotes to
`confirmed`.

**Encoder is injected**, not hard-wired. The scoring logic (cosine similarity + date decay + top-K)
is pure and unit-tested with a deterministic fake encoder — no model download, no torch, fast CI.
The production encoder (`SentenceTransformerEncoder`) lazy-imports `sentence-transformers`, which is
an *optional* runtime dependency (heavy: pulls torch) declared outside the default install; see the
class docstring. This keeps the package and CI light while the real embedding path stays available.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

import numpy as np

from parallax_research.matching.repository import (
    ensure_market_matches,
    find_match,
    insert_candidate,
)
from parallax_research.schemas import NormalizedMarket

PLATFORM = "polymarket"


class Encoder(Protocol):
    """Anything that turns a list of texts into an `(n, d)` float embedding matrix."""

    def __call__(self, texts: list[str]) -> np.ndarray: ...


@dataclass(frozen=True)
class Candidate:
    """A proposed match with its component scores (all informational)."""

    manifold_market_id: str
    polymarket_market_id: str
    score: float
    text_similarity: float
    date_factor: float


def _l2_normalize(mat: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    # Guard zero vectors (norm 0 -> leave as zeros rather than divide-by-zero).
    norms[norms == 0] = 1.0
    return mat / norms


def _date_factor(
    a: datetime | None,
    b: datetime | None,
    max_gap_days: float,
    missing: float,
) -> float:
    """Proximity of two close dates in [0, 1]: 1.0 when identical, decaying linearly to 0 at
    `max_gap_days` apart. Returns `missing` when either date is absent (no signal, don't penalize)."""
    if a is None or b is None:
        return missing
    gap_days = abs((a - b).total_seconds()) / 86400.0
    return max(0.0, 1.0 - gap_days / max_gap_days)


def generate_candidates(
    manifold: list[NormalizedMarket],
    polymarket: list[NormalizedMarket],
    *,
    encoder: Encoder,
    threshold: float = 0.6,
    top_k: int = 3,
    text_weight: float = 0.8,
    max_date_gap_days: float = 30.0,
    missing_date_factor: float = 1.0,
) -> list[Candidate]:
    """Rank Polymarket matches for each Manifold market and return candidates above `threshold`.

    `score = text_weight * cosine_similarity + (1 - text_weight) * date_factor`. For each Manifold
    market the top `top_k` Polymarket markets (by score) that clear `threshold` are kept; the full
    result is returned sorted by score, highest first. Empty inputs yield no candidates.
    """
    if not manifold or not polymarket:
        return []

    m_emb = _l2_normalize(np.asarray(encoder([m.question_text for m in manifold]), dtype=float))
    p_emb = _l2_normalize(np.asarray(encoder([p.question_text for p in polymarket]), dtype=float))
    sim = m_emb @ p_emb.T  # cosine similarity (both sides L2-normalized), shape (M, P)

    candidates: list[Candidate] = []
    for i, m in enumerate(manifold):
        scored: list[Candidate] = []
        for j, p in enumerate(polymarket):
            text_sim = float(sim[i, j])
            date_f = _date_factor(m.close_time, p.close_time, max_date_gap_days, missing_date_factor)
            score = text_weight * text_sim + (1.0 - text_weight) * date_f
            if score >= threshold:
                scored.append(Candidate(m.market_id, p.market_id, score, text_sim, date_f))
        scored.sort(key=lambda c: c.score, reverse=True)
        candidates.extend(scored[:top_k])

    candidates.sort(key=lambda c: c.score, reverse=True)
    return candidates


def store_candidates(
    conn: sqlite3.Connection,
    candidates: list[Candidate],
    *,
    platform: str = PLATFORM,
) -> int:
    """Persist candidates as `pending` matches (confidence = combined score). Idempotent: pairs
    already present are skipped. Returns the number of new rows inserted."""
    ensure_market_matches(conn)
    inserted = 0
    for c in candidates:
        if find_match(
            conn,
            manifold_market_id=c.manifold_market_id,
            external_market_id=c.polymarket_market_id,
            platform=platform,
        ) is not None:
            continue
        insert_candidate(
            conn,
            manifold_market_id=c.manifold_market_id,
            external_market_id=c.polymarket_market_id,
            platform=platform,
            confidence=c.score,
        )
        inserted += 1
    return inserted


class SentenceTransformerEncoder:
    """Production [`Encoder`] backed by `sentence-transformers`.

    `sentence-transformers` is an **optional** dependency (it pulls in torch — hundreds of MB and a
    model download on first use), so it is not in the default install. Install it to use this
    encoder: `uv add sentence-transformers`. The import is lazy, so merely importing this module
    (as the fake-encoder tests do) never requires it.

    [`Encoder`]: Encoder
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        self.model_name = model_name
        self._model = None

    def _ensure_model(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:  # pragma: no cover - exercised only without the optional dep
                raise ImportError(
                    "sentence-transformers is an optional dependency for the embedding encoder; "
                    "install it with `uv add sentence-transformers` (pulls torch)."
                ) from exc
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def __call__(self, texts: list[str]) -> np.ndarray:  # pragma: no cover - needs the heavy dep
        model = self._ensure_model()
        return np.asarray(model.encode(list(texts), normalize_embeddings=True), dtype=float)
