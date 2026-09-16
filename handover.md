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

## Current status (as of this handover)

| Phase | Done | Model |
|---|---|---|
| 0 — Foundations | 5/6 (0.6 half-blocked, see below) | 🔵 Sonnet |
| 1 — Manifold Connectivity | 6/6 ✅ | 🔵 Sonnet |
| 2 — Probability State Engine | 7/7 ✅ | 🟣 Opus |
| 3 — Feature Engine | 4/4 ✅ | 🔵 Sonnet |
| 4 — Collector & Storage | 5/5 ✅ | 🔵 Sonnet |
| 5 — Latency Benchmark Harness | 0/4 — **next up** | 🟣 Opus |
| 6 — Performance Optimization | 0/4 | 🟣 Opus |
| 7 — Metaculus Adapter | 0/3 — blocked on Task 0.6 | 🔵 Sonnet |
| 8–16 | not started | mixed, see `tasks.md` |

**82 tasks total across 17 phases.** `tasks.md` checkboxes are the authoritative progress tracker
— always re-check them (`grep -n "Task X\." tasks.md`) rather than trusting this table if time has
passed, since it can go stale.

**One open action item that's yours, not Claude's**: Task 0.6's Metaculus half is blocked —
Claude can't verify their API/ToS because their site hard-blocks automated tools (Cloudflare
challenge). You need to sign up on metaculus.com in a real browser and check their API docs/terms
before Phase 7 can start. Details in `docs/metaculus-tos-check.md`.

## How to start a new session effectively

Open Claude Code in `/Users/ashiq/Documents/projects/Parallax` and say something like:

> "Continuing Parallax. Read implementation.md and tasks.md fully, check which tasks are done,
> and continue with the next unchecked task in Phase 5."

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
  force-add them, and don't be surprised they're not on GitHub.
- Some early commits in this repo's history don't build in perfect isolation (a couple of
  dependency-batching slips where a module was declared before its file existed in the same
  commit) — HEAD always builds; the intermediate history doesn't need to be pristine.

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
│   └── bench-harness/     # Phase 5, not started
├── research/               # Python package (uv), scaffolded, mostly unbuilt (Phase 7+)
├── api/                    # FastAPI, not started (Phase 13)
├── dashboard/               # Next.js, scaffolded with disclaimer banner only (Phase 14)
├── deploy/                  # systemd/launchd/nohup configs for the collector (done, Task 4.5)
└── docs/metaculus-tos-check.md   # the pending Metaculus verification note
```

## If something in this file conflicts with `implementation.md`/`tasks.md`

Trust those two files — this handover is a snapshot at a point in time and can go stale faster
than they do (they're actively maintained as part of the task workflow; this file is not).
