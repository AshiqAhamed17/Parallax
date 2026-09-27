# Parallax Public Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Parallax's public, read-only dashboard — a distinctive cyan-on-near-black quant/low-latency UI (landing + markets + signals + performance) rendering real seeded data, satisfying Phase 14 (Tasks 14.1–14.8).

**Architecture:** Next.js 16 App Router (React 19, Tailwind v4) frontend in `dashboard/`, fetching a read-only FastAPI backend (`parallax_research.api`). During development the API serves a committed, realistic demo SQLite DB so the UI looks alive offline. Two small enabling API additions (CORS + a replay endpoint) precede the frontend work. shadcn/ui primitives are custom-themed to our tokens; `motion` drives rich-but-reduced-motion-safe animation; Recharts 3 + hand-rolled SVG draw the data.

**Tech Stack:** Next.js 16, React 19, Tailwind v4, Geist Sans/Mono, shadcn/ui (Radix), motion (Framer Motion), Recharts 3, Playwright; FastAPI + Python 3.12 (`uv`) for the API additions and seed script.

**Spec:** `docs/superpowers/specs/2026-09-27-dashboard-design.md`

## Global Constraints

- Dark-only. Exact tokens: canvas `#0A0B0D`; surfaces `#101216` / `#15181D`; borders `rgba(255,255,255,0.06–0.10)`; radii 12–16px.
- Signature accent: electric cyan `#22D3EE` (+ sky `#38BDF8` gradients), used sparingly.
- Status colors (dot + pill, never color-only): crit `#F43F5E` · high `#FB923C` · med `#FACC15` · low `#38BDF8` · ok/positive `#34D399`.
- Geist Sans for UI; Geist Mono for ALL data (probs, edge/EV, hashes, IDs, timestamps, code). `font-variant-numeric: tabular-nums` on all numbers.
- Every route shows the disclaimer. Read-only only — no auth, no write/bet endpoint, no server-side user state (constraint §2.1).
- All motion respects `prefers-reduced-motion`.
- Never fabricate measured numbers: `/performance` renders the REAL committed reports from `benchmarks/`+`reports/`; `/markets` and `/signals` use the demo DB and must carry a visible "demo data" label until the live collector feeds them.
- Python gate (run from `research/`): `uv run ruff check .` && `uv run pytest`. Frontend gate (run from `dashboard/`): `npm run lint` && `npm run build`; Playwright where specified.
- Commit style: short, plain, human messages, NO AI attribution. After each task: tick it in `tasks.md`, `gh auth status` (ensure `AshiqAhamed17`; if not, `gh auth switch --user AshiqAhamed17 && gh auth setup-git`), commit, push.
- `NEXT_PUBLIC_API_URL` configures the API base (default `http://localhost:8000`).

## Review Focus

