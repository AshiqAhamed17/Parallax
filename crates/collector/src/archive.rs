use chrono::DateTime;
use polars::prelude::*;
use rusqlite::Connection;
use std::collections::HashMap;
use std::fs::{self, File};
use std::path::{Path, PathBuf};

/// Rolls new rows from `bets`, `probability_snapshots`, and `feature_snapshots` into partitioned
/// Parquet files under `archive_dir` (`implementation.md` §5). Tracks a per-table high-water mark
/// (`id`) **in memory only** — a collector restart re-scans from `id > 0`. Fine for now (Parquet
/// files are keyed by row id within their date partition, so a re-export after a restart produces
/// a new part file with the same rows rather than data loss; the cost is one-time duplicate rows
/// in the archive until deduplicated downstream). Persisting the watermark is a reasonable future
/// improvement, not required for this task's scope.
///
/// **Partitioning**: by the calendar date (UTC) derived from each row's own `ts_ns` — not the
/// date the export ran — so a batch that happens to span midnight UTC writes to two date
/// partitions correctly. Layout: `<archive_dir>/<table>/dt=<YYYY-MM-DD>/part-<run_id>.parquet`.
/// Multiple part files per partition is the standard Hive-style layout (downstream readers like
/// DuckDB/pandas glob all parts for a date) — this avoids ever needing to read-modify-write an
/// existing Parquet file, which isn't a natural operation for the format.
pub struct ArchiveExporter {
    archive_dir: PathBuf,
    last_bet_id: i64,
    last_probability_id: i64,
    last_feature_id: i64,
}

impl ArchiveExporter {
    pub fn new(archive_dir: impl Into<PathBuf>) -> Self {
        Self {
            archive_dir: archive_dir.into(),
            last_bet_id: 0,
            last_probability_id: 0,
            last_feature_id: 0,
        }
    }

    /// Exports all three tables' new rows. Returns every part-file path written (empty if there
    /// was nothing new anywhere).
    pub fn export_all_new(&mut self, conn: &Connection, run_id: i64) -> PolarsResult<Vec<PathBuf>> {
        let mut written = self.export_new_bets(conn, run_id)?;
        written.extend(self.export_new_probability_snapshots(conn, run_id)?);
        written.extend(self.export_new_feature_snapshots(conn, run_id)?);
        Ok(written)
    }

    /// Runs `export_all_new` on a timer, forever. Opens its **own** connection to `db_path`
    /// (WAL-mode, via `crate::migration::open_and_migrate`) rather than sharing the writer's
    /// connection — SQLite's WAL mode lets one writer and one-or-more readers coexist safely on
    /// the same file without a shared-ownership/locking dance between two async tasks.
    pub async fn run_archive_loop(mut self, db_path: std::path::PathBuf, interval: std::time::Duration) {
        let conn = match crate::migration::open_and_migrate(&db_path) {
            Ok(c) => c,
            Err(e) => {
                tracing::error!(error = %e, "archive loop failed to open database, exiting");
                return;
            }
        };

        let mut ticker = tokio::time::interval(interval);
        let mut run_id = 0i64;
        loop {
            ticker.tick().await;
            run_id += 1;
            match self.export_all_new(&conn, run_id) {
                Ok(written) if !written.is_empty() => {
                    tracing::info!(files = written.len(), "archive export wrote new parquet files");
                }
                Ok(_) => {}
                Err(e) => tracing::error!(error = %e, "archive export failed"),
            }
        }
    }

    pub fn export_new_bets(&mut self, conn: &Connection, run_id: i64) -> PolarsResult<Vec<PathBuf>> {
        let rows = query_bets_since(conn, self.last_bet_id)?;
        let Some(max_id) = rows.iter().map(|r| r.id).max() else {
            return Ok(Vec::new());
        };
        let written = write_partitioned(&self.archive_dir, "bets", run_id, rows, |group| {
            df! {
                "id" => group.iter().map(|r| r.id).collect::<Vec<_>>(),
                "market_id" => group.iter().map(|r| r.market_id.clone()).collect::<Vec<_>>(),
                "ts_ns" => group.iter().map(|r| r.ts_ns).collect::<Vec<_>>(),
                "prob_before" => group.iter().map(|r| r.prob_before).collect::<Vec<_>>(),
                "prob_after" => group.iter().map(|r| r.prob_after).collect::<Vec<_>>(),
                "amount" => group.iter().map(|r| r.amount).collect::<Vec<_>>(),
                "shares" => group.iter().map(|r| r.shares).collect::<Vec<_>>(),
                "is_limit_order" => group.iter().map(|r| r.is_limit_order).collect::<Vec<_>>(),
            }
        })?;
        self.last_bet_id = max_id;
        Ok(written)
    }

