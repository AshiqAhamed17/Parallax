# Parallax — Latency Optimization Report (v1 → v2 → v3)

The full story of the Phase 5–6 performance work: how the ingestion pipeline was measured,
profiled, and optimized, with real numbers at every step. Nothing here is estimated — every figure
comes from an instrumented run reproducible with the command shown (constraint §2.3). Detailed
per-version data lives in `v1-baseline.md`, `v1-profile-notes.md`, `v2-results.md`, and
`v3-results.md`; this report is the summary and the rationale for where we stopped.

## The pipeline

One bet flows: **WS receive → state update → feature calc → storage write**. The first three are
the *latency-critical signal path* (they produce the probability/feature signal). The fourth is an
*async persistence path* running in a separate task behind a bounded channel — the signal path
never blocks on it. Per-stage latency is measured with `quanta` timestamps (Task 5.1); load is
generated synthetically (Task 5.2) and pushed through the **real** collector pipeline (Task 5.3).

## Headline results

**Max sustained throughput (unpaced, `--rate 0 --count 300000`)** — the clean, reproducible
capacity metric:

| | v1 | v2 | v3 |
|---|---:|---:|---:|
| throughput | 70,586 ev/s | 110,297 ev/s | 194,444 ev/s |
| vs v1 | — | +56% | **+175%** |

**Compute hot path (criterion medians):**

| Benchmark | v1 | v2 (=v3) | speedup |
|---|---:|---:|---:|
| `prob_velocity` / 512 | 508.63 ns | 4.01 ns | ~127× |
| `bet_arrival_rate` / 512 | 72.79 ns | 3.85 ns | ~19× |
| `compute_snapshot` / 512 | 9,244 ns | 570 ns | ~16× |
| `realized_volatility` / 512 | 787.46 ns | 228.23 ns | ~3.4× |
| `MarketState::apply` | 973 ps | 954 ps | ~1× (already minimal) |

**End-to-end latency, paced 5k ev/s (total segment):** p50 270.6µs → 38.3µs → 94.2µs; max 84.3ms →
4.6ms → 3.1ms. (v3's paced p50 rise is a Tokio-scheduling artifact at this load, not a real
regression — see below.)

## What changed at each step

**v1 → profile (Task 6.1).** Sampling profile (samply + `atos`, since macOS has no `perf`) of an
unpaced run showed the pipeline was **allocation-bound**: `malloc` 32.8% of CPU, allocator page
churn (`mach_vm_protect`) 12%, `memmove` 11.6% — together dwarfing the arithmetic. Root causes: a
`String` allocated/cloned per bet, and — the big one — `compute_snapshot` cloning the entire ≤512-
event window (each with a `String`) on *every* bet.

**v2 (Task 6.2) — eliminate per-event allocation.** Introduced `common::BetSample` (a `Copy`,
`market_id`-free view); `BetHistory` stores samples so ring-buffer pushes are allocation-free;
`compute_snapshot` linearizes into one POD `Vec<BetSample>` instead of cloning `String`-bearing
events; `ProbabilityEngine::apply` stopped cloning the map key every bet; the feature calcs window
via `partition_point` (O(log n)) instead of an O(n) filter-into-`Vec`. Result: throughput +56%,
compute-path latency down 3–127×, and — because allocator contention fell across the whole process
— even the unchanged storage stage got ~6× faster at p50 and the worst-case tail dropped ~18×.

**v3 (Task 6.4) — writer statement-caching + per-record transaction.** After v2 the remaining cost
was the SQLite write path. `write_record` now uses `prepare_cached` statements inside one
per-record `unchecked_transaction` (four fresh compiles + four autocommits → one commit reusing
cached statements). Result: unpaced throughput +76% (110k → 194k ev/s) and a tighter max tail.

## Why we stop here — the practical floor

- **The latency-critical signal path is at its floor.** `ws→state→feature` is allocation-free and
  sub-10µs; `MarketState::apply` is two field writes (~1ns) and the feature calcs are single-pass
  O(log n)-windowed. There is no meaningful allocation or redundant work left to remove on this
  path.
- **The remaining end-to-end cost is the async writer, and it is not a bottleneck.** It sits behind
  a bounded channel, off the signal path, and v3 lifted its saturated throughput to ~194k ev/s.
  Live Manifold emits ~1–2 bets/s (Task 4.4) — five orders of magnitude below capacity — so no
  production workload will ever queue on it.
- **The paced-5k latency metric is scheduling-dominated, not work-dominated.** At that rate the
  writer is near-idle and per-record latency is set by how the ingest and writer Tokio tasks
  interleave, not by SQL: making the writer *faster* in v3 did not lower the segment, and even
  unchanged compute stages read differently run-to-run. Chasing it further would be tuning runtime
  scheduling noise, not the pipeline.
- **The obvious next writer lever — batching many records per transaction — is deliberately
  declined.** It would trade per-record durability and low-load latency for throughput the system
  provably does not need (see the ~1–2 ev/s real rate). For an observe-only collector where every
  gap is lost history, committing each record as it arrives is the right default.

**Bottom line:** v2 is the floor for the latency-critical path (the project's actual "low-latency"
story); v3 is the floor for writer throughput that's worth reaching. Net over the campaign:
**+175% throughput, compute-path latency down 16–127×, worst-case end-to-end tail 84ms → 3.1ms
(~27×)** — all correctness-gated by the Phase 2.6 differential proptest at `PROPTEST_CASES=10000`.