- **API unreachable / fetch failure** → pages render a graceful error/empty state, never a crashed route. (Task 6 + each page's loader.)
- **Market with no probability snapshots** → `Sparkline`/`EdgeBar` render an empty/placeholder state, never `NaN` or a thrown error. (Task 8.)
- **Market with no model prediction** → edge/EV cells show `—`, not `undefined`/`NaN`. (Task 9.)
- **Unknown market id at `/markets/[id]`** → Next `not-found` (404) page, not an exception. (Task 10.)
- **`prefers-reduced-motion: reduce`** → all entrance/loop animations collapse to instant. (Task 7 sets the primitive; verified in Task 14.)
- **Watchlist save/unsave** → zero network requests; state survives reload. (Task 15, asserted via request log.)
- **`/signals` pagination past the end** (`offset ≥ total`) → empty list, controls disabled, no crash. (Task 11.)

---

## Task 1: API — CORS middleware

**Files:**
- Modify: `research/src/parallax_research/api/app.py`
- Test: `research/tests/test_api_cors.py`

**Interfaces:**
- Consumes: existing `create_app(db_path, *, ...)` factory.
- Produces: `create_app(..., cors_origins: list[str] | None = None)` — when None, reads `PARALLAX_CORS_ORIGINS` (comma-separated) or defaults to `["http://localhost:3000"]`; installs `CORSMiddleware`.

- [ ] **Step 1: Write the failing test**

```python
# research/tests/test_api_cors.py
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
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd research && uv run pytest tests/test_api_cors.py -v`
Expected: FAIL (no `access-control-allow-origin` header).

- [ ] **Step 3: Implement**

In `app.py`, add near the other imports:

```python
from fastapi.middleware.cors import CORSMiddleware

DEFAULT_CORS_ORIGINS = ["http://localhost:3000"]


def _default_cors_origins() -> list[str]:
    raw = os.environ.get("PARALLAX_CORS_ORIGINS")
    return [o.strip() for o in raw.split(",") if o.strip()] if raw else DEFAULT_CORS_ORIGINS
```

Add `cors_origins: list[str] | None = None` to `create_app`'s keyword args, and right after `app = FastAPI(...)`:

```python
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins if cors_origins is not None else _default_cors_origins(),
        allow_methods=["GET", "OPTIONS"],
        allow_headers=["*"],
    )
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd research && uv run pytest tests/test_api_cors.py -v` → PASS.

- [ ] **Step 5: Gate + commit**

Run: `cd research && uv run ruff check . && uv run pytest -q`
Tick nothing in tasks.md yet (this is enabling work). Commit:

```bash
git add research/src/parallax_research/api/app.py research/tests/test_api_cors.py
git commit -m "add CORS to api for the dashboard"
```

---

## Task 2: API — market replay endpoint

**Files:**
- Modify: `research/src/parallax_research/api/models.py`, `research/src/parallax_research/api/app.py`, `research/src/parallax_research/api/__init__.py`
- Test: `research/tests/test_api_replay.py`

**Interfaces:**
- Produces: `GET /markets/{market_id}/replay` → `ReplayOut { market_id: str, points: list[ReplayPoint] }`, `ReplayPoint { ts_ns: int, probability: float }`, ordered by `ts_ns` ASC. 404 if the market is unknown.

- [ ] **Step 1: Write the failing test**

```python
# research/tests/test_api_replay.py
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
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd research && uv run pytest tests/test_api_replay.py -v` → FAIL (404 for both / route missing).

- [ ] **Step 3: Add models**

In `models.py`:

```python
class ReplayPoint(BaseModel):
    ts_ns: int
    probability: float


class ReplayOut(BaseModel):
    market_id: str
    points: list[ReplayPoint]
```

- [ ] **Step 4: Add the route**

In `app.py`, import `ReplayOut, ReplayPoint`, then after `get_market`:

```python
    @app.get("/markets/{market_id}/replay", response_model=ReplayOut)
    def get_market_replay(market_id: str, conn: ConnDep) -> ReplayOut:
        exists = conn.execute(
            "SELECT 1 FROM markets WHERE market_id = ?", (market_id,)
        ).fetchone()
        if exists is None:
            raise HTTPException(status_code=404, detail=f"market {market_id!r} not found")
        rows = conn.execute(
            "SELECT ts_ns, probability FROM probability_snapshots "
            "WHERE market_id = ? ORDER BY ts_ns ASC",
            (market_id,),
        ).fetchall()
        return ReplayOut(
            market_id=market_id,
            points=[ReplayPoint(ts_ns=int(r["ts_ns"]), probability=float(r["probability"])) for r in rows],
        )
```

Export `ReplayOut`, `ReplayPoint` from `__init__.py` (add to imports + `__all__`).

- [ ] **Step 5: Run to verify it passes**

Run: `cd research && uv run pytest tests/test_api_replay.py -v` → PASS.

- [ ] **Step 6: Gate + commit**

Run: `cd research && uv run ruff check . && uv run pytest -q`

```bash
git add research/src/parallax_research/api/ research/tests/test_api_replay.py
git commit -m "add market replay endpoint"
```

---

## Task 3: Demo data seed script

**Files:**
- Create: `research/scripts/seed_demo_db.py`
- Test: `research/tests/test_seed_demo_db.py`

**Interfaces:**
- Produces: `seed_demo_db(db_path: str | Path, *, seed: int = 7) -> dict[str, int]` — writes markets, probability_snapshots, model_predictions, arbitrage_signals into `db_path`; returns row counts per table. A `main()` writes to `../data/parallax-demo.db` by default.

- [ ] **Step 1: Write the failing test**

```python
# research/tests/test_seed_demo_db.py
import sqlite3
import importlib.util
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
    # Every market has probability history so sparklines have shape.
    markets = [r[0] for r in conn.execute("SELECT market_id FROM markets").fetchall()]
    for m in markets:
        pts = conn.execute(
            "SELECT COUNT(*) FROM probability_snapshots WHERE market_id=?", (m,)
        ).fetchone()[0]
        assert pts >= 10
    # Both signal types present.
    types = {r[0] for r in conn.execute("SELECT DISTINCT type FROM arbitrage_signals").fetchall()}
    assert types == {"logical_constraint", "cross_source_divergence"}
    conn.close()


def test_seed_is_deterministic(tmp_path):
    mod = _load()
    a, b = tmp_path / "a.db", tmp_path / "b.db"
    assert mod.seed_demo_db(a, seed=7) == mod.seed_demo_db(b, seed=7)
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd research && uv run pytest tests/test_seed_demo_db.py -v` → FAIL (file missing).

- [ ] **Step 3: Implement the seed script**

Create `research/scripts/seed_demo_db.py`. Use `parallax_research.storage.ensure_schema`, a `random.Random(seed)` for reproducibility, and `parallax_research.calibration.edge.compute_edge_ev` to make edge/EV internally consistent. Write ~12 markets with realistic questions (include a few resolved), 30–60 probability snapshots each forming a smooth-ish random walk in (0.02, 0.98), one latest model_prediction per open market, and ~8 arbitrage_signals split across both types with realistic `details_json` (mirror the shapes `persist_signal`/`persist_violation` write). Label questions so they're clearly illustrative. Provide `seed_demo_db(db_path, *, seed=7)` returning counts and a `main()` writing to `../data/parallax-demo.db`. Timestamps: use fixed base epoch-ns constants (do not call wall-clock in the deterministic core; `main()` may stamp real time).

- [ ] **Step 4: Run to verify it passes**

Run: `cd research && uv run pytest tests/test_seed_demo_db.py -v` → PASS.

- [ ] **Step 5: Generate the demo DB + gate + commit**

Run: `cd research && uv run python scripts/seed_demo_db.py` (writes `data/parallax-demo.db`; gitignored — that's fine).
Run: `cd research && uv run ruff check . && uv run pytest -q`

```bash
git add research/scripts/seed_demo_db.py research/tests/test_seed_demo_db.py
git commit -m "add demo data seed script"
```

- [ ] **Step 6: Sanity-run the API against the demo DB**

Run: `cd research && PARALLAX_DB=../data/parallax-demo.db uv run uvicorn parallax_research.api.app:app --port 8000 &` then `curl -s localhost:8000/markets | head` shows populated markets; `curl -s localhost:8000/arbitrage` shows both signal types. Kill the server. (No commit — verification only.)

---

## Task 4: Dashboard tooling + design tokens

**Files:**
- Modify: `dashboard/package.json`, `dashboard/src/app/globals.css`, `dashboard/src/app/layout.tsx`
- Create: `dashboard/components.json` (shadcn config), `dashboard/.env.local.example`

**Interfaces:**
- Produces: the token layer (CSS vars + Tailwind `@theme`), installed deps (`motion`, `recharts`, shadcn deps), Geist fonts wired, dark-locked `<html>`.

- [ ] **Step 1: Install dependencies**

Run:
```bash
cd dashboard
npm i motion recharts
npm i geist   # Geist font package (if not already via next/font)
npx shadcn@latest init -d   # choose defaults; we override the theme next
```

- [ ] **Step 2: Write the token layer**

Replace `dashboard/src/app/globals.css` with `@import "tailwindcss";` plus a `:root` block defining every Global-Constraint token as CSS vars, an `@theme inline` block exposing them to Tailwind (`--color-canvas`, `--color-accent`, `--color-crit`, …), base `body { background: var(--color-canvas); color: … }`, `*{ }` border color default, tabular-nums utility, and a `@media (prefers-reduced-motion: reduce)` block zeroing transition/animation durations globally.

- [ ] **Step 3: Lock dark mode + fonts in layout**

In `layout.tsx`: set `<html lang="en" className="dark">`, wire `GeistSans`/`GeistMono` via `next/font` (or the `geist` package) exposing `--font-geist-sans`/`--font-geist-mono`, set `<body>` to the sans var.

- [ ] **Step 4: Verify build**

Run: `cd dashboard && npm run build`
Expected: build succeeds; the page renders on `#0A0B0D`.

- [ ] **Step 5: Commit**

```bash
git add dashboard/package.json dashboard/package-lock.json dashboard/components.json dashboard/src/app/globals.css dashboard/src/app/layout.tsx dashboard/.env.local.example
git commit -m "add dashboard design tokens and tooling"
```

---

## Task 5: API client + shared types

**Files:**
- Create: `dashboard/src/lib/types.ts`, `dashboard/src/lib/api.ts`

**Interfaces:**
- Produces (types mirror the API): `Market` (market_id, platform, question_text, close_time, resolved_outcome, probability, volume_24h, last_updated_ns, prediction), `ModelPrediction` (ts_ns, p_model, p_market, edge, ev), `ArbitrageSignal` (id, type, market_refs, edge, detected_at, details), `PaginatedSignals` (items, total, limit, offset), `Report` (name, content), `Replay` (market_id, points[{ts_ns, probability}]).
- Produces (client): `getMarkets(): Promise<Market[]>`, `getMarket(id): Promise<Market | null>`, `getSignals(opts?): Promise<PaginatedSignals>`, `getBenchmarks(): Promise<Report[]>`, `getBacktests(): Promise<Report[]>`, `getReplay(id): Promise<Replay | null>`. All read `process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"`, use `fetch` with `{ cache: "no-store" }`, and throw a typed `ApiError` on non-2xx (except `getMarket`/`getReplay` return `null` on 404).

- [ ] **Step 1: Write types** — `types.ts` with the interfaces above, matching field names exactly.
- [ ] **Step 2: Write the client** — `api.ts` with a `request<T>(path)` helper (base URL, no-store, error handling) and the six functions.
- [ ] **Step 3: Typecheck** — Run: `cd dashboard && npx tsc --noEmit` → no errors.
- [ ] **Step 4: Commit**

```bash
git add dashboard/src/lib/types.ts dashboard/src/lib/api.ts
git commit -m "add dashboard api client and types"
```

---

## Task 6: Core primitives — StatusPill, Sparkline, EdgeBar, formatting

**Files:**
- Create: `dashboard/src/lib/format.ts`, `dashboard/src/components/status-pill.tsx`, `dashboard/src/components/sparkline.tsx`, `dashboard/src/components/edge-bar.tsx`
- Test: `dashboard/src/lib/format.test.ts` (if a unit runner is present) — otherwise cover via the Playwright/build gate.

**Interfaces:**
- Produces: `fmtProb(p: number|null): string` (`"—"` when null, else `"64.2%"`), `fmtEdge(e:number|null)`, `fmtEv(e:number|null)`, `fmtTs(ns:number|null)`; `StatusPill({status, label})`; `Sparkline({points: number[], className?})` (animated SVG path-draw, empty state when `points.length < 2`); `EdgeBar({pMarket, pModel})` (diverging bar; renders placeholder when either is null).

- [ ] **Step 1: Implement `format.ts`** — pure functions; every one returns `"—"` for `null`/`NaN`.
- [ ] **Step 2: Implement `StatusPill`** — dot + label, color from status token; text label always present (never color-only).
- [ ] **Step 3: Implement `Sparkline`** — hand-rolled SVG polyline scaled to points; `motion` path-draw on mount; **guard: `points.length < 2` → render a flat muted baseline, never `NaN` path** (Review Focus: empty snapshots).
- [ ] **Step 4: Implement `EdgeBar`** — normalize pMarket/pModel to a 0–100 track, highlight the span between them in cyan/status; **guard: null input → muted placeholder**.
- [ ] **Step 5: Verify** — Run: `cd dashboard && npx tsc --noEmit && npm run build` → passes.
- [ ] **Step 6: Commit**

```bash
git add dashboard/src/lib/format.ts dashboard/src/components/status-pill.tsx dashboard/src/components/sparkline.tsx dashboard/src/components/edge-bar.tsx
git commit -m "add core dashboard primitives"
```

---

## Task 7: App shell — layout, top nav, disclaimer, motion primitive (Task 14.1)

**Files:**
- Modify: `dashboard/src/app/layout.tsx`, `dashboard/src/components/disclaimer-banner.tsx`
- Create: `dashboard/src/components/top-nav.tsx`, `dashboard/src/components/reveal.tsx` (reduced-motion-aware entrance wrapper), `dashboard/src/components/live-dot.tsx`

**Interfaces:**
- Produces: persistent shell rendered by `layout.tsx` wrapping all routes — `TopNav` (logo, links Overview/Markets/Signals/Performance, a `LiveDot` status) + `DisclaimerBanner` visible on every route; `Reveal({children, delay?})` (staggered fade/slide, collapses to instant under reduced motion); `LiveDot({label?})` (pulsing cyan dot).

- [ ] **Step 1: Restyle `DisclaimerBanner`** to the token system; keep it in the shell so it shows on every route.
- [ ] **Step 2: Build `TopNav`** with active-link styling (cyan underline/text on the current route).
- [ ] **Step 3: Build `Reveal`** using `motion`, reading `useReducedMotion()` to skip animation.
- [ ] **Step 4: Compose the shell in `layout.tsx`** — TopNav + banner + `{children}` in a max-width container.
- [ ] **Step 5: Verify** — Run: `cd dashboard && npm run build`; `npm run dev` and confirm nav + disclaimer render on `/`.
- [ ] **Step 6: Tick Task 14.1 in `tasks.md`, gate, commit, push**

Run: `cd dashboard && npm run lint && npm run build`; `gh auth status` (ensure AshiqAhamed17).

```bash
git add dashboard/src tasks.md
git commit -m "build dashboard shell with nav and disclaimer"
git push
```

---

## Task 8: Landing / Overview page (part of Task 14.1)

**Files:**
- Create: `dashboard/src/app/page.tsx` (replace scaffold), `dashboard/src/components/prob-tape.tsx`, `dashboard/src/components/floating-panel.tsx`, `dashboard/src/components/stat-card.tsx`, `dashboard/src/components/hero.tsx`

**Interfaces:**
- Consumes: `getMarkets`, `getSignals`, `getBenchmarks`, `getBacktests` (Task 5); `Sparkline`, `StatCard`, `Reveal`, `LiveDot`.
- Produces: the `/` route — hero (headline + subhead + CTAs + `ProbTape` + parallaxing `FloatingPanel` mock showing real seeded market rows) → bento `StatCard` grid (markets tracked, top model edge, latest signal, latency p50/p99 from a report, backtest P&L) → disclaimer note. Server Component fetches; interactive/animated bits are client subcomponents.

- [ ] **Step 1: Build `ProbTape`** — client component; horizontally scrolling mono ticker of `{question, probability}`; pauses on hover; reduced-motion → static row.
- [ ] **Step 2: Build `FloatingPanel`** — a bordered "app window" card with traffic-light dots; pointer/scroll parallax via `motion` (reduced-motion → static).
- [ ] **Step 3: Build `StatCard`** — label + big mono value + optional sparkline/trend; count-up on mount (reduced-motion → final value immediately).
- [ ] **Step 4: Compose `page.tsx`** — fetch data server-side; derive headline stats; **guard: if a fetch fails, render the hero with a muted "data unavailable" stat state** (Review Focus: API unreachable).
- [ ] **Step 5: Verify** — Run API against demo DB (Task 3 Step 6), `cd dashboard && npm run dev`, confirm the landing renders full with real seeded numbers, tape scrolls, panel parallaxes.
- [ ] **Step 6: Verify build + reduced motion** — `npm run build`; in devtools emulate `prefers-reduced-motion: reduce` and confirm no motion.
- [ ] **Step 7: Commit + push** (Task 14.1 already ticked in Task 7; note landing completion in its tasks.md sub-note)

```bash
git add dashboard/src
git commit -m "build dashboard landing overview page"
git push
```

---

## Task 9: Markets page (Task 14.2)

**Files:**
- Create: `dashboard/src/app/markets/page.tsx`, `dashboard/src/components/markets-table.tsx`, `dashboard/src/components/market-row.tsx`
- Add shadcn: `table`, `input`, `badge` (`npx shadcn@latest add table input badge`)

**Interfaces:**
- Consumes: `getMarkets`, `EdgeBar`, `Sparkline`, `StatusPill`, `fmt*`, `getReplay` optional (for row sparkline use the market's own recent points if exposed; otherwise sparkline from `getReplay` is Task 12 — here use `probability` only + a small inline sparkline from replay fetched per visible market is out of scope; use a static mini-bar).
- Produces: `/markets` — a sortable/filterable/searchable table: question · market prob · model prob · `EdgeBar` · EV pill · freshness `LiveDot`. Client `MarketsTable` handles sort/filter/search over server-fetched rows.

- [ ] **Step 1: Add shadcn table/input/badge**, theme them to tokens.
- [ ] **Step 2: Build `MarketRow`** — one row; **guard: null probability → `—` and muted; null prediction → edge/EV `—`** (Review Focus).
- [ ] **Step 3: Build `MarketsTable`** (client) — search box (question substring), sort by edge/EV/prob, filter (has-signal / open-only).
- [ ] **Step 4: Compose `page.tsx`** — server fetch `getMarkets`, pass to table; empty/error state if fetch fails.
- [ ] **Step 5: Verify** — with API+demo DB running, confirm rows, sorting, search, edge bars, EV pills.
- [ ] **Step 6: Build gate, tick Task 14.2, commit, push**

```bash
git add dashboard/src tasks.md
git commit -m "build markets overview page"
git push
```

---

## Task 10: Market detail page (Task 14.3)

**Files:**
- Create: `dashboard/src/app/markets/[id]/page.tsx`, `dashboard/src/app/markets/[id]/not-found.tsx`, `dashboard/src/components/prob-chart.tsx`, `dashboard/src/components/market-meta.tsx`
- Add shadcn: `tabs` if used here.

**Interfaces:**
- Consumes: `getMarket`, `getReplay`, `getSignals` (filter to this market via `market_refs`), `EdgeBar`, `StatusPill`, `fmt*`; Recharts for the probability-over-time chart.
- Produces: `/markets/[id]` (real dynamic route) — probability-over-time chart (from `getReplay`), edge/EV panel, live signal state for the market, metadata (close time, volume, resolution). `getMarket` returning null → `notFound()`.

- [ ] **Step 1: Build `ProbChart`** — Recharts line of replay points (ts→prob), cyan line, dark grid, tooltip in mono. Follow the `dataviz` skill for axes/legend/color.
- [ ] **Step 2: Build `MarketMeta`** — metadata strip in mono.
- [ ] **Step 3: Compose `page.tsx`** — `const m = await getMarket(id); if (!m) notFound();` then render chart + edge panel + signals for this market + meta. **Guard: unknown id → `not-found.tsx`** (Review Focus).
- [ ] **Step 4: Verify** — visit a real seeded market id; confirm chart, edge, signals, meta; visit a bogus id → 404 page.
- [ ] **Step 5: Build gate, tick Task 14.3, commit, push**

```bash
git add dashboard/src tasks.md
git commit -m "build market detail view"
git push
```

---

## Task 11: Signals panel (Task 14.4)

**Files:**
- Create: `dashboard/src/app/signals/page.tsx`, `dashboard/src/components/signal-card.tsx`, `dashboard/src/components/signal-tabs.tsx`
- Add shadcn: `tabs`.

**Interfaces:**
- Consumes: `getSignals({type, limit, offset})`, `StatusPill`, `fmt*`.
- Produces: `/signals` — tabbed (Logical-constraint | Cross-source divergence), paginated. `SignalCard` renders type, severity dot+pill, mono `market_refs`, `details` as a key/value strip, edge in mono. Divergence tab shows the "market vs. independent forecast — not tradeable arbitrage" label.

- [ ] **Step 1: Build `SignalCard`** — render both signal shapes from `details` generically (iterate key/values), highlight `edge`.
- [ ] **Step 2: Build `SignalTabs`** (client) — tab switches `type` filter; Prev/Next pager over `offset`/`limit` using `total`. **Guard: `offset ≥ total` → empty state, Next disabled** (Review Focus).
- [ ] **Step 3: Compose `page.tsx`** — server fetch first page; client tabs/pager fetch subsequent pages.
- [ ] **Step 4: Verify** — both tabs show seeded signals; pager works; divergence label present.
- [ ] **Step 5: Build gate, tick Task 14.4, commit, push**

```bash
git add dashboard/src tasks.md
git commit -m "build arbitrage and divergence signals panel"
git push
```

---

## Task 12: Performance page (Task 14.5)

**Files:**
- Create: `dashboard/src/app/performance/page.tsx`, `dashboard/src/components/report-view.tsx`, `dashboard/src/components/latency-chart.tsx`, `dashboard/src/components/pnl-note.tsx`
- Add: a small Markdown renderer dep (`npm i react-markdown`) for report bodies.

**Interfaces:**
- Consumes: `getBenchmarks`, `getBacktests`.
- Produces: `/performance` — renders the REAL committed reports; parses the latency percentile table from `latency-report.md`/`v3-results.md` into a Recharts bar chart (p50/p95/p99/p99.9/max) and renders the report Markdown; renders backtest reports (P&L numbers) via `ReportView`. Clearly separates "measured (real)" perf/backtest reports from the demo markets/signals elsewhere.

- [ ] **Step 1: Build `ReportView`** — `react-markdown` styled to tokens (mono code, cyan links, bordered tables).
- [ ] **Step 2: Build `LatencyChart`** — parse percentile rows out of a report's markdown table into `{percentile, us}` and render a Recharts bar (follow `dataviz` skill). **Guard: if parsing finds no table, fall back to rendering the report markdown only** (Review Focus: unexpected report shape).
- [ ] **Step 3: Compose `page.tsx`** — fetch both report sets; render latency chart + benchmark reports + backtest reports.
- [ ] **Step 4: Verify** — confirm real numbers from `benchmarks/`+`reports/` appear; latency chart matches the table.
- [ ] **Step 5: Build gate, tick Task 14.5, commit, push**

```bash
git add dashboard/src dashboard/package.json dashboard/package-lock.json tasks.md
git commit -m "build benchmarks and backtest results page"
git push
```

---

## Task 13: Historical replay control (Task 14.6)

**Files:**
- Create: `dashboard/src/components/replay-scrubber.tsx`
- Modify: `dashboard/src/app/markets/[id]/page.tsx` (mount the scrubber)

**Interfaces:**
- Consumes: `getReplay(id)` (Task 5), `ProbChart`.
- Produces: `ReplayScrubber({points})` — a client slider that scrubs an index over the replay points, revealing the probability curve up to that time and showing the value at the playhead; a play/pause that advances the index on a timer (reduced-motion → no autoplay, manual scrub only).

- [ ] **Step 1: Build `ReplayScrubber`** — controlled slider over `points` index; play/pause via `setInterval`; renders `ProbChart` sliced to `[0..i]` + the playhead value in mono. **Guard: `points.length === 0` → disabled control + "no history" note.**
- [ ] **Step 2: Mount** in the market detail page (already served by the Task 2 endpoint).
- [ ] **Step 3: Verify** — scrub reveals the curve; play advances; reduced-motion disables autoplay.
- [ ] **Step 4: Build gate, tick Task 14.6, commit, push**

```bash
git add dashboard/src tasks.md
git commit -m "add historical replay control"
git push
```

---

## Task 14: Responsive + accessibility + Playwright smoke (Task 14.7)

**Files:**
- Create: `dashboard/playwright.config.ts`, `dashboard/tests/smoke.spec.ts`
- Modify: `dashboard/package.json` (add `test:e2e` script), `.github/workflows/frontend.yml`
- Touch: page/component files for responsive + a11y fixes as found.

**Interfaces:**
- Produces: a Playwright smoke test; a responsive/a11y pass across pages.

- [ ] **Step 1: Install Playwright** — `cd dashboard && npm i -D @playwright/test && npx playwright install --with-deps chromium`.
- [ ] **Step 2: Write the smoke test**

```ts
// dashboard/tests/smoke.spec.ts
import { test, expect } from "@playwright/test";

test("homepage shows disclaimer and at least one market row", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText(/disclaimer|observes markets|never trades/i)).toBeVisible();
  await page.goto("/markets");
  await expect(page.locator("table tbody tr").first()).toBeVisible();
});

test("respects reduced motion", async ({ browser }) => {
  const ctx = await browser.newContext({ reducedMotion: "reduce" });
  const page = await ctx.newPage();
  await page.goto("/");
  await expect(page).toHaveTitle(/parallax/i);
});
```

- [ ] **Step 3: Configure `playwright.config.ts`** — `webServer` starts `npm run dev` (or `build && start`) with `NEXT_PUBLIC_API_URL` pointing at a locally-run API against the demo DB; baseURL `http://localhost:3000`.
- [ ] **Step 4: Responsive/a11y pass** — verify each page from mobile→desktop; add focus-visible rings, aria labels on icon buttons, alt text; ensure status is never color-only (already dot+label).
- [ ] **Step 5: Run** — `cd dashboard && npm run test:e2e` → PASS. Extend `frontend.yml` to run it.
- [ ] **Step 6: Tick Task 14.7, commit, push**

```bash
git add dashboard tasks.md .github/workflows/frontend.yml
git commit -m "add playwright smoke test and responsive polish"
git push
```

---

## Task 15: Browser-local watchlist (Task 14.8)

**Files:**
- Create: `dashboard/src/lib/watchlist.ts`, `dashboard/src/components/watchlist-toggle.tsx`, `dashboard/src/app/watchlist/page.tsx`
- Modify: `dashboard/src/components/market-row.tsx`, `dashboard/src/app/markets/[id]/page.tsx` (mount toggle), `dashboard/src/components/top-nav.tsx` (add Watchlist link)
- Test: `dashboard/tests/watchlist.spec.ts`

**Interfaces:**
- Produces: `watchlist.ts` — `getWatchlist(): string[]`, `toggle(id): void`, `isSaved(id): boolean`, all `localStorage`-only (key `parallax:watchlist`), plus a `useWatchlist()` hook; `WatchlistToggle({marketId})` (star button); `/watchlist` route filtering markets to saved ids.

- [ ] **Step 1: Implement `watchlist.ts`** — pure `localStorage` read/write, SSR-safe (guard `typeof window`).
- [ ] **Step 2: Build `WatchlistToggle`** — star that flips saved state; **no network call ever**.
- [ ] **Step 3: Add toggle** to market rows + detail; add `/watchlist` page filtering `getMarkets()` to saved ids; add nav link.
- [ ] **Step 4: Write the Playwright test**

```ts
// dashboard/tests/watchlist.spec.ts
import { test, expect } from "@playwright/test";

test("save persists across reload with no network write", async ({ page }) => {
  const posts: string[] = [];
  page.on("request", (r) => { if (r.method() !== "GET") posts.push(r.url()); });
  await page.goto("/markets");
  const star = page.getByRole("button", { name: /save|watch/i }).first();
  await star.click();
  await page.reload();
  await expect(page.getByRole("button", { name: /saved|unwatch/i }).first()).toBeVisible();
  await page.goto("/watchlist");
  await expect(page.locator("table tbody tr")).toHaveCount(1);
  expect(posts, "no non-GET request on save/unsave").toEqual([]);
});
```

- [ ] **Step 5: Run** — `cd dashboard && npm run test:e2e` → PASS (both specs).
- [ ] **Step 6: Tick Task 14.8, commit, push**

```bash
git add dashboard tasks.md
git commit -m "add browser-local watchlist"
git push
```

---

## Self-review notes (author)

- **Spec coverage:** design language → Task 4/6/7; landing → Task 8; markets → 9; detail → 10; signals → 11; performance → 12; replay → 2+13; a11y/Playwright → 14; watchlist → 15; CORS + replay API adds → 1+2; demo DB → 3. All spec sections mapped.
- **Type consistency:** `Market`, `ModelPrediction`, `ArbitrageSignal`, `PaginatedSignals`, `Report`, `Replay`/`ReplayPoint` names match the API models (`MarketOut`, `ModelPredictionOut`, `ArbitrageSignalOut`, `PaginatedSignals`, `ReportOut`, `ReplayOut`).
- **Review Focus:** each of the seven items has an owning task + guard step noted above.