    pub fn export_new_probability_snapshots(
        &mut self,
        conn: &Connection,
        run_id: i64,
    ) -> PolarsResult<Vec<PathBuf>> {
        let rows = query_probability_snapshots_since(conn, self.last_probability_id)?;
        let Some(max_id) = rows.iter().map(|r| r.id).max() else {
            return Ok(Vec::new());
        };
        let written = write_partitioned(&self.archive_dir, "probability_snapshots", run_id, rows, |group| {
            df! {
                "id" => group.iter().map(|r| r.id).collect::<Vec<_>>(),
                "market_id" => group.iter().map(|r| r.market_id.clone()).collect::<Vec<_>>(),
                "ts_ns" => group.iter().map(|r| r.ts_ns).collect::<Vec<_>>(),
                "probability" => group.iter().map(|r| r.probability).collect::<Vec<_>>(),
                "volume_24h" => group.iter().map(|r| r.volume_24h).collect::<Vec<_>>(),
            }
        })?;
        self.last_probability_id = max_id;
        Ok(written)
    }

    pub fn export_new_feature_snapshots(
        &mut self,
        conn: &Connection,
        run_id: i64,
    ) -> PolarsResult<Vec<PathBuf>> {
        let rows = query_feature_snapshots_since(conn, self.last_feature_id)?;
        let Some(max_id) = rows.iter().map(|r| r.id).max() else {
            return Ok(Vec::new());
        };
        let written = write_partitioned(&self.archive_dir, "feature_snapshots", run_id, rows, |group| {
            df! {
                "id" => group.iter().map(|r| r.id).collect::<Vec<_>>(),
                "market_id" => group.iter().map(|r| r.market_id.clone()).collect::<Vec<_>>(),
                "ts_ns" => group.iter().map(|r| r.ts_ns).collect::<Vec<_>>(),
                "prob_velocity" => group.iter().map(|r| r.prob_velocity).collect::<Vec<_>>(),
                "bet_arrival_rate" => group.iter().map(|r| r.bet_arrival_rate).collect::<Vec<_>>(),
                "realized_vol" => group.iter().map(|r| r.realized_vol).collect::<Vec<_>>(),
            }
        })?;
        self.last_feature_id = max_id;
        Ok(written)
    }
}

fn date_partition(ts_ns: i64) -> String {
    DateTime::from_timestamp_nanos(ts_ns)
        .format("%Y-%m-%d")
        .to_string()
}

/// Groups `rows` by the UTC date of `ts_ns_of(row)`, writes one Parquet part file per date group
/// under `<archive_dir>/<table>/dt=<date>/part-<run_id>.parquet`, and returns the paths written.
fn write_partitioned<T>(
    archive_dir: &Path,
    table: &str,
    run_id: i64,
    rows: Vec<T>,
    to_dataframe: impl Fn(&[T]) -> PolarsResult<DataFrame>,
) -> PolarsResult<Vec<PathBuf>>
where
    T: HasTsNs,
{
    let mut by_date: HashMap<String, Vec<T>> = HashMap::new();
    for row in rows {
        by_date.entry(date_partition(row.ts_ns())).or_default().push(row);
    }

    let mut written = Vec::new();
    for (date, group) in by_date {
        let dir = archive_dir.join(table).join(format!("dt={date}"));
        fs::create_dir_all(&dir)
            .map_err(|e| PolarsError::IO { error: e.into(), msg: None })?;
        let path = dir.join(format!("part-{run_id}.parquet"));

        let mut df = to_dataframe(&group)?;
        let file = File::create(&path).map_err(|e| PolarsError::IO { error: e.into(), msg: None })?;
        ParquetWriter::new(file).finish(&mut df)?;
        written.push(path);
    }
    Ok(written)
}

