//! Repository layer: thin SQL facade over the `r2d2` connection pool.
//!
//! All writes from the parser/import flow go through this module so the
//! schema mapping is in exactly one place. All reads (for the UI) too —
//! the command layer never issues raw SQL.
//!
//! Conventions:
//!   * One `*Repo` struct per top-level entity? No — we keep things simple
//!     and have free functions grouped by table.
//!   * Functions returning `Vec<T>` use `from_row` to build typed results.
//!   * Writes use a single transaction when they touch multiple tables
//!     (matches + players + rounds + kills + …).

use std::path::Path;

use crate::core::db::DbPool;
use crate::core::models::*;
use crate::error::{AppError, AppResult};

/// Bulk-insert a list of rows into `table` using positional placeholders.
/// Column order in `cols` must match the values yielded by `row_fn`.
#[allow(dead_code)]
fn bulk_insert<T, F>(
    conn: &rusqlite::Connection,
    table: &str,
    cols: &[&str],
    rows: &[T],
    row_fn: F,
) -> AppResult<usize>
where
    F: Fn(&T) -> Vec<rusqlite::types::Value>,
{
    if rows.is_empty() {
        return Ok(0);
    }
    let placeholders = std::iter::repeat("?")
        .take(cols.len())
        .collect::<Vec<_>>()
        .join(",");
    let col_list = cols.join(",");
    let sql = format!("INSERT INTO {table} ({col_list}) VALUES ({placeholders})");
    let mut stmt = conn.prepare(&sql).map_err(map_sqlite_err)?;
    let mut total = 0usize;
    for r in rows {
        let params = rusqlite::params_from_iter(row_fn(r));
        stmt.execute(params).map_err(map_sqlite_err)?;
        total += 1;
    }
    Ok(total)
}

// ---------------------------------------------------------------------------
// matches table
// ---------------------------------------------------------------------------

pub struct InsertMatch {
    pub file_path: String,
    pub file_hash: String,
    pub file_size: Option<u64>,
    pub map_name: String,
    pub server_name: Option<String>,
    pub client_name: Option<String>,
    pub demo_type: Option<String>,
    pub match_date: Option<String>,
    pub duration_ticks: Option<u32>,
    pub parse_version: u32,
}

pub fn insert_match(pool: &DbPool, m: InsertMatch) -> AppResult<u64> {
    let conn = pool.get().map_err(map_pool_err)?;
    let parsed_at = chrono::Utc::now().to_rfc3339();
    conn.execute(
        "INSERT INTO matches (
            file_path, file_hash, file_size, map_name, server_name, client_name,
            demo_type, match_date, duration_ticks, parsed_at, parse_version
         ) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11)",
        rusqlite::params![
            m.file_path,
            m.file_hash,
            m.file_size,
            m.map_name,
            m.server_name,
            m.client_name,
            m.demo_type,
            m.match_date,
            m.duration_ticks,
            parsed_at,
            m.parse_version as i64,
        ],
    )
    .map_err(map_sqlite_err)?;
    Ok(conn.last_insert_rowid() as u64)
}

pub fn find_match_by_hash(pool: &DbPool, hash: &str) -> AppResult<Option<Match>> {
    let conn = pool.get().map_err(map_pool_err)?;
    let mut stmt = conn
        .prepare("SELECT * FROM matches WHERE file_hash = ?1 LIMIT 1")
        .map_err(map_sqlite_err)?;
    let mut rows = stmt.query([hash]).map_err(map_sqlite_err)?;
    if let Some(row) = rows.next().map_err(map_sqlite_err)? {
        Ok(Some(row_to_match(&row).map_err(map_sqlite_err)?))
    } else {
        Ok(None)
    }
}

pub fn list_matches(pool: &DbPool) -> AppResult<Vec<Match>> {
    let conn = pool.get().map_err(map_pool_err)?;
    let mut stmt = conn
        .prepare("SELECT * FROM matches ORDER BY match_date DESC NULLS LAST, parsed_at DESC")
        .map_err(map_sqlite_err)?;
    let rows = stmt
        .query_map([], |row| row_to_match(row))
        .map_err(map_sqlite_err)?;
    let mut out = Vec::new();
    for r in rows {
        out.push(r.map_err(map_sqlite_err)?);
    }
    Ok(out)
}

