# Parallax — v2 Benchmark Results (post allocation-cut)

Re-run of the v1 measurements after Task 6.2's optimization (store `Copy` `BetSample`s in the ring
buffer; stop cloning the window in `compute_snapshot`; drop the per-bet `entry()` key clone;
window the feature calcs with `partition_point`). Same machine, same commands, same seed — the only
variable is the code. All numbers are measured, not estimated (constraint §2.3).

Reproduce:

```bash
cargo bench -p bench-harness
cargo run --release -p bench-harness -- --rate 5000 --count 50000 --num-markets 16 --seed 42
cargo run --release -p bench-harness -- --rate 0    --count 300000 --num-markets 16 --seed 42
```

## Headline: max sustained throughput (unpaced)

| | v1 | v2 | Change |
|---|---:|---:|---:|
| unpaced throughput (`--rate 0 --count 300000`) | 70,586 ev/s | 110,297 ev/s | **+56.3%** |

## Criterion micro-benchmarks (median)

| Benchmark | v1 | v2 | Speedup |
|---|---:|---:|---:|
| `MarketState::apply` | 973.09 ps | 954.00 ps | ~1.0× (unchanged; already trivial) |
| `prob_velocity` / 512 | 508.63 ns | 4.01 ns | **~127×** |
| `bet_arrival_rate` / 512 | 72.79 ns | 3.85 ns | **~18.9×** |
| `realized_volatility` / 512 | 787.46 ns | 228.23 ns | **~3.45×** |
| `compute_snapshot` / 512 | 9,244 ns | 570.28 ns | **~16.2×** |

`prob_velocity`/`bet_arrival_rate` collapsed because their old O(n) filter-into-`Vec` became an
O(log n) `partition_point` + slice with no allocation. `compute_snapshot` dropped because it no
longer clones up to 512 `String`-bearing `BetEvent`s per call. `realized_volatility` still does the
O(n) sum-of-squared-returns arithmetic, so its win (~3.4×) is "just" the removed `Vec` allocation.
`MarketState::apply` was already two field writes — unchanged, as expected.

## End-to-end pipeline latency, paced at 5,000 ev/s (microseconds)

Same command as `v1-baseline.md` §1 (`--rate 5000 --count 50000 --num-markets 16 --seed 42`).
Both runs achieved ~4,999 ev/s (paced), so this compares *latency*, not throughput.

**p50:**

| Segment | v1 | v2 | Reduction |
|---|---:|---:|---:|
| ws_receive → state_update | 0.375 | 0.042 | −88.8% |
| state_update → feature_calc | 37.823 | 0.791 | −97.9% (~48×) |
| feature_calc → storage_write | 225.791 | 37.407 | −83.4% |
| **total** | **270.591** | **38.271** | **−85.9% (~7.1×)** |

**Tail & mean (total segment):**

| Metric | v1 | v2 | Reduction |
|---|---:|---:|---:|
| mean | 497.818 | 76.084 | −84.7% |
| p99 | 6,111.231 | 715.263 | −88.3% |
| p99.9 | 25,100.287 | 1,857.535 | −92.6% |
| max | 84,344.831 | 4,571.135 | −94.6% (~18×) |

## Reading the result

Cutting per-event heap allocation didn't just speed up the compute stages that did the allocating —
it also relieved allocator contention (`malloc`/`mach_vm_protect`/`memmove` were ~44% of v1 CPU),
which is why even the **storage-write** stage (which didn't change) got ~6× faster at p50 and the
worst-case tail dropped ~18×. Less allocator pressure = fewer page-protection syscalls and less
lock contention across the whole pipeline.

After v2, the pipeline is no longer allocation-bound: `state→feature` fell from 37.8µs to 0.79µs, so
the remaining cost is concentrated almost entirely in **`feature→storage`** (37µs of the 38µs p50) —
the SQLite write path. That is the clear next hotspot, addressed in v3 (Task 6.4).
