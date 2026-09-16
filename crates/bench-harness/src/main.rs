use bench_harness::{run_load_test, BenchRun, RunMetadata, SyntheticConfig};
use clap::Parser;
use std::path::PathBuf;

/// Latency benchmark harness for the Parallax ingestion pipeline (Phase 5). Generates WS-shaped
/// synthetic load at a configurable rate, drives it through the real collector pipeline with
/// per-stage `quanta` timing on, and reports per-stage latency percentiles (p50/p95/p99/p99.9/max).
#[derive(Parser, Debug)]
#[command(name = "bench-harness")]
struct Args {
    /// Target events (bets) per second. Use 0 for "as fast as possible".
    #[arg(long, default_value_t = 1000.0)]
    rate: f64,

    /// Total number of events to generate.
    #[arg(long, default_value_t = 50_000)]
    count: usize,

    /// Number of distinct markets to spread bets across.
    #[arg(long, default_value_t = 16)]
    num_markets: usize,

    /// PRNG seed for reproducible event sequences.
    #[arg(long, default_value_t = 42)]
    seed: u64,

    /// Feature-window size in seconds.
    #[arg(long, default_value_t = 60)]
    feature_window_secs: u64,

    /// Per-market rolling bet-history capacity.
    #[arg(long, default_value_t = 512)]
    history_capacity: usize,

    /// Write the Markdown latency report to this path (in addition to printing a summary).
    #[arg(long)]
    report: Option<PathBuf>,
}

#[tokio::main]
async fn main() {
    let args = Args::parse();

    let feature_window_ns = args.feature_window_secs * 1_000_000_000;
    let run = BenchRun {
        config: SyntheticConfig {
            rate_per_sec: args.rate,
            num_markets: args.num_markets,
            seed: args.seed,
        },
        count: args.count,
        feature_window_ns,
        history_capacity: args.history_capacity,
    };

    let outcome = match run_load_test(run).await {
        Ok(o) => o,
        Err(e) => {
            eprintln!("load test failed: {e}");
            std::process::exit(1);
        }
    };

    let meta = RunMetadata {
        requested_rate: args.rate,
        events: args.count,
        num_markets: args.num_markets,
        seed: args.seed,
        feature_window_ns,
        achieved_throughput: outcome.achieved_throughput,
        elapsed_secs: outcome.elapsed_secs,
        command: format!(
            "bench-harness --rate {} --count {} --num-markets {} --seed {}",
            args.rate, args.count, args.num_markets, args.seed
        ),
    };

    let markdown = outcome.report.to_markdown(&meta);
    print!("{markdown}");

    if let Some(path) = &args.report {
        match std::fs::write(path, &markdown) {
            Ok(()) => eprintln!("wrote report to {}", path.display()),
            Err(e) => {
                eprintln!("failed to write report to {}: {e}", path.display());
                std::process::exit(1);
            }
        }
    }
}