pub fn get_match(pool: &DbPool, id: u64) -> AppResult<Match> {
    let conn = pool.get().map_err(map_pool_err)?;
    conn.query_row("SELECT * FROM matches WHERE id = ?1", [id], |row| {
        row_to_match(row)
    })
    .map_err(map_sqlite_err)
}

pub fn delete_match(pool: &DbPool, id: u64) -> AppResult<()> {
    let conn = pool.get().map_err(map_pool_err)?;
    conn.execute("DELETE FROM matches WHERE id = ?1", [id])
        .map_err(map_sqlite_err)?;
    Ok(())
}

/// Round-by-round score snapshot used by the Overview line chart.
#[derive(Debug, Clone, serde::Serialize)]
#[serde(rename_all = "camelCase")]
pub struct RoundProgression {
    pub round_num: u32,
    pub ct_score: u32,
    pub t_score: u32,
    pub winner: Option<String>,
    pub reason: Option<String>,
    pub bomb_plant: bool,
}

pub fn list_round_progression(pool: &DbPool, match_id: u64) -> AppResult<Vec<RoundProgression>> {
    let conn = pool.get().map_err(map_pool_err)?;
    let mut stmt = conn
        .prepare(
            "SELECT round_num, ct_score, t_score, winner, reason, bomb_plant
             FROM rounds
             WHERE match_id = ?1
             ORDER BY round_num ASC",
        )
        .map_err(map_sqlite_err)?;
    let rows = stmt
        .query_map([match_id as i64], |row| {
            Ok(RoundProgression {
                round_num: row.get::<_, i64>(0)? as u32,
                ct_score: row.get::<_, Option<i64>>(1)?.unwrap_or(0) as u32,
                t_score: row.get::<_, Option<i64>>(2)?.unwrap_or(0) as u32,
                winner: row.get(3)?,
                reason: row.get(4)?,
                bomb_plant: row.get::<_, i64>(5)? != 0,
            })
        })
        .map_err(map_sqlite_err)?;
    let mut out = Vec::new();
    for r in rows {
        out.push(r.map_err(map_sqlite_err)?);
    }
    Ok(out)
}

fn row_to_match(row: &rusqlite::Row) -> rusqlite::Result<Match> {
    let demo_type_str: Option<String> = row.get("demo_type")?;
    Ok(Match {
        id: row.get::<_, i64>("id")? as u64,
        file_path: row.get("file_path")?,
        file_hash: row.get("file_hash")?,
        file_size: row.get::<_, Option<i64>>("file_size")?.map(|v| v as u64),
        map_name: row.get("map_name")?,
        server_name: row.get("server_name")?,
        client_name: row.get("client_name")?,
        demo_type: demo_type_str.as_deref().map(DemoType::from_str),
        match_date: row.get("match_date")?,
        duration_ticks: row
            .get::<_, Option<i64>>("duration_ticks")?
            .map(|v| v as u32),
        parsed_at: row.get("parsed_at")?,
        parse_version: row.get::<_, i64>("parse_version")? as u32,
    })
}

// ---------------------------------------------------------------------------
// players table
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, serde::Deserialize)]
pub struct PlayerRow {
    pub name: String,
    pub steam_id: Option<String>,
    pub team: Option<String>,
    pub user_id: Option<i64>,
}

pub fn insert_players(pool: &DbPool, match_id: u64, players: &[PlayerRow]) -> AppResult<()> {
    if players.is_empty() {
        return Ok(());
    }
    let conn = pool.get().map_err(map_pool_err)?;
    let mut stmt = conn
        .prepare(
            "INSERT INTO players (match_id, steam_id, name, team, user_id)
             VALUES (?1, ?2, ?3, ?4, ?5)",
        )
        .map_err(map_sqlite_err)?;
    for p in players {
        stmt.execute(rusqlite::params![
            match_id as i64,
            p.steam_id,
            p.name,
            p.team.as_deref().unwrap_or("Spectator"),
            p.user_id,
        ])
        .map_err(map_sqlite_err)?;
    }
    Ok(())
}

