use bench_harness::{synthetic_stream, SyntheticConfig};
use clap::Parser;
use futures_util::StreamExt;

/// Synthetic load generator for the Parallax latency benchmark harness (Phase 5). Emits WS-shaped
/// synthetic bet events at a configurable rate and reports the throughput it actually achieved.
/// Later phases feed this stream through the real collector pipeline with per-stage timing on.
#[derive(Parser, Debug)]
#[command(name = "bench-harness")]
struct Args {
    /// Target events (bets) per second. Use 0 for "as fast as possible".
    #[arg(long, default_value_t = 1000.0)]
    rate: f64,

    /// Total number of events to generate.
    #[arg(long, default_value_t = 10_000)]
    count: usize,

    /// Number of distinct markets to spread bets across.
    #[arg(long, default_value_t = 16)]
    num_markets: usize,

    /// PRNG seed for reproducible event sequences.
    #[arg(long, default_value_t = 42)]
    seed: u64,
}

#[tokio::main]
async fn main() {
    let args = Args::parse();
    let config = SyntheticConfig {
        rate_per_sec: args.rate,
        num_markets: args.num_markets,
        seed: args.seed,
    };

    let start = std::time::Instant::now();
    let mut stream = Box::pin(synthetic_stream(config, args.count));
    let mut n = 0usize;
    while stream.next().await.is_some() {
        n += 1;
    }
    let elapsed = start.elapsed().as_secs_f64();
    let measured = if elapsed > 0.0 { n as f64 / elapsed } else { f64::INFINITY };

    println!(
        "generated {n} events in {elapsed:.3}s -> {measured:.1} events/s (requested {:.1}/s)",
        args.rate
    );
}
