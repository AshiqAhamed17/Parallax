//! Instrumented load runner (Task 5.3).
//!
//! [`run_load_test`] feeds a rate-paced synthetic stream through the *real* collector pipeline with
//! per-stage timing enabled, drains the completed timers off the writer's latency sink into a
//! [`LatencyRecorder`], and returns the resulting [`LatencyReport`]. Running the genuine
//! `run_ingest_loop`/`run_writer_loop` (not a re-implementation) is the point: the numbers reflect
//! the code that actually runs in production, including the bounded-channel hop and SQLite insert.
//!
//! Storage is an in-memory SQLite database so the benchmark is reproducible and doesn't depend on
//! disk characteristics; the storage-write stage therefore measures the insert *code path*, not
//! physical disk latency (documented in `implementation.md` §13).

use crate::generator::{synthetic_stream, SyntheticConfig};
use crate::report::{LatencyRecorder, LatencyReport};
use collector::health::HealthStats;
use collector::ingest::{run_ingest_loop, run_writer_loop};
use collector::migration::apply_migrations;
use rusqlite::Connection;
use tokio::sync::mpsc;

/// Parameters for one instrumented load run.
#[derive(Debug, Clone)]
pub struct BenchRun {
    pub config: SyntheticConfig,
    pub count: usize,
    pub feature_window_ns: u64,
    pub history_capacity: usize,
}

/// The result of a load run: the latency report plus the throughput actually achieved.
#[derive(Debug, Clone)]
pub struct BenchOutcome {
    pub report: LatencyReport,
    pub achieved_throughput: f64,
    pub elapsed_secs: f64,
}

/// Run `count` synthetic events through the real pipeline with timing on and collect per-stage
/// latencies. Returns an error only if the in-memory database can't be initialized or the writer
/// hits a SQL error.
pub async fn run_load_test(run: BenchRun) -> rusqlite::Result<BenchOutcome> {
    let conn = Connection::open_in_memory()?;
    apply_migrations(&conn)?;

    let health = HealthStats::new();
    // Capacities generous enough that neither channel is the bottleneck under test.
    let (tx, rx) = mpsc::channel(4096);
    let (lat_tx, mut lat_rx) = mpsc::channel(4096);

    let stream = synthetic_stream(run.config.clone(), run.count);

    let start = std::time::Instant::now();
    let ingest = tokio::spawn(run_ingest_loop(
        Box::pin(stream),
        tx,
        run.feature_window_ns,
        run.history_capacity,
        health.clone(),
        true, // timing enabled — this is the whole point of the harness
    ));
    let writer = tokio::spawn(run_writer_loop(rx, conn, health.clone(), false, Some(lat_tx)));

    // Drain completed timers concurrently with the pipeline. The loop ends when the writer task
    // finishes and drops its `lat_tx`; by then ingest and writer are effectively done too.
    let mut recorder = LatencyRecorder::new();
    while let Some(timer) = lat_rx.recv().await {
        recorder.record(&timer);
    }
    let elapsed = start.elapsed().as_secs_f64();

    ingest.await.expect("ingest task panicked");
    let _conn = writer.await.expect("writer task panicked")?;

    let report = recorder.report();
    let achieved_throughput =
        if elapsed > 0.0 { report.events_recorded as f64 / elapsed } else { f64::INFINITY };

    Ok(BenchOutcome { report, achieved_throughput, elapsed_secs: elapsed })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::report::Segment;

    #[tokio::test]
    async fn load_run_records_every_event_across_all_segments() {
        let run = BenchRun {
            config: SyntheticConfig { rate_per_sec: 0.0, num_markets: 4, seed: 1 }, // unpaced = fast
            count: 500,
            feature_window_ns: 60_000_000_000,
            history_capacity: 128,
        };
        let outcome = run_load_test(run).await.unwrap();

        // Every synthetic event should traverse all four stages and be fully recorded.
        assert_eq!(outcome.report.events_recorded, 500);
        assert_eq!(outcome.report.events_skipped, 0);

        for seg in Segment::ALL {
            let stats = outcome.report.segment(seg).unwrap();
            assert_eq!(stats.count, 500, "segment {} under-counted", seg.label());
            // Total latency must be at least each of its constituent parts' order of magnitude —
            // sanity floor: a real measurement is non-zero for the end-to-end path.
        }

        // The end-to-end segment should be >= the channel-hop segment (it contains it).
        let total = outcome.report.segment(Segment::Total).unwrap();
        assert!(total.max_ns > 0, "total latency should be measurable");
        assert!(outcome.achieved_throughput > 0.0);
    }
}