pub fn list_players(pool: &DbPool, match_id: u64) -> AppResult<Vec<Player>> {
    let conn = pool.get().map_err(map_pool_err)?;
    let mut stmt = conn
        .prepare("SELECT * FROM players WHERE match_id = ?1")
        .map_err(map_sqlite_err)?;
    let rows = stmt
        .query_map([match_id as i64], |row| {
            let team: String = row.get("team")?;
            Ok(Player {
                match_id: row.get::<_, i64>("match_id")? as u64,
                steam_id: row.get("steam_id")?,
                name: row.get("name")?,
                team: Team::from_str(&team),
                initial_side: row
                    .get::<_, Option<String>>("initial_side")?
                    .as_deref()
                    .map(Team::from_str),
                user_id: row.get("user_id")?,
            })
        })
        .map_err(map_sqlite_err)?;
    let mut out = Vec::new();
    for r in rows {
        out.push(r.map_err(map_sqlite_err)?);
    }
    Ok(out)
}

// ---------------------------------------------------------------------------
// Hashing helper
// ---------------------------------------------------------------------------

/// SHA-256 of a file as lowercase hex.
pub fn hash_file(path: &Path) -> AppResult<String> {
    use sha2::{Digest, Sha256};
    use std::fs::File;
    use std::io::Read;

    let mut f = File::open(path).map_err(|e| AppError::io("open file", e))?;
    let mut hasher = Sha256::new();
    let mut buf = vec![0u8; 64 * 1024];
    loop {
        let n = f.read(&mut buf).map_err(|e| AppError::io("read file", e))?;
        if n == 0 {
            break;
        }
        hasher.update(&buf[..n]);
    }
    Ok(hex::encode(hasher.finalize()))
}

// ---------------------------------------------------------------------------
// rounds table
// ---------------------------------------------------------------------------

pub fn list_rounds(pool: &DbPool, match_id: u64) -> AppResult<Vec<crate::core::models::Round>> {
    let conn = pool.get().map_err(map_pool_err)?;
    let mut stmt = conn
        .prepare(
            "SELECT id, match_id, round_num, start_tick, freeze_end_tick, end_tick,
             winner, reason, bomb_plant, bomb_site, ct_score, t_score
             FROM rounds WHERE match_id = ?1 ORDER BY round_num ASC",
        )
        .map_err(map_sqlite_err)?;
    let rows = stmt
        .query_map([match_id as i64], |row| {
            let winner_str: Option<String> = row.get(6)?;
            Ok(crate::core::models::Round {
                id: row.get::<_, i64>(0)? as u64,
                match_id: row.get::<_, i64>(1)? as u64,
                round_num: row.get::<_, i64>(2)? as u32,
                start_tick: row.get::<_, Option<i64>>(3)?.map(|v| v as u32),
                freeze_end_tick: row.get::<_, Option<i64>>(4)?.map(|v| v as u32),
                end_tick: row.get::<_, Option<i64>>(5)?.map(|v| v as u32),
                winner: winner_str.as_deref().map(crate::core::models::Team::from_str),
                reason: row.get(7)?,
                bomb_plant: row.get::<_, i64>(8)? != 0,
                bomb_site: row.get(9)?,
                ct_score: row.get::<_, Option<i64>>(10)?.map(|v| v as u32),
                t_score: row.get::<_, Option<i64>>(11)?.map(|v| v as u32),
            })
        })
        .map_err(map_sqlite_err)?;
    let mut out = Vec::new();
    for r in rows {
        out.push(r.map_err(map_sqlite_err)?);
    }
    Ok(out)
}

// ---------------------------------------------------------------------------
// kills for replay/heatmap
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, serde::Serialize)]
#[serde(rename_all = "camelCase")]
pub struct KillEvent {
    pub tick: Option<u32>,
    pub attacker: String,
    pub victim: String,
    pub weapon: String,
    pub headshot: bool,
    pub wallbang: bool,
    pub thru_smoke: bool,
    pub attacker_x: Option<f32>,
    pub attacker_y: Option<f32>,
    pub victim_x: Option<f32>,
    pub victim_y: Option<f32>,
    pub distance: Option<f32>,
}

