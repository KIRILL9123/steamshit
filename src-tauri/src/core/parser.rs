//! `.dem` / `.dem.zst` parser — a thin, typed wrapper around the
//! `demoparser2` crate.
//!
//! The full implementation lands in week 4 (see docs/TZ.md §6.1). This
//! skeleton defines the public surface so command stubs, mocks, and the
//! eventual worker pipeline can be wired up against stable types today.
//!
//! Design notes:
//!   * Parsing is **blocking and CPU-bound**, so it runs inside
//!     `tokio::task::spawn_blocking` from the command layer — never on the
//!     async runtime directly.
//!   * Output is exposed as `polars::DataFrame`s for fast aggregation;
//!     `ParsedDemo` owns the frames and they live for the duration of the
//!     parse result.
//!   * Progress is reported via a `crossbeam_channel::Sender<ParseProgress>`
//!     (or `tokio::sync::mpsc` in the async wrapper). The Tauri command
//!     layer bridges that to a Tauri event so the UI can render a progress
//!     bar.

use std::path::{Path, PathBuf};

use polars::prelude::DataFrame;

use crate::error::AppResult;
use crate::core::models::Vec3;

/// One-step progress report (0.0 .. 1.0) emitted during parsing.
#[derive(Debug, Clone, Copy)]
pub struct ParseProgress {
    /// 0.0 at the start, 1.0 when fully parsed.
    pub fraction: f32,
    /// Optional human-readable label (e.g. "Reading events…", "Building ticks…").
    pub label: Option<&'static str>,
}

impl ParseProgress {
    pub const fn new(fraction: f32) -> Self {
        Self {
            fraction,
            label: None,
        }
    }

    pub const fn labelled(fraction: f32, label: &'static str) -> Self {
        Self {
            fraction,
            label: Some(label),
        }
    }
}

/// Parsed match: header metadata + per-event dataframes.
pub struct ParsedDemo {
    pub header: MatchHeader,
    pub rounds: DataFrame,
    pub kills: DataFrame,
    pub damages: DataFrame,
    pub grenades: DataFrame,
    pub smokes: DataFrame,
    pub infernos: DataFrame,
    pub shots: DataFrame,
    pub bomb: DataFrame,
    pub ticks: Option<DataFrame>,
}

/// Lightweight header returned before the heavy dataframe work.
#[derive(Debug, Clone)]
pub struct MatchHeader {
    pub map_name: String,
    pub server_name: Option<String>,
    pub client_name: Option<String>,
    pub demo_type: String,
    pub match_date: Option<String>,
    pub duration_ticks: Option<u32>,
    pub tick_rate: Option<u32>,
    pub players: Vec<PlayerHeader>,
}

#[derive(Debug, Clone)]
pub struct PlayerHeader {
    pub name: String,
    pub steam_id: Option<String>,
    pub team: String,
}

/// Main entry point. Construct with a path, then call `parse` (or
/// `parse_with_progress`).
pub struct DemoParser {
    path: PathBuf,
}

impl DemoParser {
    pub fn new(path: impl AsRef<Path>) -> Self {
        Self {
            path: path.as_ref().to_path_buf(),
        }
    }

    pub fn path(&self) -> &Path {
        &self.path
    }

    /// Parse without progress reporting. The real implementation goes here
    /// in week 4 — for now we return a structured "not yet implemented"
    /// error so the call site compiles.
    pub fn parse(&self) -> AppResult<ParsedDemo> {
        self.parse_with_progress(|_| {})
    }

    /// Parse with a per-tick progress callback.
    ///
    /// The callback is invoked synchronously from the parsing thread; it
    /// should be cheap (e.g. forward to a channel). For week 1 this is a
    /// stub.
    pub fn parse_with_progress<F>(&self, _on_progress: F) -> AppResult<ParsedDemo>
    where
        F: FnMut(ParseProgress) + Send,
    {
        // Week 1: return a structured "not implemented" via the parser
        // module. The actual `demoparser2::Demo::new(path)?.parse_xxx()` call
        // chain is wired in week 4.
        Err(crate::error::AppError::Other(format!(
            "DemoParser::parse is not yet implemented (path: {})",
            self.path.display()
        )))
    }
}

/// Helper for callers that need a single position struct (`Vec3`) from
/// `(x, y, z)` columns. Provided here so models/commands can use one type.
#[allow(dead_code)]
fn vec3(x: f32, y: f32, z: f32) -> Vec3 {
    Vec3::new(x, y, z)
}
