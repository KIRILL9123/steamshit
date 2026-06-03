//! Python sidecar client stub.
//!
//! The sidecar process is a Python interpreter that runs the awpy-backed
//! analytics the Rust core delegates to: visibility (BVH), navmesh lookups,
//! advanced anticheat heuristics, trend analysis, and the future LLM coach.
//!
//! Wire format: **newline-delimited JSON over stdio**.
//!   * Request: `{"id": "uuid", "method": "visibility.compute", "params": {...}}`
//!   * Response: `{"id": "uuid", "ok": true, "result": {...}}` or
//!               `{"id": "uuid", "ok": false, "error": {"kind": "...", "message": "..."}}`
//!
//! Week 1: type definitions and a hand-rolled async client over
//! `tokio::process::Child`. The real launcher (Tauri `externalBin`,
//! subprocess on macOS/Linux, etc.) is wired in week 12.

use std::collections::HashMap;
use std::path::PathBuf;

use serde::{Deserialize, Serialize};
use serde_json::Value;
use tokio::sync::Mutex;
use uuid::Uuid;

use crate::error::{AppError, AppResult};

pub mod client;

pub use client::SidecarClient;

// ---------------------------------------------------------------------------
// IPC envelope
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Request {
    pub id: String,
    pub method: String,
    pub params: Value,
}

impl Request {
    pub fn new(method: impl Into<String>, params: Value) -> Self {
        Self {
            id: Uuid::new_v4().to_string(),
            method: method.into(),
            params,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Response {
    pub id: String,
    pub ok: bool,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub result: Option<Value>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub error: Option<SidecarError>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SidecarError {
    pub kind: String,
    pub message: String,
}

impl From<SidecarError> for AppError {
    fn from(e: SidecarError) -> Self {
        AppError::Other(format!("sidecar[{}]: {}", e.kind, e.message))
    }
}

// ---------------------------------------------------------------------------
// Method names (string constants used by the call site and the Python side)
// ---------------------------------------------------------------------------

pub mod methods {
    pub const PING: &str = "system.ping";
    pub const VERSION: &str = "system.version";

    pub const PARSE_DEMO: &str = "parser.parse_demo";

    pub const VISIBILITY_COMPUTE: &str = "visibility.compute";
    pub const NAVMESH_FIND_PATH: &str = "navmesh.find_path";
    pub const ANTICHEAT_RUN_HEURISTIC: &str = "anticheat.run_heuristic";
    pub const COACH_GENERATE_TIPS: &str = "coach.generate_tips";
    pub const TRENDS_COMPUTE: &str = "trends.compute";
}

// ---------------------------------------------------------------------------
// Handle — owned by AppState
// ---------------------------------------------------------------------------

/// Handle to the (optionally running) sidecar process. Cheap to clone.
#[derive(Clone)]
pub struct SidecarHandle {
    inner: std::sync::Arc<SidecarHandleInner>,
}

struct SidecarHandleInner {
    /// Absolute path to the sidecar binary (or Python entrypoint in dev).
    binary_path: PathBuf,
    /// Lazily-initialised client. None until `get()` is first called.
    client: Mutex<Option<SidecarClient>>,
}

impl SidecarHandle {
    pub fn new(binary_path: impl Into<PathBuf>) -> Self {
        Self {
            inner: std::sync::Arc::new(SidecarHandleInner {
                binary_path: binary_path.into(),
                client: Mutex::new(None),
            }),
        }
    }

    pub fn binary_path(&self) -> &PathBuf {
        &self.inner.binary_path
    }

    /// Borrow the client, spawning the sidecar on first use.
    pub async fn client(&self) -> AppResult<SidecarClient> {
        let mut guard = self.inner.client.lock().await;
        if guard.is_none() {
            let c = SidecarClient::spawn(&self.inner.binary_path).await?;
            *guard = Some(c);
        }
        Ok(guard.as_ref().unwrap().clone())
    }

    /// Send a method call. Convenience around `client().call(...)`.
    pub async fn call(&self, method: &str, params: Value) -> AppResult<Value> {
        let mut c = self.client().await?;
        c.call(method, params).await
    }

    /// Send a method call without awaiting a response (fire-and-forget).
    pub async fn notify(&self, method: &str, params: Value) -> AppResult<()> {
        let mut c = self.client().await?;
        c.notify(method, params).await
    }

    /// Shutdown the sidecar (kills the child process). Safe to call when
    /// the sidecar was never started.
    pub async fn shutdown(&self) {
        let mut guard = self.inner.client.lock().await;
        if let Some(c) = guard.as_mut() {
            c.shutdown().await;
        }
        *guard = None;
    }

    /// Quick health check (returns `true` if the sidecar responded to a
    /// `system.ping` within a short timeout).
    pub async fn is_alive(&self) -> bool {
        match self
            .call(methods::PING, Value::Object(Default::default()))
            .await
        {
            Ok(v) => v.as_str().map(|s| s == "pong").unwrap_or(false),
            Err(_) => false,
        }
    }

    /// Convenience for tests: register a custom set of expected method
    /// names. Not used in production.
    #[allow(dead_code)]
    pub fn expected_methods() -> HashMap<&'static str, &'static str> {
        let mut m = HashMap::new();
        m.insert(methods::PING, "system");
        m.insert(methods::VERSION, "system");
        m.insert(methods::PARSE_DEMO, "parser");
        m.insert(methods::VISIBILITY_COMPUTE, "analytics");
        m.insert(methods::NAVMESH_FIND_PATH, "analytics");
        m.insert(methods::ANTICHEAT_RUN_HEURISTIC, "analytics");
        m.insert(methods::COACH_GENERATE_TIPS, "coach");
        m.insert(methods::TRENDS_COMPUTE, "trends");
        m
    }
}
