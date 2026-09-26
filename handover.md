# Parallax — Session Handover

Read this first in a new session, then read `implementation.md` and `tasks.md` in full before
writing any code. This file is the orientation layer; those two are the actual source of truth.

## What Parallax is (one paragraph)

A low-latency Rust pipeline watches Manifold Markets' live bet stream, maintains a per-market
probability state, and builds an independent calibrated probability estimate to compare against
the market. It detects logical-constraint arbitrage across correlated Manifold markets (the
centerpiece) and a Manifold-vs-Metaculus divergence panel (a second opinion, not tradeable
arbitrage). A realistic backtester validates everything before it's trusted. Results show on a
public, read-only dashboard — no accounts, no order execution, ever. Goal: portfolio project
signaling quant-developer/low-latency-systems skill (not a trading bot, not a Web3 project).

## Where everything lives

- **Repo**: `/Users/ashiq/Documents/projects/Parallax` — GitHub: `AshiqAhamed17/Parallax` (private)
- **`implementation.md`** and **`tasks.md`** — in the repo root, **gitignored, local-only, not on
  GitHub**. If you're on a different machine, these need to be recreated or copied over manually —
  they are not recoverable from `git clone`.
- **Original design plan** (superseded, kept for history): `/Users/ashiq/.claude/plans/hey-i-m-going-to-atomic-ullman.md`
- **Ashiq's background/career context**: `/Users/ashiq/Documents/projects/Ashiq/` (resume,
  dream-companies list, project-ideas.md, project-6-explained.md)

## Current status (as of this handover — updated mid-Phase-12)

| Phase | Done | Model |
|---|---|---|
| 0 — Foundations | 6/6 ✅ (0.6 resolved via the Polymarket pivot — see below) | 🔵 Sonnet |
| 1 — Manifold Connectivity | 6/6 ✅ | 🔵 Sonnet |
| 2 — Probability State Engine | 7/7 ✅ | 🟣 Opus |
| 3 — Feature Engine | 4/4 ✅ | 🔵 Sonnet |
| 4 — Collector & Storage | 5/5 ✅ | 🔵 Sonnet |
| 5 — Latency Benchmark Harness | 4/4 ✅ | 🟣 Opus |
| 6 — Performance Optimization | 4/4 ✅ | 🟣 Opus |
| 7 — Second-Source (Polymarket) Adapter | 3/3 ✅ (pivoted from Metaculus) | 🔵 Sonnet |
| 8 — Market Matching Layer | 5/5 ✅ | 🟣 Opus |
| 9 — Cross-Source Divergence | 3/3 ✅ | 🔵 Sonnet |
| 10 — Calibration & Probability Model | 5/5 ✅ | 🟣 Opus |
| 11 — Backtester | 5/5 ✅ | 🟣 Opus |
| 12 — Logical-Constraint Arbitrage | 4/4 ✅ | 🟣 Opus |
| 13 — Public API Layer | 2/5 — **13.1, 13.2 done; 13.3 next up** | 🔵 Sonnet (done on Opus per request) |
| 14–16 | not started | mixed, see `tasks.md` |

**Phase 12 complete. Phase 13 in progress (13.1/13.2 done). Next up: Task 13.3 (arbitrage/divergence
endpoint).** Note: the FastAPI app lives in `research/src/parallax_research/api/` (so it's covered by
the single `uv run ruff`/`pytest` from `research/`); `api/main.py` at repo root is a thin
`uvicorn api.main:app` shim. `fastapi`+`uvicorn` are now deps in `research/pyproject.toml`.

`tasks.md` checkboxes are the authoritative progress tracker — always re-check them
(`grep -n "^- \[.\] \*\*Task" tasks.md`) rather than trusting this table.

**Task 0.6 is RESOLVED (no longer your action item).** The Metaculus half was blocked (Cloudflare
bot-challenge), so it was verified in a browser and **rejected** — Metaculus's ToU forbids AI/ML use
+ public redistribution of its data. The second source **pivoted to Polymarket**, whose public API
is open and whose ToU permits non-commercial informational use. See `implementation.md` §15 and
`docs/metaculus-tos-check.md`. No open human action items remain.

## How to start a new session effectively

Open Claude Code in `/Users/ashiq/Documents/projects/Parallax` and say something like:

> "Continuing Parallax. Read handover.md, implementation.md, and tasks.md fully, check which tasks
> are done, and continue with the next unchecked task in Phase 12 (12.2). Keep using Opus."

