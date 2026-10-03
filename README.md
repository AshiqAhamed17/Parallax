# Parallax

> **Parallax** *(n.)* — the apparent shift in an object's position when viewed from two vantage points.

A low-latency pipeline that watches a live prediction-market bet stream, maintains a calibrated
probability for every market in real time, and flags two kinds of mispricing — **logical-constraint
violations** across related markets and **cross-source divergence** between venues. It observes and
reports; it **never places a trade**.

This is a research-and-engineering portfolio project, not a trading product.

- **Full documentation:** the dashboard serves a docs site at **`/docs`** (Introduction →
  Architecture → Data pipeline → Model → Signals → API → Running it).
- **Read-only & honest:** every figure on the dashboard comes from a real measured run or real market
  data. Where the model loses to the market, we say so (see [The model](#the-model-is-honest)).

---

## What it does

- Ingests Manifold Markets' live WebSocket bet stream in a **Rust** pipeline and keeps each market's
  probability, recent history, and derived features up to date per bet.
- Reconstructs real prices and features for a **curated set of ~50 liquid markets** across politics,
  tech/AI, crypto, macro, sports, and culture.
- Trains a **calibrated probability model** on real resolved markets and compares it to the market
  price — reported with honest Brier/log-loss, not a fabricated edge.
- Runs two detectors: **logical-constraint** arbitrage over correlated market ladders, and
  **cross-source divergence** between Manifold and Polymarket on hand-verified same-event pairs.
- Serves it all through a read-only **FastAPI** backend and a **Next.js** dashboard.

---

## Highlights

- **Measured low-latency Rust pipeline.** The hot path (WS receive → state update → feature calc →
  storage) is instrumented per stage and benchmarked — **~175% throughput improvement** (70k → 194k
  events/s) from profiling-driven optimization (killing per-event heap allocation, caching SQL
  statements). Numbers are reproducible, not claimed. See `/docs/architecture` and
  `benchmarks/latency-report.md`.
- **Real data, end to end.** No demo placeholders on the public dashboard — real Manifold prices,
  real model predictions, real signals.
- **Intellectually honest.** The calibration model is measured against the market's own price and the
  result is published even though the market wins. No invented alpha.
- **Clean two-language architecture.** Rust owns the latency-critical hot path; Python owns the
  research/stats; they integrate through a shared SQLite store, not RPC.

---

## Architecture

```
                   ┌──────────────── RUST (hot path) ────────────────┐
 Manifold WS ────▶ collector ─▶ probability-engine ─▶ feature-engine ─▶ SQLite
 (live bets)       (ingest)     (current prob)        (velocity, vol)   (storage)
                   └──────────────────────────────────────────────────┘
                                                                          │  shared file
 Polymarket REST ─────────────────────────────────────▶ PYTHON research ◀┘
 (periodic poll)                                         (backfill, model, detectors)
                                                                  │
                                                                  ▼
                                                   FastAPI  ──▶  Next.js dashboard  (read-only)
```

The Rust half is optimized for speed; the Python half for statistics. They meet only at the storage
layer. Full detail in `/docs/architecture`.

---

## Repository layout

```
Parallax/
├── crates/                 # Rust workspace (the low-latency pipeline)
│   ├── common/             #   shared domain types (BetEvent, BetSample, StageTimer)
│   ├── manifold-client/    #   Manifold REST + WebSocket client
│   ├── probability-engine/ #   per-market probability + ring-buffer history
│   ├── feature-engine/     #   velocity / arrival-rate / realized-volatility features
│   ├── collector/          #   the always-on binary (ingest + writer tasks, SQLite)
│   └── bench-harness/      #   load generator + HDR-histogram latency report
├── research/               # Python package (uv) — research + API
│   ├── src/parallax_research/
│   │   ├── adapters/       #   Manifold + Polymarket REST adapters, poller
│   │   ├── ingest/         #   curated registry, bet-history backfill, model training, detectors
│   │   ├── calibration/    #   dataset, baseline model, edge/EV, scoring
│   │   ├── arbitrage/      #   logical-constraint + cross-source divergence detectors
│   │   ├── matching/       #   Manifold↔Polymarket market matching
│   │   └── api/            #   FastAPI app (read-only)
│   ├── config/             #   curated groups + cross-source match configs
│   └── scripts/            #   build_live_db.py (the data pipeline), seed_demo_db.py
├── dashboard/              # Next.js 16 app (the public dashboard + /docs)
├── deploy/                 # run/refresh scripts, systemd/launchd units
├── benchmarks/ reports/    # committed measured latency + calibration/backtest reports
└── data/                   # SQLite databases (gitignored)
```

---

## Tech stack

| Layer | Tech |
|---|---|
| Hot-path pipeline | Rust, Tokio (async), `rusqlite` (SQLite), `quanta` + `hdrhistogram` (latency) |
| Research / data | Python 3.12, `uv`, `httpx`, `pandas`, `scikit-learn` |
| API | FastAPI (read-only), SQLite |
| Dashboard | Next.js 16 (App Router), React 19, Tailwind v4, `motion` |
| Data sources | Manifold Markets (WS + REST), Polymarket (Gamma REST) |

---

## Quickstart (run locally)

**Prerequisites:** Rust (stable), [`uv`](https://docs.astral.sh/uv/), Node 20+.

```bash
# 1. Build the real data DB from live Manifold + Polymarket data (~5 min; needs network)
cd research && uv sync
uv run python scripts/build_live_db.py --db ../data/parallax-live.db
cd ..

# 2. Serve the read-only API against that DB
./deploy/run_api.sh                      # -> http://127.0.0.1:8000  (interactive OpenAPI at /docs)

# 3. Run the dashboard (in another terminal)
cd dashboard && npm install && npm run build && npm start   # -> http://127.0.0.1:3000
```

The dashboard reads `NEXT_PUBLIC_API_URL` (defaults to `http://127.0.0.1:8000`).

**Optional — the live Rust collector** (true 24/7 WS streaming, for the latency story and benchmarks):

```bash
cargo build --release
./deploy/run_collector.sh                # streams Manifold bets into data/parallax.db
cargo run -p bench-harness -- --rate 0   # reproduce the latency/throughput report
```

Refresh the live data on a schedule with `./deploy/refresh_live_db.sh` (cron-friendly).

---

## The model is honest

Parallax trains a logistic-regression calibration baseline on real resolved Manifold markets and
scores it on a held-out set against the market's own implied price. **The market is currently better
calibrated than the model** (lower Brier). We publish this on the dashboard's Performance page rather
than hide it. The per-market "edge" shown is the model's *disagreement* with the price — useful for
spotting where model and market diverge, **not** a profit guarantee. Pretending otherwise would be
the dishonest move.

---

## Data, safety & compliance

- **Observe-only.** No order-execution code exists anywhere in the repo. Parallax never trades.
- **Real numbers.** Benchmarks come from instrumented runs; prices and signals come from live market
  data.
- **Curated, not firehose.** The dashboard tracks a hand-picked set of liquid markets; cross-source
  signals fire only on hand-verified same-event pairs.
- **Respectful polling.** Polymarket is polled gently (read-only public API).

---

## Project status

Core pipeline, research layer, API, and dashboard are complete and run on real data. Remaining work
is **deployment** (hosting the API + dashboard) and **final documentation polish**. See `tasks.md`
for the full breakdown (local-only).

---

## Disclaimer

Parallax is a personal research and engineering project. It is **not** financial advice, not a
trading product, and places no orders. Market data belongs to its respective platforms (Manifold,
Polymarket) and is used here for informational, non-commercial purposes only.