/// All kills for a given round (for replay overlay).
pub fn list_kills_for_round(pool: &DbPool, round_id: u64) -> AppResult<Vec<KillEvent>> {
    let conn = pool.get().map_err(map_pool_err)?;
    let mut stmt = conn
        .prepare(
            "SELECT tick, attacker, victim, weapon, headshot, wallbang, thru_smoke,
             attacker_x, attacker_y, victim_x, victim_y, distance
             FROM kills WHERE round_id = ?1 ORDER BY tick ASC",
        )
        .map_err(map_sqlite_err)?;
    let rows = stmt
        .query_map([round_id as i64], |row| {
            Ok(KillEvent {
                tick: row.get::<_, Option<i64>>(0)?.map(|v| v as u32),
                attacker: row.get(1)?,
                victim: row.get(2)?,
                weapon: row.get(3)?,
                headshot: row.get::<_, i64>(4)? != 0,
                wallbang: row.get::<_, i64>(5)? != 0,
                thru_smoke: row.get::<_, i64>(6)? != 0,
                attacker_x: row.get(7)?,
                attacker_y: row.get(8)?,
                victim_x: row.get(9)?,
                victim_y: row.get(10)?,
                distance: row.get(11)?,
            })
        })
        .map_err(map_sqlite_err)?;
    let mut out = Vec::new();
    for r in rows {
        out.push(r.map_err(map_sqlite_err)?);
    }
    Ok(out)
}

/// All kills for a given match (for heatmap data).
pub fn list_kill_positions(pool: &DbPool, match_id: u64, player: Option<&str>) -> AppResult<Vec<(Option<f32>, Option<f32>, Option<f32>, Option<f32>)>> {
    let conn = pool.get().map_err(map_pool_err)?;
    let rows: Vec<(Option<f32>, Option<f32>, Option<f32>, Option<f32>)> = if let Some(p) = player {
        let mut stmt = conn
            .prepare("SELECT attacker_x, attacker_y, victim_x, victim_y FROM kills WHERE match_id = ?1 AND attacker = ?2")
            .map_err(map_sqlite_err)?;
        let collected: Vec<_> = stmt.query_map(rusqlite::params![match_id as i64, p], |row| {
            Ok((row.get(0)?, row.get(1)?, row.get(2)?, row.get(3)?))
        })
        .map_err(map_sqlite_err)?
        .filter_map(|r| r.ok())
        .collect();
        collected
    } else {
        let mut stmt = conn
            .prepare("SELECT attacker_x, attacker_y, victim_x, victim_y FROM kills WHERE match_id = ?1")
            .map_err(map_sqlite_err)?;
        let collected: Vec<_> = stmt.query_map([match_id as i64], |row| {
            Ok((row.get(0)?, row.get(1)?, row.get(2)?, row.get(3)?))
        })
        .map_err(map_sqlite_err)?
        .filter_map(|r| r.ok())
        .collect();
        collected
    };
    Ok(rows)
}

// ---------------------------------------------------------------------------
// grenades for replay/utility
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, serde::Serialize)]
#[serde(rename_all = "camelCase")]
pub struct GrenadeEvent {
    pub throw_tick: Option<u32>,
    pub thrower: String,
    pub nade_type: String,
    pub throw_x: Option<f32>,
    pub throw_y: Option<f32>,
    pub land_x: Option<f32>,
    pub land_y: Option<f32>,
}

pub fn list_grenades_for_round(pool: &DbPool, round_id: u64) -> AppResult<Vec<GrenadeEvent>> {
    let conn = pool.get().map_err(map_pool_err)?;
    let mut stmt = conn
        .prepare(
            "SELECT throw_tick, thrower, nade_type, throw_x, throw_y, land_x, land_y
             FROM grenades WHERE round_id = ?1 ORDER BY throw_tick ASC",
        )
        .map_err(map_sqlite_err)?;
    let rows = stmt
        .query_map([round_id as i64], |row| {
            Ok(GrenadeEvent {
                throw_tick: row.get::<_, Option<i64>>(0)?.map(|v| v as u32),
                thrower: row.get(1)?,
                nade_type: row.get::<_, Option<String>>(2)?.unwrap_or_default(),
                throw_x: row.get(3)?,
                throw_y: row.get(4)?,
                land_x: row.get(5)?,
                land_y: row.get(6)?,
            })
        })
        .map_err(map_sqlite_err)?;
    let mut out = Vec::new();
    for r in rows {
        out.push(r.map_err(map_sqlite_err)?);
    }
    Ok(out)
}

