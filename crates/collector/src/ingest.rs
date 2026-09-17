use crate::health::SharedHealth;
use common::{BetEvent, Stage, StageTimer};
use feature_engine::{compute_snapshot, FeatureSnapshot};
use futures_util::{Stream, StreamExt};
use manifold_client::ManifoldWsEvent;
use probability_engine::ProbabilityEngine;
use quanta::Instant;
use rusqlite::{params, Connection, Result as SqlResult};
use tokio::sync::mpsc;

/// Everything the writer needs to persist one bet: the domain event, the resulting market
/// probability, and the feature snapshot computed immediately after applying it.
///
/// `timer` carries per-stage latency timestamps (Phase 5). It is `StageTimer::Disabled` in normal
/// operation (zero-cost) and only enabled when the benchmark harness runs the pipeline; the ingest
/// loop marks the WS-receive/state-update/feature-calc stages and the writer marks storage-write.
#[derive(Debug, Clone)]
pub struct IngestedRecord {
    pub bet: BetEvent,
    pub probability: f64,
    pub features: FeatureSnapshot,
    pub timer: StageTimer,
}

/// The hot path: consumes `events` from Manifold, converts each bet to `common::BetEvent`, drives
/// a `ProbabilityEngine`, computes a `FeatureSnapshot`, and sends the result to `tx`.
///
/// This function never touches SQLite — persistence is the writer loop's job, running as a
/// separate task (see `run_writer_loop`). The channel between them is bounded: if the writer
/// falls behind, `tx.send` applies async backpressure (the ingest task yields, it doesn't block
/// an OS thread on disk I/O) rather than letting unbounded memory growth mask a stuck writer.
///
/// `Ack` events carry no bets; they're used only to mark the connection healthy in `health` (the
/// current `ManifoldWsEvent` surface has no explicit disconnect notification, so an Ack is the
/// best available "we're really connected" signal — see `implementation.md`'s Task 4.4 note).
pub async fn run_ingest_loop(
    mut events: impl Stream<Item = ManifoldWsEvent> + Unpin,
    tx: mpsc::Sender<IngestedRecord>,
    feature_window_ns: u64,
    history_capacity: usize,
    health: SharedHealth,
    timing: bool,
) {
    let mut engine = ProbabilityEngine::new(history_capacity);

    while let Some(event) = events.next().await {
        // Stamp WS-receive once per broadcast; every bet it carries shares this entry instant.
        let ws_receive = timing.then(Instant::now);
        let bets = match event {
            ManifoldWsEvent::Ack { .. } => {
                health.set_connected(true);
                continue;
            }
            ManifoldWsEvent::NewBets { bets, .. } => bets,
        };
        for wire_bet in &bets {
            let mut timer = match ws_receive {
                Some(t) => StageTimer::enabled_from(t),
                None => StageTimer::disabled(),
            };

            let domain: BetEvent = wire_bet.into();
            engine.apply(&domain);
            timer.mark(Stage::StateUpdate);
            health.record_event();

            let Some(tracker) = engine.market(&domain.market_id) else {
                continue; // apply() always creates the tracker, but stay defensive
            };
            let features = compute_snapshot(tracker, feature_window_ns);
            timer.mark(Stage::FeatureCalc);

            let record = IngestedRecord {
                bet: domain.clone(),
                probability: tracker.state().current_prob,
                features,
                timer,
            };
            if tx.send(record).await.is_err() {
                return; // writer's gone; nothing left to do
            }
        }
    }
}

