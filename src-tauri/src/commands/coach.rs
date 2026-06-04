//! Tauri commands for coaching tips.

use tauri::State;

use crate::core::{coach, repo};
use crate::error::AppError;
use crate::state::AppState;

#[tauri::command]
pub async fn get_coach_tips(
    state: State<'_, AppState>,
    id: u64,
    player: Option<String>,
) -> Result<Vec<crate::core::models::CoachTip>, AppError> {
    let pool = state.db().await?;

    // Try cache first
    let cached = repo::list_coach_tips(&pool, id, player.as_deref())?;
    if !cached.is_empty() {
        return Ok(cached);
    }

    // Generate fresh tips
    let sidecar = state.sidecar().await.ok_or_else(|| AppError::Other("Sidecar not initialized".into()))?;
    let db_path = state.db_path();
    coach::generate_and_store(&pool, &sidecar, db_path.to_string_lossy().as_ref(), id).await?;
    repo::list_coach_tips(&pool, id, player.as_deref())
}

/// Force regenerate coaching tips.
#[tauri::command]
pub async fn regenerate_coach_tips(
    state: State<'_, AppState>,
    id: u64,
) -> Result<Vec<crate::core::models::CoachTip>, AppError> {
    let pool = state.db().await?;
    let sidecar = state
        .sidecar()
        .await
        .ok_or_else(|| AppError::Other("Sidecar not initialized".into()))?;
    let db_path = state.db_path();
    coach::generate_and_store(&pool, &sidecar, db_path.to_string_lossy().as_ref(), id).await?;
    repo::list_coach_tips(&pool, id, None)
}
