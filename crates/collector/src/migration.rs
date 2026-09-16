use rusqlite::{Connection, Result};
use std::path::Path;

/// Opens (creating if absent) the SQLite database at `path`, switches it to WAL journal mode, and
/// applies migrations. WAL allows the writer connection (this one) and the archive exporter's
/// separate read connection to the same file to coexist without "database is locked" errors —
/// required once `run_archive_loop` opens its own connection alongside the writer's.
pub fn open_and_migrate(path: &Path) -> Result<Connection> {
    let conn = Connection::open(path)?;
    conn.pragma_update(None, "journal_mode", "WAL")?;
    apply_migrations(&conn)?;
    Ok(conn)
}

/// Creates every table from `implementation.md` §5 if it doesn't already exist. Safe to call on
/// every startup — `CREATE TABLE IF NOT EXISTS` makes this idempotent, so the collector doesn't
/// need a separate "has this DB been initialized" check.
///
/// All tables are created now (not just the ones Phase 4 uses) so the schema is stable for later
/// phases — `implementation.md` §5 is the source of truth for column meanings.
pub fn apply_migrations(conn: &Connection) -> Result<()> {
    conn.execute_batch(
        "
        CREATE TABLE IF NOT EXISTS markets (
            market_id TEXT PRIMARY KEY,
            platform TEXT NOT NULL,
            question_text TEXT NOT NULL,
            close_time TEXT NOT NULL,
            resolved_outcome INTEGER
        );

        CREATE TABLE IF NOT EXISTS probability_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            market_id TEXT NOT NULL REFERENCES markets(market_id),
            ts_ns INTEGER NOT NULL,
            probability REAL NOT NULL,
            volume_24h REAL
        );

        CREATE TABLE IF NOT EXISTS bets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            market_id TEXT NOT NULL REFERENCES markets(market_id),
            ts_ns INTEGER NOT NULL,
            prob_before REAL NOT NULL,
            prob_after REAL NOT NULL,
            amount REAL NOT NULL,
            shares REAL NOT NULL,
            is_limit_order INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS feature_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            market_id TEXT NOT NULL REFERENCES markets(market_id),
            ts_ns INTEGER NOT NULL,
            prob_velocity REAL,
            bet_arrival_rate REAL,
            realized_vol REAL
        );

        CREATE TABLE IF NOT EXISTS cross_source_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            market_id TEXT NOT NULL,
            polled_at TEXT NOT NULL,
            community_prediction REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS market_matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            manifold_market_id TEXT NOT NULL REFERENCES markets(market_id),
            platform TEXT NOT NULL DEFAULT 'metaculus',
            external_market_id TEXT NOT NULL,
            confidence REAL,
            status TEXT NOT NULL DEFAULT 'pending'
        );

        CREATE TABLE IF NOT EXISTS model_predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            market_id TEXT NOT NULL REFERENCES markets(market_id),
            ts_ns INTEGER NOT NULL,
            p_model REAL NOT NULL,
            p_market REAL NOT NULL,
            edge REAL NOT NULL,
            ev REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS arbitrage_signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,
            market_refs TEXT NOT NULL,
            edge REAL NOT NULL,
            detected_at TEXT NOT NULL,
            details_json TEXT NOT NULL
        );
        ",
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Table names, excluding SQLite's own internal bookkeeping tables (e.g. `sqlite_sequence`,
    /// auto-created because of `AUTOINCREMENT` — not one of ours).
    fn table_names(conn: &Connection) -> Vec<String> {
        let mut stmt = conn
            .prepare("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
            .unwrap();
        stmt.query_map([], |row| row.get(0))
            .unwrap()
            .map(|r| r.unwrap())
            .collect()
    }

    #[test]
    fn creates_all_expected_tables_on_empty_db() {
        let conn = Connection::open_in_memory().unwrap();
        apply_migrations(&conn).unwrap();

        let tables = table_names(&conn);
        for expected in [
            "arbitrage_signals",
            "bets",
            "cross_source_snapshots",
            "feature_snapshots",
            "market_matches",
            "markets",
            "model_predictions",
            "probability_snapshots",
        ] {
            assert!(tables.contains(&expected.to_string()), "missing table {expected}");
        }
    }

    #[test]
    fn running_migrations_twice_is_idempotent() {
        let conn = Connection::open_in_memory().unwrap();
        apply_migrations(&conn).unwrap();
        apply_migrations(&conn).unwrap(); // must not error on the second run

        let tables = table_names(&conn);
        assert_eq!(tables.len(), 8, "expected exactly 8 tables, got {tables:?}");
    }

    #[test]
    fn migrations_preserve_existing_data_on_rerun() {
        let conn = Connection::open_in_memory().unwrap();
        apply_migrations(&conn).unwrap();
        conn.execute(
            "INSERT INTO markets (market_id, platform, question_text, close_time) VALUES (?1, ?2, ?3, ?4)",
            rusqlite::params!["m1", "manifold", "Will it rain?", "2026-01-01T00:00:00Z"],
        )
        .unwrap();

        apply_migrations(&conn).unwrap(); // re-running must not wipe data

        let count: i64 = conn
            .query_row("SELECT COUNT(*) FROM markets", [], |row| row.get(0))
            .unwrap();
        assert_eq!(count, 1);
    }
}
