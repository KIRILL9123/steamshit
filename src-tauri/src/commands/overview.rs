//! Tauri commands for per-round overview data (replay support).

use tauri::State;

use crate::core::repo::{self, KillEvent, GrenadeEvent};
use crate::core::models::Round;
use crate::error::AppError;
use crate::state::AppState;

#[tauri::command]
pub async fn list_rounds(
    state: State<'_, AppState>,
    id: u64,
) -> Result<Vec<Round>, AppError> {
    let pool = state.db().await?;
    repo::list_rounds(&pool, id).map_err(Into::into)
}

#[tauri::command]
pub async fn get_round_kills(
    state: State<'_, AppState>,
    round_id: u64,
) -> Result<Vec<KillEvent>, AppError> {
    let pool = state.db().await?;
    repo::list_kills_for_round(&pool, round_id).map_err(Into::into)
}

#[tauri::command]
pub async fn get_round_grenades(
    state: State<'_, AppState>,
    round_id: u64,
) -> Result<Vec<GrenadeEvent>, AppError> {
    let pool = state.db().await?;
    repo::list_grenades_for_round(&pool, round_id).map_err(Into::into)
}
