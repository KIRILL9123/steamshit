//! Tauri commands for anticheat analysis.

use tauri::State;

use crate::core::{anticheat, repo};
use crate::error::AppError;
use crate::state::AppState;

/// Run anticheat heuristics for a match and return the flags.
/// Also persists results to the DB for caching.
#[tauri::command]
pub async fn get_anticheat_flags(
    state: State<'_, AppState>,
    id: u64,
) -> Result<Vec<crate::core::models::AnticheatFlag>, AppError> {
    let pool = state.db().await?;

    // Check if we have cached flags
    let cached = repo::list_anticheat_flags(&pool, id)?;
    if !cached.is_empty() {
        return Ok(cached);
    }

    // Run fresh analysis
    let flags = anticheat::analyse(&pool, id)?;
    repo::upsert_anticheat_flags(&pool, id, &flags)?;
    Ok(flags)
}

/// Force re-run anticheat analysis (ignores cache).
#[tauri::command]
pub async fn compute_anticheat(
    state: State<'_, AppState>,
    id: u64,
) -> Result<Vec<crate::core::models::AnticheatFlag>, AppError> {
    let pool = state.db().await?;
    let flags = anticheat::analyse(&pool, id)?;
    repo::upsert_anticheat_flags(&pool, id, &flags)?;
    Ok(flags)
}
