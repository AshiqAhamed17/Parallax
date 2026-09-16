//! Per-stage latency recording and reporting (Task 5.3).
//!
//! [`LatencyRecorder`] consumes the completed [`StageTimer`]s emitted by the collector's writer
//! loop (via its `latency_sink`) and records each stage-to-stage segment into its own
//! [`hdrhistogram::Histogram`]. [`LatencyRecorder::report`] snapshots the histograms into a
//! [`LatencyReport`], which renders to Markdown for `benchmarks/*.md`.
//!
//! Durations are recorded in **nanoseconds**. Histogram bounds are 1ns‥60s at 3 significant
//! figures — 0.1% precision, comfortably finer than the ±tolerances any report cares about, while
//! spanning every latency the pipeline could plausibly produce.

use common::{Stage, StageTimer};
use hdrhistogram::Histogram;

const LOWEST_NS: u64 = 1;
const HIGHEST_NS: u64 = 60_000_000_000; // 60s
const SIGFIG: u8 = 3;

/// A stage-to-stage latency segment the harness reports on.
///
/// The first three are the consecutive pipeline hops; [`Segment::Total`] is the end-to-end
/// WS-receive‥storage-write latency.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Segment {
    /// WS-receive → state-update: wire→domain conversion + probability-engine apply.
    WsToState,
    /// State-update → feature-calc: feature-engine snapshot computation.
    StateToFeature,
    /// Feature-calc → storage-write: bounded-channel hop + SQLite insert.
    FeatureToStorage,
    /// WS-receive → storage-write: the whole pipeline.
    Total,
}

impl Segment {
    /// Every segment, in report order.
    pub const ALL: [Segment; 4] = [
        Segment::WsToState,
        Segment::StateToFeature,
        Segment::FeatureToStorage,
        Segment::Total,
    ];

    /// Human-readable label used in report tables.
    pub fn label(self) -> &'static str {
        match self {
            Segment::WsToState => "ws_receive → state_update",
            Segment::StateToFeature => "state_update → feature_calc",
            Segment::FeatureToStorage => "feature_calc → storage_write",
            Segment::Total => "total (ws_receive → storage_write)",
        }
    }

    /// The `(from, to)` stages this segment spans.
    fn bounds(self) -> (Stage, Stage) {
        match self {
            Segment::WsToState => (Stage::WsReceive, Stage::StateUpdate),
            Segment::StateToFeature => (Stage::StateUpdate, Stage::FeatureCalc),
            Segment::FeatureToStorage => (Stage::FeatureCalc, Stage::StorageWrite),
            Segment::Total => (Stage::WsReceive, Stage::StorageWrite),
        }
    }

    fn index(self) -> usize {
        match self {
            Segment::WsToState => 0,
            Segment::StateToFeature => 1,
            Segment::FeatureToStorage => 2,
            Segment::Total => 3,
        }
    }
}

/// Accumulates per-segment latency samples into HDR histograms.
pub struct LatencyRecorder {
    histograms: Vec<Histogram<u64>>,
    /// Timers with all four stages present (a fully-recorded event).
    recorded: u64,
    /// Timers missing a stage (disabled/partial) — recorded into no histogram.
    skipped: u64,
}

impl Default for LatencyRecorder {
    fn default() -> Self {
        Self::new()
    }
}

impl LatencyRecorder {
    pub fn new() -> Self {
        let histograms = Segment::ALL
            .iter()
            .map(|_| {
                Histogram::<u64>::new_with_bounds(LOWEST_NS, HIGHEST_NS, SIGFIG)
                    .expect("valid HDR histogram bounds")
            })
            .collect();
        Self { histograms, recorded: 0, skipped: 0 }
    }

    /// Record a single latency sample (nanoseconds) for `segment`. Values above the histogram's
    /// ceiling saturate to it rather than erroring, so a pathological outlier can't abort a run.
    pub fn record_ns(&mut self, segment: Segment, ns: u64) {
        self.histograms[segment.index()].saturating_record(ns);
    }

