//! Async client for the Python sidecar.
//!
//! Protocol: newline-delimited JSON over the child's stdio (stdin/stdout).
//! `stdin` is half-duplex from our side — we serialise a `Request` per
//! line. `stdout` is line-buffered and we read it with a small background
//! task that fans out responses to waiting callers by `id`.
//!
//! Errors:
//!   * Spawn / IO failures → `AppError::Other` (week 12: dedicated
//!     `AppErrorKind::Sidecar` variant).
//!   * Sidecar-reported errors → wrapped from `SidecarError`.
//!   * Protocol errors (non-JSON, mismatched id) → `AppError::Other`.
//!
//! Week 1: structure only. Spawn, send/recv round-trip and shutdown work
//! with a trivial `cat`-like stub for smoke tests. The real awpy-side
//! methods land in week 12.

use std::collections::HashMap;
use std::process::Stdio;
use std::sync::Arc;

use serde_json::Value;
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};
use tokio::process::{Child, Command};
use tokio::sync::{oneshot, Mutex};

use crate::error::{AppError, AppResult};

use super::{Request, Response};

/// Cheap-cloneable handle to a running sidecar process.
#[derive(Clone)]
pub struct SidecarClient {
    inner: Arc<SidecarClientInner>,
}

struct SidecarClientInner {
    /// Stdin writer (so the child can keep reading while we await a reply).
    stdin: Mutex<tokio::process::ChildStdin>,
    /// Pending requests keyed by `Request::id`; resolved by the reader task.
    pending: Mutex<HashMap<String, oneshot::Sender<AppResult<Response>>>>,
    /// Keep the `Child` handle alive (dropping it sends SIGKILL on Unix).
    child: Mutex<Option<Child>>,
}

impl SidecarClient {
    /// Spawn the sidecar process. The first line the child writes to
    /// stdout is expected to be a JSON greeting — for week 1 we accept any
    /// startup behaviour; real handshake comes in week 12.
    pub async fn spawn(binary_path: &std::path::Path) -> AppResult<Self> {
        let mut child = Command::new(binary_path)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .kill_on_drop(true)
            .spawn()
            .map_err(|e| AppError::Other(format!("spawn sidecar: {e}")))?;

        let stdin = child
            .stdin
            .take()
            .ok_or_else(|| AppError::Other("sidecar stdin missing".into()))?;
        let stdout = child
            .stdout
            .take()
            .ok_or_else(|| AppError::Other("sidecar stdout missing".into()))?;
        let stderr = child
            .stderr
            .take()
            .ok_or_else(|| AppError::Other("sidecar stderr missing".into()))?;

        let client = Self {
            inner: Arc::new(SidecarClientInner {
                stdin: Mutex::new(stdin),
                pending: Mutex::new(HashMap::new()),
                child: Mutex::new(Some(child)),
            }),
        };

        // Reader task: forwards each stdout line to the right pending caller.
        {
            let inner = client.inner.clone();
            tokio::spawn(reader_task(inner, stdout));
        }
        // Stderr task: just logs to tracing.
        {
            tokio::spawn(async move {
                use tokio::io::AsyncBufReadExt as _;
                let mut lines = BufReader::new(stderr).lines();
                while let Ok(Some(line)) = lines.next_line().await {
                    tracing::warn!(target: "sidecar", "{}", line);
                }
            });
        }

        Ok(client)
    }

    /// Send a request and await its response.
    pub async fn call(&mut self, method: &str, params: Value) -> AppResult<Value> {
        let req = Request::new(method, params);
        let id = req.id.clone();

        let (tx, rx) = oneshot::channel();
        self.inner.pending.lock().await.insert(id.clone(), tx);

        self.send(req).await?;

        let resp = rx
            .await
            .map_err(|_| AppError::Other("sidecar response channel closed".into()))??;

        if resp.id != id {
            return Err(AppError::Other(format!(
                "sidecar id mismatch: sent {id}, got {}",
                resp.id
            )));
        }
        if !resp.ok {
            return Err(resp
                .error
                .map(Into::into)
                .unwrap_or_else(|| AppError::Other("sidecar reported error".into())));
        }
        Ok(resp.result.unwrap_or(Value::Null))
    }

    /// Send a request without awaiting a response.
    pub async fn notify(&mut self, method: &str, params: Value) -> AppResult<()> {
        let req = Request::new(method, params);
        self.send(req).await
    }

    /// Kill the child process. Idempotent.
    pub async fn shutdown(&mut self) {
        let mut guard = self.inner.child.lock().await;
        if let Some(mut c) = guard.take() {
            let _ = c.kill().await;
        }
    }

    // -----------------------------------------------------------------------

    async fn send(&self, req: Request) -> AppResult<()> {
        let mut line = serde_json::to_string(&req)
            .map_err(|e| AppError::Other(format!("serialise request: {e}")))?;
        line.push('\n');
        let mut stdin = self.inner.stdin.lock().await;
        stdin
            .write_all(line.as_bytes())
            .await
            .map_err(|e| AppError::Other(format!("write to sidecar: {e}")))?;
        stdin
            .flush()
            .await
            .map_err(|e| AppError::Other(format!("flush sidecar: {e}")))?;
        Ok(())
    }
}

async fn reader_task(inner: Arc<SidecarClientInner>, stdout: tokio::process::ChildStdout) {
    let mut lines = BufReader::new(stdout).lines();
    loop {
        match lines.next_line().await {
            Ok(Some(line)) => {
                let parsed: Result<Response, _> = serde_json::from_str(&line);
                match parsed {
                    Ok(resp) => {
                        let mut pending = inner.pending.lock().await;
                        if let Some(tx) = pending.remove(&resp.id) {
                            // Convert protocol-level error into AppError here
                            // so the awaiting caller can pattern-match.
                            let _ = tx.send(Ok(resp));
                        } else {
                            tracing::debug!(
                                target: "sidecar",
                                "ignoring unsolicited response id={}", resp.id
                            );
                        }
                    }
                    Err(e) => {
                        tracing::warn!(target: "sidecar", "non-JSON line: {e}: {line}");
                    }
                }
            }
            Ok(None) => {
                tracing::info!(target: "sidecar", "stdout closed; draining pending callers");
                let mut pending = inner.pending.lock().await;
                for (_, tx) in pending.drain() {
                    let _ = tx.send(Err(AppError::Other("sidecar closed".into())));
                }
                break;
            }
            Err(e) => {
                tracing::error!(target: "sidecar", "read error: {e}");
                break;
            }
        }
    }
}
