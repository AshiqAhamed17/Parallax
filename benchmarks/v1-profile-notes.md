# Parallax — v1 Profiling Notes

CPU profile of the ingestion pipeline under `bench-harness` load, taken on the same v1 code as
`benchmarks/v1-baseline.md`. This identifies *where the CPU goes* so Phase 6.2 can target the
hottest path. All numbers below come from a real profiled run — nothing is estimated
(constraint §2.3).

## Method

`perf` and `cargo flamegraph` are Linux-oriented and unavailable here (macOS/Darwin; `perf` doesn't
exist, `dtrace` needs privileges this environment can't grant non-interactively). Instead this uses
**samply** (a cross-platform sampling profiler that launches the process itself — no `sudo`) plus
`atos` for symbolication.

Build the profiled binary with debug symbols retained in release, then record:

```bash
CARGO_PROFILE_RELEASE_DEBUG=2 cargo build --release -p bench-harness
samply record -s -o profile.json.gz -r 2000 -- \
  ./target/release/bench-harness --rate 0 --count 700000 --num-markets 16 --seed 42
```

- `--rate 0` (unpaced) saturates the CPU so the sampler captures real hot code rather than idle
  time between paced events.
- Sampling: 2000 Hz, ~64,000 samples across all threads over a ~10s run. Self-CPU is weighted by
  each sample's `threadCPUDelta` (µs), so blocked/sleeping threads don't distort the ranking.
- Symbolication: `atos -o target/release/bench-harness -l 0x100000000 <vmaddr>` for our binary
  (which statically links the collector, SQLite via `rusqlite` bundled, and Tokio);
  `atos -o /usr/lib/system/libsystem_kernel.dylib` for kernel frames.

## Measured self-CPU by module

| Module | Self-CPU | What it is |
|---|---:|---|
| `bench-harness` (our code + static SQLite/Tokio) | 35.5% | generator, pipeline, feature math, `String` clones |
| `libsystem_malloc` | 32.8% | `malloc`/`free`/`realloc` — heap allocation |
| `libsystem_kernel` | 18.5% | syscalls: `mach_vm_protect` (allocator page churn), `__psynch_rw_unlock` (lock contention) |
| `libsystem_platform` | 11.6% | `memmove`/`memset` — buffer copies |
| pthread / libc / dyld | 1.6% | misc |

Top symbolicated frames (self-CPU, CPU-weighted): `mach_vm_protect` (12.1%, called from the
allocator), `__psynch_rw_unlock` (3.2%, lock contention), then a long tail of `malloc`-family
frames, `<String as Clone>::clone`, `__rdl_alloc`, `free`, `memcpy`, and — the largest pure-compute
frames of our own code — `feature_engine::compute_snapshot`, `prob_velocity`, and
`realized_volatility` (~2.3% combined).

The story is unambiguous: **the pipeline is allocation-bound.** Allocation itself (`malloc` 32.8%)
plus the allocator's kernel page-protection churn (`mach_vm_protect`, most of the 12.1% top frame)
plus the `memmove`/`memset` that accompanies it together dwarf the actual arithmetic.

## Top 3 hotspots (Phase 6.2 targets)

1. **Heap-allocation churn — the dominant cost (`malloc` 32.8% + allocator kernel/`memcpy` time).**
   The hot path allocates and clones a `String` per bet: `From<&manifold_client::Bet> for
   BetEvent` clones `contract_id` into `market_id`, and `run_ingest_loop` then does
   `domain.clone()` for every bet (`crates/collector/src/ingest.rs`) so it can both drive the
   engine and send the record. Cutting per-event allocation (e.g. avoid the `domain.clone()`; share
   the market id as `Arc<str>`; reuse buffers) is the single biggest lever.
   *Caveat:* the synthetic generator's per-event `format!("synthetic-…")` also allocates two strings
   per event and is **bench-only** — it inflates the absolute `malloc` share versus production,
   where the equivalent allocations come from serde JSON parsing of WS frames. The pipeline-side
   clones, however, are production-real and are the actionable target.

2. **SQLite write path — 4 un-cached `execute`s per record.** `write_record`
   (`crates/collector/src/ingest.rs`) calls `conn.execute(...)` four times per bet (markets,
   bets, probability_snapshots, feature_snapshots), each of which re-prepares its SQL statement and
   takes the SQLite mutex — visible as the kernel `__psynch_rw_unlock` contention (3.2%) and part of
   the `memmove` cost. This is the same segment the v1 baseline flagged: `feature→storage` carries
   the latency tail (p99 ≈ 6ms, max ≈ 84ms). Prepared-statement caching (`prepare_cached`) and
   batching inserts inside a transaction are the fix.

3. **Feature recomputation — largest pure-compute slice of our code (~2.3%).**
   `compute_snapshot` runs `prob_velocity` + `bet_arrival_rate` + `realized_volatility`, each
   independently scanning the rolling window (up to 512 events) on every bet. It's an order of
   magnitude below the allocation cost, so it's a *secondary* target — worth a single-pass
   rewrite only after (1) and (2) are addressed.

## Caveats

- Storage is in-memory SQLite (reproducibility; see `implementation.md` §13), so this understates
  real disk-write cost but faithfully captures the statement-preparation and locking overhead.
- Exact kernel-frame symbol names are approximate: the on-disk `libsystem_kernel.dylib` offsets can
  drift slightly from the running dyld-shared-cache copy. The **module-level** split (kernel 18.5%)
  and the primary frame (`mach_vm_protect`) are reliable; treat secondary kernel symbol names as
  indicative.
- The unpaced (`--rate 0`) run maximizes CPU signal; under the paced 5k/s baseline the same
  hotspots apply but wall-clock is dominated by inter-event waiting.