trait HasTsNs {
    fn ts_ns(&self) -> i64;
}

struct BetRow {
    id: i64,
    market_id: String,
    ts_ns: i64,
    prob_before: f64,
    prob_after: f64,
    amount: f64,
    shares: f64,
    is_limit_order: i64,
}
impl HasTsNs for BetRow {
    fn ts_ns(&self) -> i64 {
        self.ts_ns
    }
}

struct ProbabilitySnapshotRow {
    id: i64,
    market_id: String,
    ts_ns: i64,
    probability: f64,
    volume_24h: Option<f64>,
}
impl HasTsNs for ProbabilitySnapshotRow {
    fn ts_ns(&self) -> i64 {
        self.ts_ns
    }
}

struct FeatureSnapshotRow {
    id: i64,
    market_id: String,
    ts_ns: i64,
    prob_velocity: Option<f64>,
    bet_arrival_rate: Option<f64>,
    realized_vol: Option<f64>,
}
impl HasTsNs for FeatureSnapshotRow {
    fn ts_ns(&self) -> i64 {
        self.ts_ns
    }
}

fn query_bets_since(conn: &Connection, since_id: i64) -> PolarsResult<Vec<BetRow>> {
    let mut stmt = conn
        .prepare(
            "SELECT id, market_id, ts_ns, prob_before, prob_after, amount, shares, is_limit_order
             FROM bets WHERE id > ?1 ORDER BY id",
        )
        .map_err(sql_err)?;
    let rows = stmt
        .query_map([since_id], |r| {
            Ok(BetRow {
                id: r.get(0)?,
                market_id: r.get(1)?,
                ts_ns: r.get(2)?,
                prob_before: r.get(3)?,
                prob_after: r.get(4)?,
                amount: r.get(5)?,
                shares: r.get(6)?,
                is_limit_order: r.get(7)?,
            })
        })
        .map_err(sql_err)?
        .collect::<rusqlite::Result<Vec<_>>>()
        .map_err(sql_err)?;
    Ok(rows)
}

fn query_probability_snapshots_since(
    conn: &Connection,
    since_id: i64,
) -> PolarsResult<Vec<ProbabilitySnapshotRow>> {
    let mut stmt = conn
        .prepare(
            "SELECT id, market_id, ts_ns, probability, volume_24h
             FROM probability_snapshots WHERE id > ?1 ORDER BY id",
        )
        .map_err(sql_err)?;
    let rows = stmt
        .query_map([since_id], |r| {
            Ok(ProbabilitySnapshotRow {
                id: r.get(0)?,
                market_id: r.get(1)?,
                ts_ns: r.get(2)?,
                probability: r.get(3)?,
                volume_24h: r.get(4)?,
            })
        })
        .map_err(sql_err)?
        .collect::<rusqlite::Result<Vec<_>>>()
        .map_err(sql_err)?;
    Ok(rows)
}

fn query_feature_snapshots_since(
    conn: &Connection,
    since_id: i64,
) -> PolarsResult<Vec<FeatureSnapshotRow>> {
    let mut stmt = conn
        .prepare(
            "SELECT id, market_id, ts_ns, prob_velocity, bet_arrival_rate, realized_vol
             FROM feature_snapshots WHERE id > ?1 ORDER BY id",
        )
        .map_err(sql_err)?;
    let rows = stmt
        .query_map([since_id], |r| {
            Ok(FeatureSnapshotRow {
                id: r.get(0)?,
                market_id: r.get(1)?,
                ts_ns: r.get(2)?,
                prob_velocity: r.get(3)?,
                bet_arrival_rate: r.get(4)?,
                realized_vol: r.get(5)?,
            })
        })
        .map_err(sql_err)?
        .collect::<rusqlite::Result<Vec<_>>>()
        .map_err(sql_err)?;
    Ok(rows)
}