/// Drains `rx`, writing each record to SQLite, until the channel closes (the ingest loop ended
/// and dropped its sender). Returns the connection back so callers (tests, graceful shutdown)
/// can use it afterward instead of it being silently dropped inside this function.
///
/// When `dry_run` is true, records are still drained (so the channel doesn't back up and the
/// pipeline can be observed end-to-end via `health`) but never written to SQLite.
///
/// `latency_sink`, when `Some`, receives each record's completed `StageTimer` after its
/// storage-write stage is marked — this is how the benchmark harness (Phase 5) collects per-event
/// timelines to feed its histogram. It's `None` in normal operation. The stage is marked whether
/// or not the row is actually written (including dry-run), so the timing reflects the pipeline's
/// work regardless of persistence.
pub async fn run_writer_loop(
    mut rx: mpsc::Receiver<IngestedRecord>,
    conn: Connection,
    health: SharedHealth,
    dry_run: bool,
    latency_sink: Option<mpsc::Sender<StageTimer>>,
) -> SqlResult<Connection> {
    while let Some(mut record) = rx.recv().await {
        if !dry_run {
            write_record(&conn, &record)?;
            health.record_write_now();
        }
        record.timer.mark(Stage::StorageWrite);
        if let Some(sink) = &latency_sink {
            // The harness owning the sink drives the run; if it's gone, drop the timer silently.
            let _ = sink.send(record.timer).await;
        }
    }
    Ok(conn)
}