Claude should then, per-task, follow the pattern used throughout this project so far:
1. Read the exact task spec in `tasks.md` (and any referenced section of `implementation.md`).
2. Implement it.
3. **Verify against reality, not assumptions** — this project's single biggest recurring lesson.
   Several "obviously true" assumptions turned out wrong when actually checked (Manifold's WS
   supposedly "needing" a keepalive ping — false; Kalshi/Polymarket accessibility from India —
   more nuanced than first assumed; Metaculus's API shape — still unverified). Before writing code
   against an external API, hit it directly with `curl` or a throwaway script first.
4. Write real tests, run them, run `cargo clippy --workspace --all-targets -- -D warnings` and
   `cargo build --workspace` / `cargo test --workspace` — the whole workspace must stay green, not
   just the crate being touched.
5. For anything with a "run against live Manifold" acceptance criterion, actually do that — don't
   mark it done on unit tests alone.
6. Mark the task `[x]` in `tasks.md` with a short note on anything non-obvious that came up.
7. Commit with a **short, plain, human-style message, no AI attribution** (e.g. `add sqlite schema
   migration`, not a multi-paragraph explanation) — this is an explicit, saved preference. Push.
8. If a task's premise turns out wrong once you actually build it (this has happened several
   times), don't force it — fix the design, document the correction in `implementation.md`, note
   it in `tasks.md`, and proceed. This project treats course-correction as normal, not a failure.

## Model routing

`tasks.md` tags every phase 🔵 Sonnet or 🟣 Opus (see its "Model Legend" section for the
rationale). Switch models with `/model` to match the phase you're working on — Opus for
correctness-critical work (concurrency, latency methodology, statistical/calibration correctness,
look-ahead-bias risk), Sonnet for well-specified integration/mechanical/UI work.

## Known operational gotchas

- **GitHub CLI account drifts.** The active `gh` account randomly switches to `ashiq-b` between
  sessions (probably from other work on this machine). Always run `gh auth status` before
  pushing; if the active account isn't `AshiqAhamed17`, run:
  `gh auth switch --user AshiqAhamed17 && gh auth setup-git`
- **`implementation.md`/`tasks.md` are gitignored on purpose** (Ashiq's choice) — don't try to
  force-add them, and don't be surprised they're not on GitHub. **`learn/` is also gitignored** —
  local-only study notes (docs 01–03 written: what-is-parallax, architecture, prediction-markets).
- Some early commits in this repo's history don't build in perfect isolation (a couple of
  dependency-batching slips where a module was declared before its file existed in the same
  commit) — HEAD always builds; the intermediate history doesn't need to be pristine.

## What's built + how to verify (as of mid-Phase-12)

- **Rust side (Phases 0–6): DONE.** `cargo test --workspace` + `cargo clippy --workspace
  --all-targets -- -D warnings` are green. Perf: v1→v3 optimization gave +175% throughput (70k→194k
  ev/s), tail 84ms→3.1ms; numbers in `benchmarks/`. The Phase 2.6 differential proptest
  (`PROPTEST_CASES=10000 cargo test -p probability-engine differential`) is the correctness gate for
  any hot-path change.
- **Python research side (Phases 7–11 + 12.1): DONE.** Run from `research/`: `uv run ruff check .`
  and `uv run pytest` — currently **138 tests, all green**. Package: `research/src/parallax_research/`
  = `schemas.py`, `storage.py` (all table DDLs + `ensure_schema`), `adapters/` (polymarket + poller),
  `matching/` (repository, mapping_loader, fuzzy_match, review), `arbitrage/`
  (cross_source_divergence, scheduler, **constraints.py** = 12.1), `calibration/` (dataset, model,
  scoring, run, edge), `backtester/` (replay, fill, execution, pnl). Committed reports in `reports/`
  (calibration-v1, backtest-synthetic, backtest-validation).
- **Known data gap (recurring caveat):** the Rust collector doesn't yet backfill Manifold market
  question-text or resolution (Task 4.2 note), so there's no real resolved-Manifold dataset in the
  DB yet. Phases 8.4 / 9.3 / 10.4 / 11.4 were therefore demonstrated on clearly-labeled synthetic or
  seeded data, EXCEPT 11.5 which validated the backtester against a **real** resolved Manifold market
  fetched live (`reports/backtest-validation.md`, PASS). This gap doesn't block Phase 12.

## Repository layout (Rust workspace + Python + Next.js)

```
Parallax/
├── implementation.md, tasks.md   # gitignored, local-only — the real source of truth
├── handover.md                    # this file
├── Cargo.toml                     # Rust workspace
├── crates/
│   ├── common/            # BetEvent, MarketState — shared domain types
│   ├── manifold-client/   # REST + WS client for Manifold (done, Phase 1)
│   ├── probability-engine/# MarketTracker, ProbabilityEngine, BetHistory (done, Phase 2)
│   ├── feature-engine/    # prob_velocity, bet_arrival_rate, realized_volatility (done, Phase 3)
│   ├── collector/         # the real ingestion binary — migration/ingest/archive/health (done, Phase 4)
│   └── bench-harness/     # synthetic load gen + latency harness + criterion (done, Phases 5–6)
├── research/               # Python package (uv) — Phases 7–11 + 12.1 DONE (see "What's built" above)
├── api/                    # FastAPI, not started (Phase 13)
├── dashboard/               # Next.js, scaffolded with disclaimer banner only (Phase 14)
├── deploy/                  # systemd/launchd/nohup configs for the collector (done, Task 4.5)
└── docs/metaculus-tos-check.md   # the pending Metaculus verification note
```

## If something in this file conflicts with `implementation.md`/`tasks.md`

Trust those two files — this handover is a snapshot at a point in time and can go stale faster
than they do (they're actively maintained as part of the task workflow; this file is not).