    /// Record every segment derivable from `timer`. A timer with all four stages marked counts as
    /// `recorded`; one missing any stage (e.g. a disabled timer) counts as `skipped` and
    /// contributes no samples.
    pub fn record(&mut self, timer: &StageTimer) {
        // The total spans the whole pipeline; if it's present, every stage is present.
        if timer.total().is_none() {
            self.skipped += 1;
            return;
        }
        for segment in Segment::ALL {
            let (from, to) = segment.bounds();
            if let Some(d) = timer.duration_between(from, to) {
                self.record_ns(segment, d.as_nanos() as u64);
            }
        }
        self.recorded += 1;
    }

    /// Snapshot the current histograms into an immutable [`LatencyReport`].
    pub fn report(&self) -> LatencyReport {
        let segments = Segment::ALL
            .iter()
            .map(|&segment| {
                let h = &self.histograms[segment.index()];
                SegmentStats {
                    segment,
                    count: h.len(),
                    p50_ns: h.value_at_quantile(0.50),
                    p95_ns: h.value_at_quantile(0.95),
                    p99_ns: h.value_at_quantile(0.99),
                    p999_ns: h.value_at_quantile(0.999),
                    max_ns: h.max(),
                    mean_ns: h.mean(),
                }
            })
            .collect();
        LatencyReport { segments, events_recorded: self.recorded, events_skipped: self.skipped }
    }
}

/// Percentile summary for one segment. All latency fields are nanoseconds.
#[derive(Debug, Clone)]
pub struct SegmentStats {
    pub segment: Segment,
    pub count: u64,
    pub p50_ns: u64,
    pub p95_ns: u64,
    pub p99_ns: u64,
    pub p999_ns: u64,
    pub max_ns: u64,
    pub mean_ns: f64,
}

/// An immutable snapshot of all segments' latency percentiles.
#[derive(Debug, Clone)]
pub struct LatencyReport {
    pub segments: Vec<SegmentStats>,
    pub events_recorded: u64,
    pub events_skipped: u64,
}

/// Metadata describing the run that produced a report — rendered into the report header so the
/// numbers are reproducible (constraint §2.3: every benchmark number is traceable to a real run).
#[derive(Debug, Clone)]
pub struct RunMetadata {
    pub requested_rate: f64,
    pub events: usize,
    pub num_markets: usize,
    pub seed: u64,
    pub feature_window_ns: u64,
    pub achieved_throughput: f64,
    pub elapsed_secs: f64,
    /// The exact command that generated this report.
    pub command: String,
}

impl LatencyReport {
    /// The stats for `segment`, if present.
    pub fn segment(&self, segment: Segment) -> Option<&SegmentStats> {
        self.segments.iter().find(|s| s.segment == segment)
    }