/// Writes one record's rows. Also ensures a placeholder `markets` row exists (`INSERT OR
/// IGNORE`) so `bets`/`probability_snapshots`/`feature_snapshots` always have a market to
/// reference — real question text/close time require a REST backfill this task doesn't do (see
/// `tasks.md` Task 4.2 note); the placeholder keeps the row present rather than absent.
///
/// The four inserts run inside a single per-record transaction (`unchecked_transaction` — safe:
/// the writer is the connection's only user) and via `prepare_cached`, so v1's four separate
/// autocommits + four fresh statement compilations per record become one commit reusing cached
/// prepared statements (Task 6.4 / v3). This is the `feature→storage` hotspot the v2 profile left
/// dominant. A record is still committed atomically as it arrives — no batching, no durability
/// change.
fn write_record(conn: &Connection, record: &IngestedRecord) -> SqlResult<()> {
    let tx = conn.unchecked_transaction()?;
    {
        tx.prepare_cached(
            "INSERT OR IGNORE INTO markets (market_id, platform, question_text, close_time)
             VALUES (?1, 'manifold', '', '')",
        )?
        .execute(params![record.bet.market_id])?;

        tx.prepare_cached(
            "INSERT INTO bets
                (market_id, ts_ns, prob_before, prob_after, amount, shares, is_limit_order)
             VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)",
        )?
        .execute(params![
            record.bet.market_id,
            record.bet.ts_ns as i64,
            record.bet.prob_before,
            record.bet.prob_after,
            record.bet.amount,
            record.bet.shares,
            record.bet.is_limit_order as i64,
        ])?;

        tx.prepare_cached(
            "INSERT INTO probability_snapshots (market_id, ts_ns, probability, volume_24h)
             VALUES (?1, ?2, ?3, NULL)",
        )?
        .execute(params![record.bet.market_id, record.bet.ts_ns as i64, record.probability])?;

        tx.prepare_cached(
            "INSERT INTO feature_snapshots
                (market_id, ts_ns, prob_velocity, bet_arrival_rate, realized_vol)
             VALUES (?1, ?2, ?3, ?4, ?5)",
        )?
        .execute(params![
            record.bet.market_id,
            record.features.ts_ns as i64,
            record.features.prob_velocity,
            record.features.bet_arrival_rate,
            record.features.realized_vol,
        ])?;
    }
    tx.commit()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::health::HealthStats;
    use crate::migration::apply_migrations;
    use manifold_client::Bet;

    fn wire_bet(contract_id: &str, created_time_ms: i64, prob_before: f64, prob_after: f64) -> Bet {
        Bet {
            id: "bet".to_string(),
            contract_id: contract_id.to_string(),
            created_time: created_time_ms,
            prob_before,
            prob_after,
            amount: 10.0,
            shares: 15.0,
            is_filled: Some(true),
            is_cancelled: Some(false),
            limit_prob: None,
        }
    }

    fn markets_count(conn: &Connection) -> i64 {
        conn.query_row("SELECT COUNT(*) FROM markets", [], |r| r.get(0)).unwrap()
    }

    #[tokio::test]
    async fn pipeline_writes_rows_in_order_across_two_markets() {
        let events = futures_util::stream::iter(vec![
            ManifoldWsEvent::NewBets {
                topic: "global/new-bet".to_string(),
                bets: vec![wire_bet("m1", 1000, 0.5, 0.6)],
            },
            ManifoldWsEvent::Ack { txid: 1, success: true }, // must be ignored, no rows from this
            ManifoldWsEvent::NewBets {
                topic: "global/new-bet".to_string(),
                bets: vec![wire_bet("m1", 2000, 0.6, 0.55), wire_bet("m2", 2000, 0.5, 0.2)],
            },
        ]);

        let conn = Connection::open_in_memory().unwrap();
        apply_migrations(&conn).unwrap();

        let (tx, rx) = mpsc::channel(16);
        let health = HealthStats::new();
        let (_, writer_result) = tokio::join!(
            run_ingest_loop(events, tx, 60_000_000_000, 64, health.clone(), false),
            run_writer_loop(rx, conn, health.clone(), false, None),
        );
        let conn = writer_result.unwrap();

        // health tracked all 3 bets and the Ack's connection signal.
        let snap = health.snapshot();
        assert_eq!(snap.events_processed, 3);
        assert!(snap.connected);
        assert!(snap.last_write_ns > 0);

        // 3 bets total (b1@m1, b2@m1, b3@m2); the Ack contributed nothing.
        let bet_count: i64 = conn.query_row("SELECT COUNT(*) FROM bets", [], |r| r.get(0)).unwrap();
        assert_eq!(bet_count, 3);

        // m1's two bets landed in timestamp order (ms -> ns scaling preserves ordering).
        let mut stmt = conn
            .prepare("SELECT ts_ns, prob_after FROM bets WHERE market_id = 'm1' ORDER BY id")
            .unwrap();
        let rows: Vec<(i64, f64)> = stmt
            .query_map([], |r| Ok((r.get(0)?, r.get(1)?)))
            .unwrap()
            .map(|r| r.unwrap())
            .collect();
        assert_eq!(rows, vec![(1000 * 1_000_000, 0.6), (2000 * 1_000_000, 0.55)]);

        // Both markets got a placeholder `markets` row.
        assert_eq!(markets_count(&conn), 2);

        // Each bet produced a matching probability_snapshots and feature_snapshots row.
        let prob_count: i64 = conn
            .query_row("SELECT COUNT(*) FROM probability_snapshots", [], |r| r.get(0))
            .unwrap();
        let feature_count: i64 = conn
            .query_row("SELECT COUNT(*) FROM feature_snapshots", [], |r| r.get(0))
            .unwrap();
        assert_eq!(prob_count, 3);
        assert_eq!(feature_count, 3);

        // m1's final probability_snapshots row reflects the second (most recent) bet.
        let final_prob: f64 = conn
            .query_row(
                "SELECT probability FROM probability_snapshots WHERE market_id = 'm1' ORDER BY id DESC LIMIT 1",
                [],
                |r| r.get(0),
            )
            .unwrap();
        assert_eq!(final_prob, 0.55);
    }

    #[tokio::test]
    async fn writer_stops_cleanly_when_ingest_side_closes_the_channel() {
        let events = futures_util::stream::iter(Vec::<ManifoldWsEvent>::new());
        let conn = Connection::open_in_memory().unwrap();
        apply_migrations(&conn).unwrap();

        let (tx, rx) = mpsc::channel(16);
        let health = HealthStats::new();
        let (_, writer_result) = tokio::join!(
            run_ingest_loop(events, tx, 1_000_000_000, 8, health.clone(), false),
            run_writer_loop(rx, conn, health, false, None),
        );
        let conn = writer_result.unwrap(); // must return Ok, not hang or error
        assert_eq!(markets_count(&conn), 0);
    }

    #[tokio::test]
    async fn dry_run_skips_writes_but_still_tracks_health() {
        let events = futures_util::stream::iter(vec![ManifoldWsEvent::NewBets {
            topic: "global/new-bet".to_string(),
            bets: vec![wire_bet("m1", 1000, 0.5, 0.6)],
        }]);
        let conn = Connection::open_in_memory().unwrap();
        apply_migrations(&conn).unwrap();

        let (tx, rx) = mpsc::channel(16);
        let health = HealthStats::new();
        let (_, writer_result) = tokio::join!(
            run_ingest_loop(events, tx, 1_000_000_000, 8, health.clone(), false),
            run_writer_loop(rx, conn, health.clone(), true, None), // dry_run = true
        );
        let conn = writer_result.unwrap();

        assert_eq!(markets_count(&conn), 0, "dry-run must not write to the DB");
        let bet_count: i64 = conn.query_row("SELECT COUNT(*) FROM bets", [], |r| r.get(0)).unwrap();
        assert_eq!(bet_count, 0);

        let snap = health.snapshot();
        assert_eq!(snap.events_processed, 1, "events are still counted in dry-run");
        assert_eq!(snap.last_write_ns, -1, "no write should be recorded in dry-run");
    }

    #[tokio::test]
    async fn timing_enabled_captures_monotonic_per_stage_timestamps() {
        // A single bet flows through the real pipeline with timing on; the writer forwards its
        // completed timer to the latency sink. All four stages must be marked in causal order.
        let events = futures_util::stream::iter(vec![ManifoldWsEvent::NewBets {
            topic: "global/new-bet".to_string(),
            bets: vec![wire_bet("m1", 1000, 0.5, 0.6)],
        }]);
        let conn = Connection::open_in_memory().unwrap();
        apply_migrations(&conn).unwrap();

        let (tx, rx) = mpsc::channel(16);
        let (lat_tx, mut lat_rx) = mpsc::channel(16);
        let health = HealthStats::new();
        let (_, writer_result) = tokio::join!(
            run_ingest_loop(events, tx, 1_000_000_000, 8, health.clone(), true),
            run_writer_loop(rx, conn, health.clone(), false, Some(lat_tx)),
        );
        writer_result.unwrap();

        let timer = lat_rx.recv().await.expect("one completed timer for the single bet");
        assert!(timer.is_enabled());
        let timeline = timer.timeline().expect("all four stages marked");
        for pair in timeline.windows(2) {
            assert!(pair[1] >= pair[0], "stage timestamps must be non-decreasing");
        }
        assert!(timer.is_monotonic());
        assert!(timer.total().is_some(), "WS-receive -> storage-write duration is available");
        assert!(lat_rx.recv().await.is_none(), "exactly one timer expected");
    }

    #[tokio::test]
    async fn timing_disabled_leaves_records_uninstrumented() {
        let events = futures_util::stream::iter(vec![ManifoldWsEvent::NewBets {
            topic: "global/new-bet".to_string(),
            bets: vec![wire_bet("m1", 1000, 0.5, 0.6)],
        }]);
        let conn = Connection::open_in_memory().unwrap();
        apply_migrations(&conn).unwrap();

        let (tx, rx) = mpsc::channel(16);
        let (lat_tx, mut lat_rx) = mpsc::channel(16);
        let health = HealthStats::new();
        let (_, writer_result) = tokio::join!(
            run_ingest_loop(events, tx, 1_000_000_000, 8, health.clone(), false),
            run_writer_loop(rx, conn, health.clone(), false, Some(lat_tx)),
        );
        writer_result.unwrap();

        let timer = lat_rx.recv().await.expect("the record still flows, just uninstrumented");
        assert!(!timer.is_enabled());
        assert_eq!(timer.timeline(), None);
    }
}
