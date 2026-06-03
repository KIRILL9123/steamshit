//! SQLite connection pool + refinery migrations.
//!
//! The pool is exposed to the rest of the core as `DbPool = r2d2::Pool<SqliteConnectionManager>`.
//! It is created once at startup via `open_pool` and stored in `AppState`.
//! All access goes through `Pool::get()` which yields a checked-out connection.
//!
//! PRAGMAs:
//!   * `journal_mode = WAL`        — concurrent readers + single writer
//!   * `synchronous  = NORMAL`     — WAL-safe, ~10x faster than FULL
//!   * `foreign_keys = ON`         — per-connection (must be re-applied)
//!   * `temp_store    = MEMORY`     — sort/group_by in RAM
//!
//! Migrations live under `src-tauri/migrations/` and are embedded at compile
//! time so the binary is self-contained (no external `sql/` directory).

use r2d2_sqlite::SqliteConnectionManager;
use refinery::embed_migrations;
use rusqlite::{Connection, OpenFlags};
use std::path::Path;

use crate::error::{AppError, AppResult};

embed_migrations!("migrations");

pub type DbPool = r2d2::Pool<SqliteConnectionManager>;

/// Open (or create) a SQLite database at `db_path` and configure PRAGMAs.
pub fn open_pool(db_path: &Path) -> AppResult<DbPool> {
    if let Some(parent) = db_path.parent() {
        std::fs::create_dir_all(parent).map_err(|e| AppError::io("create db dir", e))?;
    }

    let manager = SqliteConnectionManager::file(db_path)
        .with_flags(
            OpenFlags::SQLITE_OPEN_READ_WRITE
                | OpenFlags::SQLITE_OPEN_CREATE
                | OpenFlags::SQLITE_OPEN_URI,
        )
        .with_init(|c| {
            c.execute_batch(
                "PRAGMA journal_mode = WAL;\
                 PRAGMA synchronous  = NORMAL;\
                 PRAGMA foreign_keys = ON;\
                 PRAGMA temp_store   = MEMORY;\
                 PRAGMA mmap_size    = 268435456;",
            )
        });

    let pool = r2d2::Pool::builder()
        .max_size(8)
        .min_idle(Some(1))
        .build(manager)
        .map_err(|e| AppError::Other(format!("create db pool: {e}")))?;

    // Verify the connection + PRAGMAs by running a quick check.
    {
        let conn = pool.get().map_err(map_pool_err)?;
        let mode: String = conn
            .query_row("PRAGMA journal_mode", [], |r| r.get(0))
            .unwrap_or_default();
        tracing::info!("sqlite journal_mode = {mode}");
    }

    Ok(pool)
}

/// Apply all pending refinery migrations against `db_path`.
///
/// We open a separate short-lived connection (not from the pool) because
/// refinery's `runner().run()` takes `&mut rusqlite::Connection` and we don't
/// want to keep a pool slot busy during migration. The migrations are
/// idempotent: refinery records applied versions in `refinery_schema_history`.
pub fn run_migrations(db_path: &Path) -> AppResult<()> {
    if let Some(parent) = db_path.parent() {
        std::fs::create_dir_all(parent).map_err(|e| AppError::io("create db dir", e))?;
    }

    let mut conn = Connection::open(db_path).map_err(map_rusqlite_err)?;
    conn.execute_batch(
        "PRAGMA journal_mode = WAL;\
         PRAGMA synchronous  = NORMAL;\
         PRAGMA foreign_keys = ON;",
    )
    .map_err(map_rusqlite_err)?;

    let report = migrations::runner()
        .run(&mut conn)
        .map_err(|e| AppError::Other(format!("run migrations: {e}")))?;

    tracing::info!(
        "applied {} migration(s); versions: {:?}",
        report.applied_migrations().len(),
        report
            .applied_migrations()
            .iter()
            .map(|m| m.version())
            .collect::<Vec<_>>()
    );
    Ok(())
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

fn map_pool_err(e: r2d2::Error) -> AppError {
    AppError::Other(format!("db pool: {e}"))
}

fn map_rusqlite_err(e: rusqlite::Error) -> AppError {
    AppError::Other(format!("sqlite: {e}"))
}
