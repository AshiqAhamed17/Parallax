//! Latency benchmark harness for the Parallax ingestion pipeline (Phase 5).
//!
//! - [`generator`] produces WS-shaped synthetic load at a controlled, reproducible rate (Task 5.2).
//! - [`report`] records per-stage latencies into HDR histograms and renders a percentile report
//!   (Task 5.3).
//! - [`runner`] drives the *real* collector pipeline (`run_ingest_loop`/`run_writer_loop`) with
//!   per-stage timing enabled, feeding the histograms (Task 5.3).

mod generator;
mod report;
mod runner;

pub use generator::{synthetic_stream, SyntheticConfig, SyntheticGenerator};
pub use report::{LatencyRecorder, LatencyReport, RunMetadata, Segment, SegmentStats};
pub use runner::{run_load_test, BenchOutcome, BenchRun};
