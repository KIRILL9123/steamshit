//! Tauri commands for heatmap data.

use serde::Serialize;
use tauri::State;

use crate::core::repo;
use crate::error::AppError;
use crate::state::AppState;

/// A 2D point for heatmap rendering.
#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct HeatmapPoint {
    pub x: f32,
    pub y: f32,
    pub kind: HeatmapKind,
}

#[derive(Debug, Serialize, Clone, Copy, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum HeatmapKind {
    KillAttacker,
    KillVictim,
}

/// Return heatmap points for kill positions.
/// `player`: optional player name filter
#[tauri::command]
pub async fn get_heatmap_data(
    state: State<'_, AppState>,
    id: u64,
    player: Option<String>,
) -> Result<Vec<HeatmapPoint>, AppError> {
    let pool = state.db().await?;
    let positions = repo::list_kill_positions(&pool, id, player.as_deref())?;
    let mut points = Vec::with_capacity(positions.len() * 2);
    for (ax, ay, vx, vy) in positions {
        if let (Some(x), Some(y)) = (ax, ay) {
            points.push(HeatmapPoint { x, y, kind: HeatmapKind::KillAttacker });
        }
        if let (Some(x), Some(y)) = (vx, vy) {
            points.push(HeatmapPoint { x, y, kind: HeatmapKind::KillVictim });
        }
    }
    Ok(points)
}