fn sql_err(e: rusqlite::Error) -> PolarsError {
    PolarsError::ComputeError(format!("sqlite error: {e}").into())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::migration::apply_migrations;

    fn seed_bet(conn: &Connection, market_id: &str, ts_ns: i64, prob_after: f64) {
        conn.execute(
            "INSERT OR IGNORE INTO markets (market_id, platform, question_text, close_time)
             VALUES (?1, 'manifold', '', '')",
            rusqlite::params![market_id],
        )
        .unwrap();
        conn.execute(
            "INSERT INTO bets (market_id, ts_ns, prob_before, prob_after, amount, shares, is_limit_order)
             VALUES (?1, ?2, 0.5, ?3, 10.0, 15.0, 0)",
            rusqlite::params![market_id, ts_ns, prob_after],
        )
        .unwrap();
    }

    const DAY_NS: i64 = 86_400 * 1_000_000_000;
    // 2026-01-01T00:00:00Z, comfortably mid-range so +DAY_NS stays within the same test window.
    const BASE_TS: i64 = 1_767_225_600 * 1_000_000_000;

    #[test]
    fn exported_parquet_round_trips_the_same_data() {
        let conn = Connection::open_in_memory().unwrap();
        apply_migrations(&conn).unwrap();
        seed_bet(&conn, "m1", BASE_TS, 0.6);
        seed_bet(&conn, "m1", BASE_TS + 1_000_000_000, 0.65);

        let tmp = tempfile::tempdir().unwrap();
        let mut exporter = ArchiveExporter::new(tmp.path());
        let written = exporter.export_new_bets(&conn, 1).unwrap();

        assert_eq!(written.len(), 1, "both rows share a date -> one part file");
        let path = &written[0];
        assert!(path.to_string_lossy().contains("dt="));
        assert!(path.file_name().unwrap().to_string_lossy().starts_with("part-1"));

        let file = File::open(path).unwrap();
        let df = ParquetReader::new(file).finish().unwrap();
        assert_eq!(df.height(), 2);

        let prob_after: Vec<f64> = df
            .column("prob_after")
            .unwrap()
            .f64()
            .unwrap()
            .into_no_null_iter()
            .collect();
        assert_eq!(prob_after, vec![0.6, 0.65]);

        let market_ids: Vec<&str> = df
            .column("market_id")
            .unwrap()
            .str()
            .unwrap()
            .iter()
            .map(|v| v.unwrap())
            .collect();
        assert_eq!(market_ids, vec!["m1", "m1"]);
    }

    #[test]
    fn rows_spanning_two_dates_produce_two_part_files() {
        let conn = Connection::open_in_memory().unwrap();
        apply_migrations(&conn).unwrap();
        seed_bet(&conn, "m1", BASE_TS, 0.5); // day 1
        seed_bet(&conn, "m1", BASE_TS + DAY_NS, 0.6); // day 2

        let tmp = tempfile::tempdir().unwrap();
        let mut exporter = ArchiveExporter::new(tmp.path());
        let written = exporter.export_new_bets(&conn, 42).unwrap();

        assert_eq!(written.len(), 2);
    }

    #[test]
    fn watermark_prevents_re_exporting_already_exported_rows() {
        let conn = Connection::open_in_memory().unwrap();
        apply_migrations(&conn).unwrap();
        seed_bet(&conn, "m1", BASE_TS, 0.5);

        let tmp = tempfile::tempdir().unwrap();
        let mut exporter = ArchiveExporter::new(tmp.path());
        let first = exporter.export_new_bets(&conn, 1).unwrap();
        assert_eq!(first.len(), 1);

        // No new rows since the watermark advanced -> nothing to export.
        let second = exporter.export_new_bets(&conn, 2).unwrap();
        assert!(second.is_empty());

        // A genuinely new row after the watermark IS exported.
        seed_bet(&conn, "m1", BASE_TS + 1_000_000_000, 0.55);
        let third = exporter.export_new_bets(&conn, 3).unwrap();
        assert_eq!(third.len(), 1);
    }

    #[test]
    fn no_new_rows_returns_empty_without_creating_files() {
        let conn = Connection::open_in_memory().unwrap();
        apply_migrations(&conn).unwrap();

        let tmp = tempfile::tempdir().unwrap();
        let mut exporter = ArchiveExporter::new(tmp.path());
        let written = exporter.export_all_new(&conn, 1).unwrap();
        assert!(written.is_empty());
    }
}
