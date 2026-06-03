//! Demo parser — a thin Rust wrapper around the Python sidecar's
//! `parser.parse_demo` method (which uses `awpy` over `demoparser2`).
//!
//! The actual file parsing is CPU-bound and lives in another process; this
//! module is just the IPC shim + typed deserialisation of the response.
//!
//! Progress reporting: the import command emits Tauri events with the
//! following shape:
//!   * `import:start`     — `{ "path": "..." }`
//!   * `import:parsing`   — `{ "fraction": 0.2, "label": "Парсинг..." }`
//!   * `import:writing`   — `{ "fraction": 0.7 }`
//!   * `import:done`      — `{ "match_id": 42 }`
//!   * `import:error`     — `{ "message": "..." }`
//!
//! The Python sidecar is invoked synchronously; we report progress as the
//! orchestrator (`core::import`) advances through its stages.

use std::path::{Path, PathBuf};

use serde::{Deserialize, Serialize};

use crate::error::{AppError, AppResult};
use crate::sidecar::SidecarHandle;

/// Parsed demo as returned by the Python sidecar. Field naming mirrors
/// the Python module so deserialisation is straightforward.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ParsedDemo {
    pub header: HeaderJson,
    pub players: Vec<PlayerJson>,
    pub rounds: Vec<serde_json::Value>,
    pub kills: Vec<serde_json::Value>,
    pub damages: Vec<serde_json::Value>,
    pub grenades: Vec<serde_json::Value>,
    pub smokes: Vec<serde_json::Value>,
    pub infernos: Vec<serde_json::Value>,
    pub shots: Vec<serde_json::Value>,
    pub bomb: Vec<serde_json::Value>,
    #[serde(default)]
    pub ticks: Vec<serde_json::Value>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HeaderJson {
    pub map_name: String,
    pub server_name: Option<String>,
    pub client_name: Option<String>,
    pub demo_type: Option<String>,
    pub match_date: Option<String>,
    pub duration_ticks: Option<u32>,
    pub tick_rate: Option<u32>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PlayerJson {
    pub name: String,
    pub steam_id: Option<String>,
    pub team: Option<String>,
    pub user_id: Option<i64>,
}

#[derive(Debug, Clone, Copy)]
pub struct ParseOptions {
    pub include_ticks: bool,
}

impl Default for ParseOptions {
    fn default() -> Self {
        Self {
            include_ticks: false,
        }
    }
}

/// DemoParser — constructed with a sidecar handle and an optional path.
/// Path is optional because the orchestrator (`core::import`) may stream
/// progress before parsing starts.
pub struct DemoParser<'a> {
    sidecar: &'a SidecarHandle,
    path: PathBuf,
}

impl<'a> DemoParser<'a> {
    pub fn new(sidecar: &'a SidecarHandle, path: impl AsRef<Path>) -> Self {
        Self {
            sidecar,
            path: path.as_ref().to_path_buf(),
        }
    }

    pub fn path(&self) -> &Path {
        &self.path
    }

    /// Parse via the sidecar. Returns a `ParsedDemo` ready to be written
    /// to the DB.
    pub async fn parse(&self) -> AppResult<ParsedDemo> {
        self.parse_with(ParseOptions::default()).await
    }

    pub async fn parse_with(&self, opts: ParseOptions) -> AppResult<ParsedDemo> {
        let params = serde_json::json!({
            "path": self.path.to_string_lossy(),
            "include_ticks": opts.include_ticks,
        });
        let result = self
            .sidecar
            .call(crate::sidecar::methods::PARSE_DEMO, params)
            .await
            .map_err(|e| AppError::parse(format!("sidecar parse_demo: {e}")))?;
        let parsed: ParsedDemo = serde_json::from_value(result)
            .map_err(|e| AppError::parse(format!("decode parse_demo response: {e}")))?;
        Ok(parsed)
    }
}
