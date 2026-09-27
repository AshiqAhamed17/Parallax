# Parallax Public Dashboard — Design Spec (Phase 14)

- **Date:** 2026-09-27
- **Status:** Approved direction (pending spec review) → next step is `writing-plans`.
- **Scope:** Phase 14 of `tasks.md` (Tasks 14.1–14.8), plus two small enabling API additions.

## 1. Context & intent

The dashboard is the only public, human-visible surface of Parallax — the artifact that
communicates the whole project (low-latency Manifold ingestion, calibrated probability model,
logical-constraint arbitrage, cross-source divergence, latency benchmarks, backtests) to visitors,
recruiters, and users. It must read as a *serious, distinctive quant/low-latency product*, not a
templated or "AI-vibe" dashboard.

- **Who it's for:** the project owner (portfolio signal for quant-developer / low-latency-systems
  roles) and general read-only visitors. No accounts, no auth, no trading — ever (constraint §2.1).
- **Success looks like:** a visitor immediately understands what Parallax does, sees live-looking
  real data (markets, edges, signals, latency, P&L), and comes away feeling it's a polished,
  credible engineering project. Every page carries the honest disclaimer.

## 2. Design language

Dark-only. Tokens live as CSS variables in `globals.css` and are exposed to Tailwind v4 via
`@theme`.

**Color**
- Canvas `#0A0B0D` (cool near-black); elevated surfaces `#101216` / `#15181D`; hairline borders
  `rgba(255,255,255,0.06–0.10)`; radii 12–16px.
- Signature accent: **electric cyan `#22D3EE`** (+ sky `#38BDF8` for gradients), used sparingly —
  active states, focal numbers, links, primary chart lines.
- Semantic status (always a dot + rounded pill): crit `#F43F5E` · high `#FB923C` · med `#FACC15` ·
  low `#38BDF8` · ok/positive `#34D399`.

**Typography**
- **Geist Sans** for UI text; **Geist Mono** for ALL data — probabilities, edge/EV, hashes, IDs,
  timestamps, code, filenames. Both are already wired in the scaffold.
- `font-variant-numeric: tabular-nums` on all numbers so values don't jitter when they update.
- Big, bold, high-contrast headlines; muted gray (`#9CA3AF`-ish) body/subtext.

**Signature motifs (make it Parallax, not generic)**
- **Parallax depth** (on-brand with the name): layered accent-tinted radial glows and hero panels
  drift at different rates on scroll/pointer — subtle, GPU-cheap (transform/opacity only).
- **Live probability tape:** a horizontally scrolling monospace ticker of tracked markets +
  probabilities in the hero — instantly reads as a live system.
- **Freshness pulse:** a small cyan pulsing dot wherever data is "live," derived from
  `last_updated_ns`.
- **Edge bar:** a diverging market-prob ↔ model-prob bar with the edge span highlighted — the core
  quant story as one compact glyph. Reused in the markets table and market detail.

**Motion (rich/showy, but disciplined)**
- Staggered entrance fades/slides, animated sparkline path-draw, count-up number rolls on load/update,
  hover elevation on cards/rows, animated hero gradient, parallax on the hero layers.
- Library: `motion` (Framer Motion, React 19 compatible), client components only.
- **All motion respects `prefers-reduced-motion`** (reduce to instant/opacity-only).

**Accessibility**
- Contrast targets AA for text; status is never color-only (dot + text label). Focus-visible rings
  in cyan. Keyboard-navigable tables/tabs/dialogs (Radix primitives provide this).

## 3. Information architecture (routes → Phase-14 tasks)

- **`/` — Landing / Overview** *(part of 14.1)* — the front door. Hero (headline + subhead + CTAs +
  live probability tape + floating, parallaxing app-panel mockups showing real seeded rows) → bento
  grid of live stat cards (markets tracked, top model edges, latest signals, latency p50/p99,
  backtest P&L) → honest disclaimer. This is the primary "wow" surface.
- **App shell** *(14.1)* — persistent top bar (logo, nav, live status indicator) and the
  **disclaimer banner on every route**. Nav: Overview · Markets · Signals · Performance.
- **`/markets`** *(14.2)* — flagship data table: question · market prob · model prob · **edge bar** ·
  EV pill · probability sparkline · freshness pulse. Client-side sort/filter/search.
- **`/markets/[id]`** *(14.3, real dynamic route)* — probability-over-time chart, edge/EV panel,
  live signal state for the market, metadata (close time, volume, resolution). The URL is what makes
  a market shareable (14.8 depends on this).
- **`/signals`** *(14.4)* — tabbed: Logical-constraint | Cross-source divergence, from `/arbitrage`,
  paginated. Divergence tab explicitly labeled "market vs. independent forecast — not tradeable
  arbitrage." Each card: severity dot+pill, mono market refs, `details_json` rendered as a clean
  key/value strip, edge in mono.
