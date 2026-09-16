use std::sync::atomic::{AtomicBool, AtomicI64, AtomicU64, Ordering};
use std::sync::Arc;
use std::time::{Duration, SystemTime, UNIX_EPOCH};

/// Shared, lock-free counters updated from the ingest/writer tasks and read periodically by
/// `run_health_log_loop`. `Arc`'d so both tasks and the logger hold the same instance.
#[derive(Debug, Default)]
pub struct HealthStats {
    events_processed: AtomicU64,
    /// Unix nanoseconds of the last successful DB write; `-1` means "never" (covers dry-run mode
    /// and the startup window before the first write).
    last_write_ns: AtomicI64,
    connected: AtomicBool,
}

pub type SharedHealth = Arc<HealthStats>;

#[derive(Debug, Clone, Copy)]
pub struct HealthSnapshot {
    pub events_processed: u64,
    pub last_write_ns: i64,
    pub connected: bool,
}

impl HealthStats {
    pub fn new() -> SharedHealth {
        Arc::new(Self {
            events_processed: AtomicU64::new(0),
            last_write_ns: AtomicI64::new(-1),
            connected: AtomicBool::new(false),
        })
    }

    pub fn record_event(&self) {
        self.events_processed.fetch_add(1, Ordering::Relaxed);
    }

    pub fn record_write_now(&self) {
        let now_ns = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map(|d| d.as_nanos() as i64)
            .unwrap_or(0);
        self.last_write_ns.store(now_ns, Ordering::Relaxed);
    }

    pub fn set_connected(&self, connected: bool) {
        self.connected.store(connected, Ordering::Relaxed);
    }

    pub fn snapshot(&self) -> HealthSnapshot {
        HealthSnapshot {
            events_processed: self.events_processed.load(Ordering::Relaxed),
            last_write_ns: self.last_write_ns.load(Ordering::Relaxed),
            connected: self.connected.load(Ordering::Relaxed),
        }
    }
}

/// Logs a structured health summary (`tracing::info!`) every `interval`, including
/// events/sec computed over that interval (not a lifetime average) and the last-write time in
/// RFC 3339. Runs forever — intended to be one of several tasks joined in `main`.
pub async fn run_health_log_loop(health: SharedHealth, interval: Duration) {
    let mut last_count = 0u64;
    let mut ticker = tokio::time::interval(interval);
    ticker.tick().await; // consume the immediate first tick so the first log has a real window

    loop {
        ticker.tick().await;
        let snap = health.snapshot();
        let delta = snap.events_processed.saturating_sub(last_count);
        let events_per_sec = delta as f64 / interval.as_secs_f64();
        last_count = snap.events_processed;

        let last_write = if snap.last_write_ns < 0 {
            "never".to_string()
        } else {
            chrono::DateTime::from_timestamp_nanos(snap.last_write_ns).to_rfc3339()
        };

        tracing::info!(
            connected = snap.connected,
            events_per_sec = events_per_sec,
            total_events = snap.events_processed,
            last_write = %last_write,
            "collector health"
        );
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn fresh_stats_report_never_written_and_disconnected() {
        let health = HealthStats::new();
        let snap = health.snapshot();
        assert_eq!(snap.events_processed, 0);
        assert_eq!(snap.last_write_ns, -1);
        assert!(!snap.connected);
    }

    #[test]
    fn record_event_increments_counter() {
        let health = HealthStats::new();
        health.record_event();
        health.record_event();
        assert_eq!(health.snapshot().events_processed, 2);
    }

    #[test]
    fn record_write_now_sets_a_positive_timestamp() {
        let health = HealthStats::new();
        health.record_write_now();
        assert!(health.snapshot().last_write_ns > 0);
    }

    #[test]
    fn set_connected_updates_snapshot() {
        let health = HealthStats::new();
        health.set_connected(true);
        assert!(health.snapshot().connected);
        health.set_connected(false);
        assert!(!health.snapshot().connected);
    }
}
