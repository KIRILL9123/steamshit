//! Tauri commands related to match import and listing.

use std::path::PathBuf;

use serde::Serialize;
use tauri::{AppHandle, State};

use crate::core::db::DbPool;
use crate::core::import;
use crate::core::models::{Match, Player, PlayerMatchStats};
use crate::core::repo;
use crate::error::{AppError, AppResult};
use crate::state::AppState;

// ---------------------------------------------------------------------------
// import_demo
// ---------------------------------------------------------------------------

#[derive(Debug, Serialize)]
pub struct ImportResult {
    pub match_row: Match,
    pub reused: bool,
}

#[tauri::command]
pub async fn import_demo(
    app: AppHandle,
    state: State<'_, AppState>,
    path: String,
) -> Result<Match, AppError> {
    let path_buf = PathBuf::from(&path);
    if !path_buf.exists() {
        return Err(AppError::invalid(format!("file not found: {path}")));
    }
    let sidecar = state
        .sidecar()
        .await
        .ok_or_else(|| AppError::Sidecar("sidecar not initialised".into()))?;
    let pool = state.db().await?;
    let m = import::import_demo(app, pool, sidecar, &path_buf).await?;
    Ok(m)
}

// ---------------------------------------------------------------------------
// list_matches / get_match / delete_match
// ---------------------------------------------------------------------------

#[tauri::command]
pub async fn list_matches(state: State<'_, AppState>) -> Result<Vec<Match>, AppError> {
    let pool = state.db().await?;
    repo::list_matches(&pool).map_err(Into::into)
}

#[derive(Debug, Serialize)]
pub struct MatchDetail {
    #[serde(flatten)]
    pub header: Match,
    pub players: Vec<Player>,
    pub stats: Vec<PlayerMatchStats>,
}

#[tauri::command]
pub async fn get_match(state: State<'_, AppState>, id: u64) -> Result<MatchDetail, AppError> {
    let pool = state.db().await?;
    let header = repo::get_match(&pool, id)?;
    let players = repo::list_players(&pool, id)?;
    let stats = list_stats(&pool, id)?;
    Ok(MatchDetail {
        header,
        players,
        stats,
    })
}

#[tauri::command]
pub async fn delete_match(state: State<'_, AppState>, id: u64) -> Result<(), AppError> {
    let pool = state.db().await?;
    repo::delete_match(&pool, id)
}

#[tauri::command]
pub async fn get_round_progression(
    state: State<'_, AppState>,
    id: u64,
) -> Result<Vec<repo::RoundProgression>, AppError> {
    let pool = state.db().await?;
    repo::list_round_progression(&pool, id).map_err(Into::into)
}

fn list_stats(pool: &DbPool, match_id: u64) -> AppResult<Vec<PlayerMatchStats>> {
    let conn = pool.get().map_err(map_pool_err)?;
    let mut stmt = conn
        .prepare(
            "SELECT * FROM player_match_stats WHERE match_id = ?1
             ORDER BY rating DESC, kills DESC",
        )
        .map_err(map_sqlite)?;
    let rows = stmt
        .query_map([match_id as i64], |row| {
            Ok(PlayerMatchStats {
                match_id: row.get::<_, i64>("match_id")? as u64,
                player: row.get("player")?,
                team: row
                    .get::<_, Option<String>>("team")?
                    .as_deref()
                    .map(crate::core::models::Team::from_str),
                kills: row.get::<_, i64>("kills")? as u32,
                deaths: row.get::<_, i64>("deaths")? as u32,
                assists: row.get::<_, i64>("assists")? as u32,
                damage: row.get::<_, i64>("damage")? as u32,
                adr: row.get::<_, f64>("adr")? as f32,
                kast: row.get::<_, f64>("kast")? as f32,
                rating: row.get::<_, f64>("rating")? as f32,
                hs_pct: row.get::<_, f64>("hs_pct")? as f32,
                head_shots: row.get::<_, i64>("head_shots")? as u32,
                multi_kills_2k: row.get::<_, i64>("multi_kills_2k")? as u32,
                multi_kills_3k: row.get::<_, i64>("multi_kills_3k")? as u32,
                multi_kills_4k: row.get::<_, i64>("multi_kills_4k")? as u32,
                multi_kills_5k: row.get::<_, i64>("multi_kills_5k")? as u32,
                clutches_won: row.get::<_, i64>("clutches_won")? as u32,
                clutches_total: row.get::<_, i64>("clutches_total")? as u32,
                entry_kills: row.get::<_, i64>("entry_kills")? as u32,
                entry_deaths: row.get::<_, i64>("entry_deaths")? as u32,
                utility_damage: row.get::<_, i64>("utility_damage")? as u32,
                utility_enemies_flashed: row.get::<_, i64>("utility_enemies_flashed")? as u32,
                flash_assists: row.get::<_, i64>("flash_assists")? as u32,
                first_bloods: row.get::<_, i64>("first_bloods")? as u32,
                mvp_count: row.get::<_, i64>("mvp_count")? as u32,
            })
        })
        .map_err(map_sqlite)?;
    let mut out = Vec::new();
    for r in rows {
        out.push(r.map_err(map_sqlite)?);
    }
    Ok(out)
}

fn map_pool_err(e: r2d2::Error) -> AppError {
    AppError::Other(format!("db pool: {e}"))
}

fn map_sqlite(e: rusqlite::Error) -> AppError {
    AppError::Other(format!("sqlite: {e}"))
}