pub fn get_utility_throws(pool: &DbPool, match_id: u64) -> AppResult<Vec<UtilityStats>> {
    let conn = pool.get().map_err(map_pool_err)?;
    let mut stmt = conn
        .prepare(
            "SELECT thrower, nade_type, COUNT(*) as count 
             FROM grenades 
             WHERE match_id = ?1 AND thrower IS NOT NULL 
             GROUP BY thrower, nade_type",
        )
        .map_err(map_sqlite_err)?;

    let rows = stmt
        .query_map([match_id as i64], |row| {
            Ok((
                row.get::<_, String>(0)?,
                row.get::<_, String>(1)?,
                row.get::<_, u32>(2)?,
            ))
        })
        .map_err(map_sqlite_err)?;

    let mut stats_map: std::collections::HashMap<String, UtilityStats> = std::collections::HashMap::new();

    for r in rows {
        let (thrower, nade_type, count) = r.map_err(map_sqlite_err)?;
        let stats = stats_map.entry(thrower.clone()).or_insert(UtilityStats {
            player: thrower,
            he: 0,
            flash: 0,
            smoke: 0,
            molly: 0,
            decoy: 0,
        });

        match nade_type.as_str() {
            "hegrenade" => stats.he += count,
            "flashbang" => stats.flash += count,
            "smokegrenade" => stats.smoke += count,
            "molotov" | "incgrenade" => stats.molly += count,
            "decoy" => stats.decoy += count,
            _ => {}
        }
    }

    Ok(stats_map.into_values().collect())
}

// ---------------------------------------------------------------------------
// player_match_stats helpers for anticheat/coach
// ---------------------------------------------------------------------------

pub fn list_match_stats(pool: &DbPool, match_id: u64) -> AppResult<Vec<crate::core::models::PlayerMatchStats>> {
    let conn = pool.get().map_err(map_pool_err)?;
    let mut stmt = conn
        .prepare(
            "SELECT match_id, player, team, kills, deaths, assists, damage,
             adr, kast, rating, hs_pct, head_shots,
             multi_kills_2k, multi_kills_3k, multi_kills_4k, multi_kills_5k,
             clutches_won, clutches_total, entry_kills, entry_deaths,
             utility_damage, utility_enemies_flashed, flash_assists, first_bloods, mvp_count
             FROM player_match_stats WHERE match_id = ?1 ORDER BY rating DESC",
        )
        .map_err(map_sqlite_err)?;
    let rows = stmt
        .query_map([match_id as i64], |row| {
            let team_str: Option<String> = row.get(2)?;
            Ok(crate::core::models::PlayerMatchStats {
                match_id: row.get::<_, i64>(0)? as u64,
                player: row.get(1)?,
                team: team_str.as_deref().map(crate::core::models::Team::from_str),
                kills: row.get::<_, i64>(3)? as u32,
                deaths: row.get::<_, i64>(4)? as u32,
                assists: row.get::<_, i64>(5)? as u32,
                damage: row.get::<_, i64>(6)? as u32,
                adr: row.get::<_, f64>(7)? as f32,
                kast: row.get::<_, f64>(8)? as f32,
                rating: row.get::<_, f64>(9)? as f32,
                hs_pct: row.get::<_, f64>(10)? as f32,
                head_shots: row.get::<_, i64>(11)? as u32,
                multi_kills_2k: row.get::<_, i64>(12)? as u32,
                multi_kills_3k: row.get::<_, i64>(13)? as u32,
                multi_kills_4k: row.get::<_, i64>(14)? as u32,
                multi_kills_5k: row.get::<_, i64>(15)? as u32,
                clutches_won: row.get::<_, i64>(16)? as u32,
                clutches_total: row.get::<_, i64>(17)? as u32,
                entry_kills: row.get::<_, i64>(18)? as u32,
                entry_deaths: row.get::<_, i64>(19)? as u32,
                utility_damage: row.get::<_, i64>(20)? as u32,
                utility_enemies_flashed: row.get::<_, i64>(21)? as u32,
                flash_assists: row.get::<_, i64>(22)? as u32,
                first_bloods: row.get::<_, i64>(23)? as u32,
                mvp_count: row.get::<_, i64>(24)? as u32,
            })
        })
        .map_err(map_sqlite_err)?;
    let mut out = Vec::new();
    for r in rows {
        out.push(r.map_err(map_sqlite_err)?);
    }
    Ok(out)
}

