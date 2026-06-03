//! `system` commands — meta commands (ping, app info, paths).
//!
//! Used by the frontend on startup to verify the IPC bridge works and
//! to discover the data directory. Real command surface (matches, replay,
//! heatmaps, …) is added in later weeks.

use serde::Serialize;
use tauri::State;

use crate::state::AppState;

#[derive(Debug, Serialize)]
pub struct AppInfo {
    pub name: &'static str,
    pub version: &'static str,
    pub data_dir: String,
    pub db_path: String,
    pub backend: &'static str,
    pub sidecar_alive: bool,
}

#[tauri::command]
pub async fn ping() -> &'static str {
    "pong"
}

#[tauri::command]
pub async fn app_info(state: State<'_, AppState>) -> Result<AppInfo, crate::AppError> {
    let data_dir = state.data_dir().await;
    let db_path = state.db_path().to_string_lossy().into_owned();
    let sidecar_alive = state
        .sidecar()
        .await
        .map(|h| futures::executor::block_on(h.is_alive()))
        .unwrap_or(false);
    Ok(AppInfo {
        name: "CS2 Analyzer",
        version: env!("CARGO_PKG_VERSION"),
        data_dir: data_dir.to_string_lossy().into_owned(),
        db_path,
        backend: "rust+python-sidecar",
        sidecar_alive,
    })
}
