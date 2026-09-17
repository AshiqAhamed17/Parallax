# Parallax — v3 Benchmark Results (writer statement-caching + per-record transaction)

After v2 the pipeline was no longer allocation-bound; the remaining end-to-end cost sat almost
entirely in the SQLite write path (`feature→storage`). v3 (Task 6.4) targets it: `write_record`
now runs its four inserts through `prepare_cached` statements inside a single per-record
`unchecked_transaction`, so v1's four fresh statement compilations + four autocommits per record
become one commit reusing cached prepared statements. A record is still committed atomically as it
arrives — no cross-record batching, no durability change.

Reproduce:

```bash
cargo run --release -p bench-harness -- --rate 0    --count 300000 --num-markets 16 --seed 42
cargo run --release -p bench-harness -- --rate 5000 --count 50000  --num-markets 16 --seed 42
```

## Headline: max sustained throughput (unpaced) — the clean capacity metric

| Version | unpaced throughput | vs v1 | vs prev |
|---|---:|---:|---:|
| v1 (baseline) | 70,586 ev/s | — | — |
| v2 (allocation cut) | 110,297 ev/s | +56.3% | +56.3% |
| **v3 (writer caching+txn)** | **194,444 ev/s** | **+175.5%** | **+76.3%** |

The writer was the throughput ceiling once v2 made the compute path allocation-free: caching the
prepared statements alone lifted it to ~182k ev/s, and folding the four inserts into one
transaction took it to ~194k. (For reference, live Manifold emits on the order of ~1–2 bets/s — see
Task 4.4 — so this is capacity headroom, not a production requirement.)

## End-to-end latency, paced at 5,000 ev/s (microseconds)

| Segment (total) | v1 | v2 | v3 |
|---|---:|---:|---:|
| p50 | 270.591 | 38.271 | 94.207 |
| p99 | 6,111.231 | 715.263 | 1,500.159 |
| max | 84,344.831 | 4,571.135 | 3,082.239 |

**Read this carefully — the paced per-stage latency is scheduling-dominated at 5k/s, not a clean
writer metric.** Two facts show why:

- Making the writer *faster* (v2→v3) did **not** lower the `feature→storage` latency; the
  `prepare_cached`-only variant (faster writer, ~182k ev/s) showed the same ~100µs p50 as the
  full txn version. If this segment were writer-bound, a faster writer would reduce it.
- Even the **unchanged** compute stages read differently between v2 and v3 runs (`state→feature`
  p50 0.79µs in the v2 run, 5.79µs in the v3 run) despite identical code — because at 5k/s the
  per-record cost is dominated by how the ingest and writer async tasks interleave on the Tokio
  runtime, not by the work itself.

So the honest attribution: v3 is a **throughput** optimization for the async writer (which sits
behind a bounded channel, off the latency-critical signal path). Its clean, reproducible win is the
+76% unpaced throughput and a tighter worst-case tail (max 4.6ms → 3.1ms). The v1→v2 latency
collapse remains the real *latency* story; v3 does not touch — and the signal path
(`ws→state→feature`) remains sub-10µs.

## Criterion micro-benchmarks

Unchanged from v2 — the criterion suite covers `MarketState::apply` and the feature calcs, none of
which the v3 writer change touches. See `benchmarks/v2-results.md`.

## Correctness

`write_record`'s row output is unchanged (same four inserts, same values); the collector's ingest
integration tests (row count + ordering across markets, dry-run, clean shutdown) pass, the whole
workspace is green, and the Phase 2.6 differential proptest still passes at `PROPTEST_CASES=10000`.