// Insert anticheat flags (replacing old ones for this match)
pub fn upsert_anticheat_flags(pool: &DbPool, match_id: u64, flags: &[crate::core::models::AnticheatFlag]) -> AppResult<()> {
    let conn = pool.get().map_err(map_pool_err)?;
    conn.execute("DELETE FROM anticheat_flags WHERE match_id = ?1", [match_id as i64]).map_err(map_sqlite_err)?;
    let mut stmt = conn.prepare(
        "INSERT INTO anticheat_flags (match_id, player, heuristic, severity, evidence_count, details_json)
         VALUES (?1, ?2, ?3, ?4, ?5, ?6)"
    ).map_err(map_sqlite_err)?;
    for f in flags {
        stmt.execute(rusqlite::params![
            f.match_id as i64,
            f.player,
            f.heuristic.as_str(),
            f.severity as f64,
            f.evidence_count.map(|v| v as i64),
            f.details_json,
        ]).map_err(map_sqlite_err)?;
    }
    Ok(())
}

pub fn list_anticheat_flags(pool: &DbPool, match_id: u64) -> AppResult<Vec<crate::core::models::AnticheatFlag>> {
    let conn = pool.get().map_err(map_pool_err)?;
    let mut stmt = conn.prepare(
        "SELECT id, match_id, player, heuristic, severity, evidence_count, details_json
         FROM anticheat_flags WHERE match_id = ?1 ORDER BY severity DESC"
    ).map_err(map_sqlite_err)?;
    let rows = stmt.query_map([match_id as i64], |row| {
        let heuristic_str: String = row.get(3)?;
        let h = match heuristic_str.as_str() {
            "snap_aim" => crate::core::models::AnticheatHeuristic::SnapAim,
            "pre_aim_through_wall" => crate::core::models::AnticheatHeuristic::PreAimThroughWall,
            "reaction_time_anomaly" => crate::core::models::AnticheatHeuristic::ReactionTimeAnomaly,
            "headshot_ratio_anomaly" => crate::core::models::AnticheatHeuristic::HeadshotRatioAnomaly,
            "crosshair_placement" => crate::core::models::AnticheatHeuristic::CrosshairPlacement,
            "smoke_molly_anomaly" => crate::core::models::AnticheatHeuristic::SmokeMollyAnomaly,
            "bhop_consistency" => crate::core::models::AnticheatHeuristic::BhopConsistency,
            _ => crate::core::models::AnticheatHeuristic::InconsistencyScore,
        };
        Ok(crate::core::models::AnticheatFlag {
            id: row.get::<_, i64>(0)? as u64,
            match_id: row.get::<_, i64>(1)? as u64,
            player: row.get(2)?,
            heuristic: h,
            severity: row.get::<_, f64>(4)? as f32,
            evidence_count: row.get::<_, Option<i64>>(5)?.map(|v| v as u32),
            details_json: row.get(6)?,
        })
    }).map_err(map_sqlite_err)?;
    let mut out = Vec::new();
    for r in rows {
        out.push(r.map_err(map_sqlite_err)?);
    }
    Ok(out)
}

#[derive(serde::Deserialize, serde::Serialize, Debug)]
pub struct CoachTipInsert {
    pub player: Option<String>,
    pub category: String,
    pub priority: i32,
    pub title: String,
    pub body: String,
    pub metric_name: Option<String>,
    pub current_value: Option<f32>,
    pub target_value: Option<f32>,
}

