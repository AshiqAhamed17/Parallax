use clap::Parser;
use collector::archive::ArchiveExporter;
use collector::health::{run_health_log_loop, HealthStats};
use collector::ingest::{run_ingest_loop, run_writer_loop};
use collector::migration::open_and_migrate;
use std::path::PathBuf;
use std::time::Duration;
use tokio::sync::mpsc;

/// Parallax's always-on Manifold ingestion pipeline: subscribes to live bet events, drives the
/// probability engine and feature engine, and persists both to SQLite plus a periodic Parquet
/// archive. See `implementation.md` §3 for the overall architecture this ties together.
#[derive(Parser, Debug)]
#[command(name = "collector")]
struct Args {
    /// Manifold WS topics to subscribe to, comma-separated.
    #[arg(long, default_value = "global/new-bet")]
    topics: String,

    /// Path to the SQLite database file.
    #[arg(long, default_value = "data/parallax.db")]
    db_path: PathBuf,

    /// Directory for Parquet archive exports.
    #[arg(long, default_value = "data/archive")]
    archive_dir: PathBuf,

    /// Feature-window size in seconds, used for prob_velocity/bet_arrival_rate/realized_vol.
    #[arg(long, default_value_t = 60)]
    feature_window_secs: u64,

    /// Per-market rolling bet-history capacity.
    #[arg(long, default_value_t = 512)]
    history_capacity: usize,

    /// How often to log a health summary, in seconds.
    #[arg(long, default_value_t = 30)]
    health_interval_secs: u64,

    /// How often to run the Parquet archive export, in seconds.
    #[arg(long, default_value_t = 3600)]
    archive_interval_secs: u64,

    /// Process live events but skip SQLite writes entirely (still logs health/events).
    #[arg(long, default_value_t = false)]
    dry_run: bool,
}

#[tokio::main]
async fn main() {
    tracing_subscriber::fmt()
        .with_env_filter(tracing_subscriber::EnvFilter::from_default_env().add_directive(tracing::Level::INFO.into()))
        .init();

    let args = Args::parse();
    let topics: Vec<String> = args.topics.split(',').map(|s| s.trim().to_string()).collect();

    tracing::info!(?topics, db_path = %args.db_path.display(), dry_run = args.dry_run, "starting collector");

    if let Some(parent) = args.db_path.parent()
        && !parent.as_os_str().is_empty()
    {
        let _ = std::fs::create_dir_all(parent);
    }
    let _ = std::fs::create_dir_all(&args.archive_dir);

    let conn = match open_and_migrate(&args.db_path) {
        Ok(c) => c,
        Err(e) => {
            tracing::error!(error = %e, "failed to open/migrate database, exiting");
            std::process::exit(1);
        }
    };

    let health = HealthStats::new();
    let (tx, rx) = mpsc::channel(1024);

    let event_stream = manifold_client::connect(topics);

    let ingest_task = tokio::spawn(run_ingest_loop(
        Box::pin(event_stream),
        tx,
        args.feature_window_secs * 1_000_000_000,
        args.history_capacity,
        health.clone(),
    ));

    let writer_task = tokio::spawn(run_writer_loop(rx, conn, health.clone(), args.dry_run));

    let health_task = tokio::spawn(run_health_log_loop(
        health.clone(),
        Duration::from_secs(args.health_interval_secs),
    ));

    let archive_task = tokio::spawn(
        ArchiveExporter::new(args.archive_dir).run_archive_loop(
            args.db_path.clone(),
            Duration::from_secs(args.archive_interval_secs),
        ),
    );

    tokio::select! {
        _ = tokio::signal::ctrl_c() => {
            tracing::info!("received Ctrl+C, shutting down");
        }
        result = ingest_task => {
            tracing::warn!(?result, "ingest task ended unexpectedly");
        }
        result = writer_task => {
            tracing::warn!(?result, "writer task ended unexpectedly");
        }
        result = health_task => {
            tracing::warn!(?result, "health task ended unexpectedly");
        }
        result = archive_task => {
            tracing::warn!(?result, "archive task ended unexpectedly");
        }
    }
}
