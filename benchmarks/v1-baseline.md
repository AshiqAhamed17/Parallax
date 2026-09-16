# Parallax — v1 Latency Baseline

Baseline performance numbers for the ingestion pipeline, measured **before** any Phase 6
optimization work. This is the reference point every later benchmark (v2/v3) is compared against.
All numbers here come from real instrumented runs — nothing is estimated (constraint §2.3).

## Environment

- Machine: Apple Silicon macOS (Darwin), release build (`--release`, `opt-level=3`).
- Toolchain: `cargo 1.96.0`.
- Storage for the pipeline test: in-memory SQLite (so the storage-write stage measures the insert
  code path, not physical disk latency — see `implementation.md` §13). Reproducible across machines.

Reproduce everything below with:

```bash
cargo bench -p bench-harness
cargo run --release -p bench-harness -- --rate 5000 --count 50000 --num-markets 16 --seed 42
```

---

## 1. End-to-end pipeline latency (per stage)

Synthetic load driven through the real `collector` pipeline (`run_ingest_loop` → bounded channel →
`run_writer_loop`) with per-stage `quanta` timing on. Latencies in **microseconds**.

Command:

```bash
cargo run --release -p bench-harness -- --rate 5000 --count 50000 --num-markets 16 --seed 42
```

- Requested rate: 5000.0 events/s — Achieved: **4999.8 events/s** over 10.000s
- Events: 50000 (all fully recorded across all four stages, 0 skipped)
- Markets: 16 · Seed: 42 · Feature window: 60s

| Segment | Count | p50 | p95 | p99 | p99.9 | max | mean |
|---|---:|---:|---:|---:|---:|---:|---:|
| ws_receive → state_update | 50000 | 0.375 | 0.833 | 1.226 | 6.503 | 198.015 | 0.437 |
| state_update → feature_calc | 50000 | 37.823 | 79.423 | 92.095 | 553.983 | 17465.343 | 45.422 |
| feature_calc → storage_write | 50000 | 225.791 | 843.263 | 6045.695 | 25001.983 | 84344.831 | 451.963 |
| total (ws_receive → storage_write) | 50000 | 270.591 | 901.631 | 6111.231 | 25100.287 | 84344.831 | 497.818 |

**Reading the numbers.** The `ws→state` hop (wire→domain conversion + `MarketState` update) is
sub-microsecond at the median. The bulk of end-to-end latency lives after feature calc, in the
`feature→storage` hop — the bounded-channel handoff plus the SQLite insert, whose tail
(p99 ≈ 6ms, max ≈ 84ms) reflects writer-side queuing under sustained 5k/s load. That makes the
writer path the obvious first target for Phase 6.

---

## 2. Criterion micro-benchmarks (isolated hot-path compute)

These isolate the pure compute the end-to-end test can't separate from channel/storage cost.
512-event window = the collector's default per-market history capacity.

Command:

```bash
cargo bench -p bench-harness
```

| Benchmark | Median (est.) |
|---|---:|
| `MarketState::apply` (single) | 973.09 ps |
| `prob_velocity` / 512 events | 508.63 ns |
| `bet_arrival_rate` / 512 events | 72.79 ns |
| `realized_volatility` / 512 events | 787.46 ns |
| `compute_snapshot` / 512 events | 9.244 µs |

**Reading the numbers.** A single `MarketState::apply` is sub-nanosecond (two field writes). The
feature calcs are tens-to-hundreds of nanoseconds each; `compute_snapshot` (which runs all three
over the window plus assembles the snapshot) is ~9µs on a full 512-event history — consistent with
the pipeline's `state→feature` segment being dominated by feature computation.