// Insert coach tips (replacing old ones for this match)
pub fn upsert_coach_tips(pool: &DbPool, match_id: u64, tips: &[CoachTipInsert]) -> AppResult<()> {
    let conn = pool.get().map_err(map_pool_err)?;
    conn.execute("DELETE FROM coach_tips WHERE match_id = ?1", [match_id as i64]).map_err(map_sqlite_err)?;
    let mut stmt = conn.prepare(
        "INSERT INTO coach_tips (match_id, player, category, priority, title, body, metric_name, current_value, target_value)
         VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9)"
    ).map_err(map_sqlite_err)?;
    for t in tips {
        stmt.execute(rusqlite::params![
            match_id as i64,
            t.player,
            t.category,
            t.priority,
            t.title,
            t.body,
            t.metric_name,
            t.current_value.map(|v| v as f64),
            t.target_value.map(|v| v as f64),
        ]).map_err(map_sqlite_err)?;
    }
    Ok(())
}

pub fn list_coach_tips(pool: &DbPool, match_id: u64, player: Option<&str>) -> AppResult<Vec<crate::core::models::CoachTip>> {
    let conn = pool.get().map_err(map_pool_err)?;
    let rows: Vec<crate::core::models::CoachTip> = if let Some(p) = player {
        let mut stmt = conn.prepare(
            "SELECT id, match_id, player, category, priority, title, body, metric_name, current_value, target_value, evidence_json
             FROM coach_tips WHERE match_id = ?1 AND (player = ?2 OR player IS NULL) ORDER BY priority DESC"
        ).map_err(map_sqlite_err)?;
        let collected: Vec<_> = stmt.query_map(rusqlite::params![match_id as i64, p], row_to_coach_tip)
            .map_err(map_sqlite_err)?
            .filter_map(|r| r.ok())
            .collect();
        collected
    } else {
        let mut stmt = conn.prepare(
            "SELECT id, match_id, player, category, priority, title, body, metric_name, current_value, target_value, evidence_json
             FROM coach_tips WHERE match_id = ?1 ORDER BY priority DESC"
        ).map_err(map_sqlite_err)?;
        let collected: Vec<_> = stmt.query_map([match_id as i64], row_to_coach_tip)
            .map_err(map_sqlite_err)?
            .filter_map(|r| r.ok())
            .collect();
        collected
    };
    Ok(rows)
}

fn row_to_coach_tip(row: &rusqlite::Row) -> rusqlite::Result<crate::core::models::CoachTip> {
    let cat_str: String = row.get(3)?;
    let cat = match cat_str.as_str() {
        "positioning" => crate::core::models::CoachCategory::Positioning,
        "utility" => crate::core::models::CoachCategory::Utility,
        "economy" => crate::core::models::CoachCategory::Economy,
        "aim" => crate::core::models::CoachCategory::Aim,
        "trade" => crate::core::models::CoachCategory::Trade,
        "movement" => crate::core::models::CoachCategory::Movement,
        _ => crate::core::models::CoachCategory::Timing,
    };
    Ok(crate::core::models::CoachTip {
        id: row.get::<_, i64>(0)? as u64,
        match_id: row.get::<_, i64>(1)? as u64,
        player: row.get(2)?,
        category: cat,
        priority: row.get(4)?,
        title: row.get(5)?,
        body: row.get(6)?,
        metric_name: row.get(7)?,
        current_value: row.get::<_, Option<f64>>(8)?.map(|v| v as f32),
        target_value: row.get::<_, Option<f64>>(9)?.map(|v| v as f32),
        evidence_json: row.get(10)?,
    })
}

// ---------------------------------------------------------------------------
// Error mapping
// ---------------------------------------------------------------------------

fn map_pool_err(e: r2d2::Error) -> AppError {
    AppError::Other(format!("db pool: {e}"))
}

fn map_sqlite_err(e: rusqlite::Error) -> AppError {
    AppError::Other(format!("sqlite: {e}"))
}
