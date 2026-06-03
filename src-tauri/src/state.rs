//! Shared application state.
//!
//! `AppState` is managed by Tauri and accessible from every command via
//! `tauri::State<'_, AppState>`. It holds long-lived resources: the SQLite
//! pool, the Python sidecar handle, and a cached data directory.
//!
//! `AppState` is `Clone` (cheap — all inner state is wrapped in `Arc`) so
//! commands can pass it by value into spawned tasks.

use std::sync::Arc;
use tokio::sync::RwLock;

use crate::core::db::DbPool;
use crate::sidecar::SidecarHandle;

#[derive(Clone)]
pub struct AppState {
    inner: Arc<AppStateInner>,
}

struct AppStateInner {
    /// SQLite connection pool. `None` until `init_db` is called.
    db: RwLock<Option<DbPool>>,
    /// Path to the data directory (`%APPDATA%/CS2Analyzer` on Windows).
    /// Populated lazily — see `data_dir()`.
    data_dir: RwLock<Option<std::path::PathBuf>>,
    /// Sidecar process handle. `None` until first call to `sidecar()`.
    sidecar: RwLock<Option<SidecarHandle>>,
    /// Absolute path to `app.db`. Cached after first init.
    db_path: std::path::PathBuf,
}

impl AppState {
    /// Create a new state container. Pool / sidecar are initialised
    /// lazily on first use (or eagerly via `init_db` / `init_sidecar`).
    pub fn new() -> Self {
        Self {
            inner: Arc::new(AppStateInner {
                db: RwLock::new(None),
                data_dir: RwLock::new(None),
                sidecar: RwLock::new(None),
                db_path: std::path::PathBuf::new(),
            }),
        }
    }

    /// Build a state container that already knows where the DB lives.
    /// Used by `main()` after computing the data dir.
    pub fn with_paths(db_path: std::path::PathBuf, data_dir: std::path::PathBuf) -> Self {
        Self {
            inner: Arc::new(AppStateInner {
                db: RwLock::new(None),
                data_dir: RwLock::new(Some(data_dir)),
                sidecar: RwLock::new(None),
                db_path,
            }),
        }
    }

    /// Returns (and caches) the OS-appropriate data directory.
    pub async fn data_dir(&self) -> std::path::PathBuf {
        {
            let guard = self.inner.data_dir.read().await;
            if let Some(p) = guard.as_ref() {
                return p.clone();
            }
        }
        let path = directories::ProjectDirs::from("com", "cs2analyzer", "CS2Analyzer")
            .map(|p| p.data_dir().to_path_buf())
            .unwrap_or_else(|| std::env::temp_dir().join("CS2Analyzer"));
        if let Err(e) = std::fs::create_dir_all(&path) {
            tracing::warn!("failed to create data dir {:?}: {e}", path);
        }
        *self.inner.data_dir.write().await = Some(path.clone());
        path
    }

    pub fn db_path(&self) -> &std::path::Path {
        &self.inner.db_path
    }

    /// Initialise the DB pool. Idempotent.
    pub async fn init_db(&self) -> crate::AppResult<()> {
        {
            let guard = self.inner.db.read().await;
            if guard.is_some() {
                return Ok(());
            }
        }
        let pool = crate::core::db::open_pool(&self.inner.db_path)?;
        *self.inner.db.write().await = Some(pool);
        Ok(())
    }

    /// Borrow the DB pool, initialising it on first use.
    pub async fn db(&self) -> crate::AppResult<DbPool> {
        self.init_db().await?;
        Ok(self
            .inner
            .db
            .read()
            .await
            .as_ref()
            .expect("db pool initialised")
            .clone())
    }

    /// Configure the sidecar binary path. Does not spawn it.
    pub async fn init_sidecar(&self, binary_path: std::path::PathBuf) {
        let mut guard = self.inner.sidecar.write().await;
        if guard.is_none() {
            *guard = Some(SidecarHandle::new(binary_path));
        }
    }

    /// Borrow the sidecar handle. Returns `None` if `init_sidecar` was
    /// never called.
    pub async fn sidecar(&self) -> Option<SidecarHandle> {
        self.inner.sidecar.read().await.clone()
    }
}

impl Default for AppState {
    fn default() -> Self {
        Self::new()
    }
}