- **`/performance`** *(14.5)* — latency histogram (p50/p95/p99/p99.9), P&L curve, reliability
  diagram, rendered from `/benchmarks` and `/backtests`. Charts follow the `dataviz` skill.
- **Replay control** *(14.6)* — a scrub control on `/markets/[id]` that replays stored
  probability/bet history; backed by a new `GET /markets/{id}/replay` API endpoint.
- **Responsive + a11y pass + Playwright smoke test** *(14.7)*.
- **Browser-local watchlist** *(14.8)* — a save/star toggle on market rows and the detail page,
  persisted in `localStorage` only (no backend, no network on save/unsave), plus a "My Watchlist"
  filter view.

## 4. Data & integration

- **API client:** typed `lib/api.ts` hitting the FastAPI backend at `NEXT_PUBLIC_API_URL`
  (default `http://localhost:8000`). Prefer React Server Components for data fetching; use client
  components only where interactivity/motion requires it. `lib/types.ts` mirrors the API response
  models (`MarketOut`, `PaginatedSignals`, `ArbitrageSignalOut`, `ReportOut`, replay shape).
- **Demo data (dev):** a committed `research/scripts/seed_demo_db.py` writes a realistic
  `data/parallax-demo.db` — a set of markets with plausible questions, multi-point probability
  history (so sparklines/charts have shape), model predictions (edge/EV), and both signal types.
  Run the API with `PARALLAX_DB=data/parallax-demo.db`. This makes the dashboard look alive offline;
  the live collector API replaces it in Phase 15. The seed data is clearly demo-labeled.
- **Enabling API additions (this phase):**
  1. **CORS middleware** on the FastAPI app so the Next dev origin (`http://localhost:3000`) and the
     eventual deployed dashboard origin can call it. Configurable allowed origins.
  2. **`GET /markets/{id}/replay`** returning ordered probability/bet history for a market (backs
     14.6). Read-only, reuses the storage contract.
  Both get their own tests in the `research` suite and keep `uv run ruff`/`pytest` green.

## 5. Component inventory

- **shadcn/ui primitives** (custom-themed to our tokens, must NOT read as default shadcn): table,
  tabs, dialog, tooltip, dropdown/select, button, badge, skeleton, scroll-area.
- **Bespoke components:** `DisclaimerBanner` (exists — restyle), `TopNav`, `StatusPill`, `EdgeBar`,
  `Sparkline` (hand-rolled animated SVG), `ProbTape` (hero ticker), `StatCard`, `FloatingPanel`
  (parallax hero mockup), `SignalCard`, `MarketRow`, `ReplayScrubber`, `WatchlistToggle`.
- Charts: **Recharts 3** for latency histogram / P&L curve / reliability; hand-rolled SVG for
  sparklines and edge bars (crisp, animatable path-draw).

## 6. Tech stack additions

- `shadcn/ui` (+ its Radix deps), `motion` (Framer Motion), `recharts@3`.
- Tailwind v4 theme extended with the token set. Fonts already present (Geist Sans/Mono).
- `@playwright/test` for the 14.7 smoke test.

## 7. Testing strategy

- **Playwright smoke (14.7):** homepage loads with the disclaimer visible and at least one market
  row rendered; runs in CI.
- **Watchlist (14.8):** component/Playwright test — save a market, reload, still saved and in the
  watchlist view; unsaved market absent; **assert no network request fires on save/unsave** (verify
  via request log, not code review).
- **API additions:** pytest coverage for CORS behavior and the replay endpoint in the `research`
  suite.
- Frontend CI (`.github/workflows/frontend.yml`) lints + builds; extend to run the Playwright smoke.

## 8. Non-goals / out of scope

- No auth, accounts, user state on a server, or any write/bet endpoint (constraint §2.1).
- No live production deployment (that's Phase 15); dev runs against the seeded demo DB.
- No real-time WebSocket push to the browser this phase — periodic fetch / server render is enough;
  the "live" feel comes from freshness indicators and motion, not a socket.

## 9. Resolved decisions (from brainstorming)

- Accent: **electric cyan** on cool near-black. Motion: **rich/showy** (reduced-motion honored).
- Components: **shadcn/ui, custom-themed**. Dev data: **seeded demo DB**.
- A **landing/overview `/`** is the front door (confirmed), not app-only-from-`/markets`.

## 10. Success criteria (checklist)

- Distinctive, cohesive cyan-on-near-black system across every page; no default-template look.
- Disclaimer visible on every route.
- Real (seeded) data throughout — markets, edges, signals, latency, P&L — no empty states in the demo.
- Rich but performant motion, `prefers-reduced-motion` respected.
- Responsive down to mobile; Playwright smoke green in CI.
- All eight Phase-14 tasks satisfied with their `tasks.md` acceptance criteria and commit messages.