    /// Render the report as Markdown for `benchmarks/*.md`. Latencies are shown in microseconds
    /// (3 decimals) for readability; the recorder keeps nanosecond precision underneath.
    pub fn to_markdown(&self, meta: &RunMetadata) -> String {
        let us = |ns: u64| format!("{:.3}", ns as f64 / 1000.0);
        let us_f = |ns: f64| format!("{:.3}", ns / 1000.0);

        let mut out = String::new();
        out.push_str("# Parallax — v1 Latency Baseline\n\n");
        out.push_str(
            "Per-stage pipeline latency under synthetic load, measured end-to-end through the real \
             `collector` pipeline (`run_ingest_loop` → bounded channel → `run_writer_loop`) with \
             per-stage `quanta` timing enabled. Storage-write is measured against an in-memory \
             SQLite database (see `implementation.md` §13).\n\n",
        );

        out.push_str("## Run parameters\n\n");
        out.push_str(&format!("- Command: `{}`\n", meta.command));
        out.push_str(&format!("- Requested rate: {:.1} events/s\n", meta.requested_rate));
        out.push_str(&format!(
            "- Achieved throughput: {:.1} events/s over {:.3}s\n",
            meta.achieved_throughput, meta.elapsed_secs
        ));
        out.push_str(&format!("- Events: {}\n", meta.events));
        out.push_str(&format!("- Markets: {}\n", meta.num_markets));
        out.push_str(&format!("- Seed: {}\n", meta.seed));
        out.push_str(&format!(
            "- Feature window: {} ns ({:.1}s)\n",
            meta.feature_window_ns,
            meta.feature_window_ns as f64 / 1e9
        ));
        out.push_str(&format!(
            "- Events fully recorded: {} (skipped: {})\n\n",
            self.events_recorded, self.events_skipped
        ));

        out.push_str("## Per-stage latency (microseconds)\n\n");
        out.push_str("| Segment | Count | p50 | p95 | p99 | p99.9 | max | mean |\n");
        out.push_str("|---|---:|---:|---:|---:|---:|---:|---:|\n");
        for s in &self.segments {
            out.push_str(&format!(
                "| {} | {} | {} | {} | {} | {} | {} | {} |\n",
                s.segment.label(),
                s.count,
                us(s.p50_ns),
                us(s.p95_ns),
                us(s.p99_ns),
                us(s.p999_ns),
                us(s.max_ns),
                us_f(s.mean_ns),
            ));
        }
        out.push('\n');
        out
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn percentiles_match_a_known_uniform_distribution() {
        // 1000 samples uniformly at 1µs, 2µs, …, 1000µs (recorded as ns).
        let mut rec = LatencyRecorder::new();
        for us in 1..=1000u64 {
            rec.record_ns(Segment::WsToState, us * 1_000);
        }
        let report = rec.report();
        let s = report.segment(Segment::WsToState).expect("segment present");

        assert_eq!(s.count, 1000);

        // Uniform 1..=1000µs: p50 ≈ 500µs, p95 ≈ 950µs, p99 ≈ 990µs, max = 1000µs.
        let approx = |actual: u64, expected_us: f64, tol_us: f64| {
            let actual_us = actual as f64 / 1000.0;
            assert!(
                (actual_us - expected_us).abs() <= tol_us,
                "expected ~{expected_us}µs, got {actual_us}µs"
            );
        };
        approx(s.p50_ns, 500.0, 5.0);
        approx(s.p95_ns, 950.0, 5.0);
        approx(s.p99_ns, 990.0, 5.0);
        approx(s.max_ns, 1000.0, 2.0);
        approx(s.mean_ns as u64, 500.0, 5.0);
    }

    #[test]
    fn record_counts_full_and_partial_timers() {
        let mut rec = LatencyRecorder::new();

        // A fully-marked timer via explicit instants would need real clock reads; use `mark`.
        let mut full = StageTimer::enabled();
        for stage in Stage::ALL {
            full.mark(stage);
            std::hint::black_box(&full);
        }
        rec.record(&full);

        // A disabled timer contributes nothing and counts as skipped.
        rec.record(&StageTimer::disabled());

        // A partial timer (missing storage-write) is also skipped.
        let mut partial = StageTimer::enabled();
        partial.mark(Stage::WsReceive);
        partial.mark(Stage::StateUpdate);
        rec.record(&partial);

        let report = rec.report();
        assert_eq!(report.events_recorded, 1);
        assert_eq!(report.events_skipped, 2);
        assert_eq!(report.segment(Segment::Total).unwrap().count, 1);
    }

    #[test]
    fn markdown_contains_metadata_and_every_segment() {
        let mut rec = LatencyRecorder::new();
        for us in 1..=100u64 {
            for seg in Segment::ALL {
                rec.record_ns(seg, us * 1_000);
            }
        }
        let meta = RunMetadata {
            requested_rate: 1000.0,
            events: 100,
            num_markets: 8,
            seed: 42,
            feature_window_ns: 60_000_000_000,
            achieved_throughput: 998.0,
            elapsed_secs: 0.1,
            command: "bench-harness --rate 1000 --count 100".to_string(),
        };
        let md = rec.report().to_markdown(&meta);
        assert!(md.contains("bench-harness --rate 1000 --count 100"));
        assert!(md.contains("Achieved throughput"));
        for seg in Segment::ALL {
            assert!(md.contains(seg.label()), "missing segment {}", seg.label());
        }
    }
}
