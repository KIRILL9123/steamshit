//! Row-mapping helpers for the import pipeline. Split out from
//! `core/import.rs` so the orchestrator reads top-to-bottom without
//! drowning in 200 lines of per-table boilerplate.
//!
//! Each `bulk_insert_*` function takes the `serde_json::Value` rows
//! returned by the Python sidecar, projects them to the SQL columns, and
//! inserts them inside the supplied transaction.

use std::collections::HashMap;

use rusqlite::Transaction;

use crate::core::repo::{InsertMatch, PlayerRow};
use crate::error::{AppError, AppResult};

// ---------------------------------------------------------------------------
// matches + players
// ---------------------------------------------------------------------------

pub fn insert_match_in_tx(tx: &Transaction, m: InsertMatch) -> AppResult<u64> {
    let parsed_at = chrono::Utc::now().to_rfc3339();
    tx.execute(
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
    .map_err(map_sqlite)?;
    Ok(tx.last_insert_rowid() as u64)
}

pub fn insert_players_in_tx(
    tx: &Transaction,
    match_id: u64,
    players: &[PlayerRow],
) -> AppResult<()> {
    if players.is_empty() {
        return Ok(());
    }
    let mut stmt = tx
        .prepare(
            "INSERT INTO players (match_id, steam_id, name, team, user_id)
             VALUES (?1, ?2, ?3, ?4, ?5)",
        )
        .map_err(map_sqlite)?;
    for p in players {
        stmt.execute(rusqlite::params![
            match_id as i64,
            p.steam_id,
            p.name,
            p.team.as_deref().unwrap_or("Spectator"),
            p.user_id,
        ])
        .map_err(map_sqlite)?;
    }
    Ok(())
}

pub fn build_round_id_map(tx: &Transaction, match_id: u64) -> AppResult<HashMap<i64, i64>> {
    let mut stmt = tx
        .prepare("SELECT id, round_num FROM rounds WHERE match_id = ?1")
        .map_err(map_sqlite)?;
    let rows = stmt
        .query_map([match_id as i64], |r| {
            Ok((r.get::<_, i64>(0)?, r.get::<_, i64>(1)?))
        })
        .map_err(map_sqlite)?;
    let mut out = HashMap::new();
    for r in rows {
        let (id, num) = r.map_err(map_sqlite)?;
        out.insert(num, id);
    }
    Ok(out)
}

// ---------------------------------------------------------------------------
// JSON helpers
// ---------------------------------------------------------------------------

fn json_i64(v: Option<&serde_json::Value>) -> Option<i64> {
    v.and_then(|v| {
        v.as_i64()
            .or_else(|| v.as_f64().map(|f| f as i64))
            .or_else(|| v.as_str().and_then(|s| s.parse().ok()))
    })
}

fn json_f64(v: Option<&serde_json::Value>) -> Option<f64> {
    v.and_then(|v| {
        v.as_f64()
            .or_else(|| v.as_i64().map(|i| i as f64))
            .or_else(|| v.as_str().and_then(|s| s.parse().ok()))
    })
}

fn json_bool(v: Option<&serde_json::Value>) -> bool {
    match v {
        Some(serde_json::Value::Bool(b)) => *b,
        Some(serde_json::Value::Number(n)) => n.as_i64().map(|i| i != 0).unwrap_or(false),
        Some(serde_json::Value::String(s)) => s == "true" || s == "1",
        _ => false,
    }
}

fn get<'a>(v: &'a serde_json::Value, key: &str) -> Option<&'a serde_json::Value> {
    v.as_object().and_then(|o| o.get(key))
}

fn map_sqlite(e: rusqlite::Error) -> AppError {
    AppError::Other(format!("sqlite: {e}"))
}

// ---------------------------------------------------------------------------
// Per-table bulk inserts
// ---------------------------------------------------------------------------

pub fn bulk_insert_rounds(
    tx: &Transaction,
    rows: &[serde_json::Value],
    match_id: u64,
) -> AppResult<usize> {
    let cols = [
        "match_id",
        "round_num",
        "start_tick",
        "freeze_end_tick",
        "end_tick",
        "winner",
        "reason",
        "bomb_plant",
        "bomb_site",
        "ct_score",
        "t_score",
    ];
    let placeholders = std::iter::repeat("?")
        .take(cols.len())
        .collect::<Vec<_>>()
        .join(",");
    let sql = format!(
        "INSERT INTO rounds ({}) VALUES ({})",
        cols.join(","),
        placeholders
    );
    let mut stmt = tx.prepare(&sql).map_err(map_sqlite)?;
    let mut n = 0;
    for v in rows {
        stmt.execute(rusqlite::params![
            match_id as i64,
            json_i64(get(v, "round_num")).unwrap_or(0),
            json_i64(get(v, "start_tick")).unwrap_or(0),
            json_i64(get(v, "freeze_end_tick")).unwrap_or(0),
            json_i64(get(v, "end_tick")).unwrap_or(0),
            get(v, "winner").and_then(|x| x.as_str()).map(String::from),
            get(v, "reason").and_then(|x| x.as_str()).map(String::from),
            json_bool(get(v, "bomb_plant")) as i64,
            get(v, "bomb_site")
                .and_then(|x| x.as_str())
                .map(String::from),
            json_i64(get(v, "ct_score")).unwrap_or(0),
            json_i64(get(v, "t_score")).unwrap_or(0),
        ])
        .map_err(map_sqlite)?;
        n += 1;
    }
    Ok(n)
}

pub fn bulk_insert_kills(
    tx: &Transaction,
    rows: &[serde_json::Value],
    match_id: u64,
    round_ids: &HashMap<i64, i64>,
) -> AppResult<usize> {
    let cols = [
        "match_id",
        "round_id",
        "tick",
        "attacker",
        "victim",
        "assister",
        "weapon",
        "headshot",
        "wallbang",
        "noscope",
        "thru_smoke",
        "thru_wall",
        "blind_kill",
        "attacker_x",
        "attacker_y",
        "attacker_z",
        "victim_x",
        "victim_y",
        "victim_z",
        "distance",
    ];
    let placeholders = std::iter::repeat("?")
        .take(cols.len())
        .collect::<Vec<_>>()
        .join(",");
    let sql = format!(
        "INSERT INTO kills ({}) VALUES ({})",
        cols.join(","),
        placeholders
    );
    let mut stmt = tx.prepare(&sql).map_err(map_sqlite)?;
    let mut n = 0;
    for v in rows {
        let round_num = json_i64(get(v, "round_num")).unwrap_or(0);
        let round_id = match round_ids.get(&round_num).copied() {
            Some(id) => id,
            None => continue,
        };
        stmt.execute(rusqlite::params![
            match_id as i64,
            round_id,
            json_i64(get(v, "tick")).unwrap_or(0),
            get(v, "attacker_name")
                .and_then(|x| x.as_str())
                .unwrap_or("")
                .to_string(),
            get(v, "victim_name")
                .and_then(|x| x.as_str())
                .unwrap_or("")
                .to_string(),
            get(v, "assister_name")
                .and_then(|x| x.as_str())
                .map(String::from),
            get(v, "weapon")
                .and_then(|x| x.as_str())
                .unwrap_or("")
                .to_string(),
            json_bool(get(v, "headshot")) as i64,
            json_bool(get(v, "wallbang")) as i64,
            json_bool(get(v, "noscope")) as i64,
            json_bool(get(v, "thru_smoke")) as i64,
            json_bool(get(v, "thru_wall")) as i64,
            json_bool(get(v, "blind_kill")) as i64,
            json_f64(get(v, "attacker_x")).unwrap_or(0.0),
            json_f64(get(v, "attacker_y")).unwrap_or(0.0),
            json_f64(get(v, "attacker_z")).unwrap_or(0.0),
            json_f64(get(v, "victim_x")).unwrap_or(0.0),
            json_f64(get(v, "victim_y")).unwrap_or(0.0),
            json_f64(get(v, "victim_z")).unwrap_or(0.0),
            json_f64(get(v, "distance")).unwrap_or(0.0),
        ])
        .map_err(map_sqlite)?;
        n += 1;
    }
    Ok(n)
}

pub fn bulk_insert_damages(
    tx: &Transaction,
    rows: &[serde_json::Value],
    match_id: u64,
    round_ids: &HashMap<i64, i64>,
) -> AppResult<usize> {
    let cols = [
        "match_id",
        "round_id",
        "tick",
        "attacker",
        "victim",
        "weapon",
        "hp_damage",
        "armor_damage",
        "hitgroup",
    ];
    let placeholders = std::iter::repeat("?")
        .take(cols.len())
        .collect::<Vec<_>>()
        .join(",");
    let sql = format!(
        "INSERT INTO damages ({}) VALUES ({})",
        cols.join(","),
        placeholders
    );
    let mut stmt = tx.prepare(&sql).map_err(map_sqlite)?;
    let mut n = 0;
    for v in rows {
        let round_num = json_i64(get(v, "round_num")).unwrap_or(0);
        let round_id = match round_ids.get(&round_num).copied() {
            Some(id) => id,
            None => continue,
        };
        stmt.execute(rusqlite::params![
            match_id as i64,
            round_id,
            json_i64(get(v, "tick")).unwrap_or(0),
            get(v, "attacker_name")
                .and_then(|x| x.as_str())
                .unwrap_or("")
                .to_string(),
            get(v, "victim_name")
                .and_then(|x| x.as_str())
                .unwrap_or("")
                .to_string(),
            get(v, "weapon").and_then(|x| x.as_str()).map(String::from),
            json_i64(get(v, "hp_damage")).unwrap_or(0),
            json_i64(get(v, "armor_damage")).unwrap_or(0),
            get(v, "hitgroup")
                .and_then(|x| x.as_str())
                .map(String::from),
        ])
        .map_err(map_sqlite)?;
        n += 1;
    }
    Ok(n)
}

pub fn bulk_insert_grenades(
    tx: &Transaction,
    rows: &[serde_json::Value],
    match_id: u64,
    round_ids: &HashMap<i64, i64>,
) -> AppResult<usize> {
    let cols = [
        "match_id",
        "round_id",
        "throw_tick",
        "thrower",
        "nade_type",
        "throw_x",
        "throw_y",
        "throw_z",
        "land_x",
        "land_y",
        "land_z",
        "land_tick",
        "duration_ticks",
    ];
    let placeholders = std::iter::repeat("?")
        .take(cols.len())
        .collect::<Vec<_>>()
        .join(",");
    let sql = format!(
        "INSERT INTO grenades ({}) VALUES ({})",
        cols.join(","),
        placeholders
    );
    let mut stmt = tx.prepare(&sql).map_err(map_sqlite)?;
    let mut n = 0;
    for v in rows {
        let round_num = json_i64(get(v, "round_num")).unwrap_or(0);
        let round_id = match round_ids.get(&round_num).copied() {
            Some(id) => id,
            None => continue,
        };
        stmt.execute(rusqlite::params![
            match_id as i64,
            round_id,
            json_i64(get(v, "throw_tick")).unwrap_or(0),
            get(v, "thrower_name")
                .and_then(|x| x.as_str())
                .unwrap_or("")
                .to_string(),
            get(v, "nade_type")
                .and_then(|x| x.as_str())
                .unwrap_or("smoke")
                .to_string(),
            json_f64(get(v, "throw_x")).unwrap_or(0.0),
            json_f64(get(v, "throw_y")).unwrap_or(0.0),
            json_f64(get(v, "throw_z")).unwrap_or(0.0),
            json_f64(get(v, "land_x")).unwrap_or(0.0),
            json_f64(get(v, "land_y")).unwrap_or(0.0),
            json_f64(get(v, "land_z")).unwrap_or(0.0),
            json_i64(get(v, "land_tick")).unwrap_or(0),
            json_i64(get(v, "duration_ticks")).unwrap_or(0),
        ])
        .map_err(map_sqlite)?;
        n += 1;
    }
    Ok(n)
}

pub fn bulk_insert_smokes(
    tx: &Transaction,
    rows: &[serde_json::Value],
    match_id: u64,
    round_ids: &HashMap<i64, i64>,
) -> AppResult<usize> {
    // The schema has a dedicated `utility_blinds` table for flash events;
    // smokes are stored under `grenades` with nade_type='smoke'. We
    // route the sidecar's `smokes` array into a slim `grenades` row.
    let cols = [
        "match_id",
        "round_id",
        "throw_tick",
        "thrower",
        "nade_type",
        "throw_x",
        "throw_y",
        "throw_z",
        "land_x",
        "land_y",
        "land_z",
        "land_tick",
        "duration_ticks",
    ];
    let placeholders = std::iter::repeat("?")
        .take(cols.len())
        .collect::<Vec<_>>()
        .join(",");
    let sql = format!(
        "INSERT INTO grenades ({}) VALUES ({})",
        cols.join(","),
        placeholders
    );
    let mut stmt = tx.prepare(&sql).map_err(map_sqlite)?;
    let mut n = 0;
    for v in rows {
        let round_num = json_i64(get(v, "round_num")).unwrap_or(0);
        let round_id = match round_ids.get(&round_num).copied() {
            Some(id) => id,
            None => continue,
        };
        stmt.execute(rusqlite::params![
            match_id as i64,
            round_id,
            json_i64(get(v, "throw_tick")).unwrap_or(0),
            get(v, "thrower_name")
                .and_then(|x| x.as_str())
                .unwrap_or("")
                .to_string(),
            "smoke",
            json_f64(get(v, "throw_x")).unwrap_or(0.0),
            json_f64(get(v, "throw_y")).unwrap_or(0.0),
            json_f64(get(v, "throw_z")).unwrap_or(0.0),
            json_f64(get(v, "land_x")).unwrap_or(0.0),
            json_f64(get(v, "land_y")).unwrap_or(0.0),
            json_f64(get(v, "land_z")).unwrap_or(0.0),
            json_i64(get(v, "land_tick")).unwrap_or(0),
            json_i64(get(v, "duration_ticks")).unwrap_or(0),
        ])
        .map_err(map_sqlite)?;
        n += 1;
    }
    Ok(n)
}

pub fn bulk_insert_infernos(
    tx: &Transaction,
    rows: &[serde_json::Value],
    match_id: u64,
    round_ids: &HashMap<i64, i64>,
) -> AppResult<usize> {
    // Same routing as smokes — store under `grenades` with nade_type='molotov'.
    let cols = [
        "match_id",
        "round_id",
        "throw_tick",
        "thrower",
        "nade_type",
        "throw_x",
        "throw_y",
        "throw_z",
        "land_x",
        "land_y",
        "land_z",
        "land_tick",
        "duration_ticks",
    ];
    let placeholders = std::iter::repeat("?")
        .take(cols.len())
        .collect::<Vec<_>>()
        .join(",");
    let sql = format!(
        "INSERT INTO grenades ({}) VALUES ({})",
        cols.join(","),
        placeholders
    );
    let mut stmt = tx.prepare(&sql).map_err(map_sqlite)?;
    let mut n = 0;
    for v in rows {
        let round_num = json_i64(get(v, "round_num")).unwrap_or(0);
        let round_id = match round_ids.get(&round_num).copied() {
            Some(id) => id,
            None => continue,
        };
        stmt.execute(rusqlite::params![
            match_id as i64,
            round_id,
            json_i64(get(v, "throw_tick")).unwrap_or(0),
            get(v, "thrower_name")
                .and_then(|x| x.as_str())
                .unwrap_or("")
                .to_string(),
            "molotov",
            json_f64(get(v, "throw_x")).unwrap_or(0.0),
            json_f64(get(v, "throw_y")).unwrap_or(0.0),
            json_f64(get(v, "throw_z")).unwrap_or(0.0),
            json_f64(get(v, "land_x")).unwrap_or(0.0),
            json_f64(get(v, "land_y")).unwrap_or(0.0),
            json_f64(get(v, "land_z")).unwrap_or(0.0),
            json_i64(get(v, "land_tick")).unwrap_or(0),
            json_i64(get(v, "duration_ticks")).unwrap_or(0),
        ])
        .map_err(map_sqlite)?;
        n += 1;
    }
    Ok(n)
}

pub fn bulk_insert_shots(
    tx: &Transaction,
    rows: &[serde_json::Value],
    match_id: u64,
    round_ids: &HashMap<i64, i64>,
) -> AppResult<usize> {
    let cols = ["match_id", "round_id", "tick", "attacker", "weapon"];
    let placeholders = std::iter::repeat("?")
        .take(cols.len())
        .collect::<Vec<_>>()
        .join(",");
    let sql = format!(
        "INSERT INTO weapon_fires ({}) VALUES ({})",
        cols.join(","),
        placeholders
    );
    let mut stmt = tx.prepare(&sql).map_err(map_sqlite)?;
    let mut n = 0;
    for v in rows {
        let round_num = json_i64(get(v, "round_num")).unwrap_or(0);
        let round_id = match round_ids.get(&round_num).copied() {
            Some(id) => id,
            None => continue,
        };
        stmt.execute(rusqlite::params![
            match_id as i64,
            round_id,
            json_i64(get(v, "tick")).unwrap_or(0),
            get(v, "player_name")
                .and_then(|x| x.as_str())
                .unwrap_or("")
                .to_string(),
            get(v, "weapon").and_then(|x| x.as_str()).map(String::from),
        ])
        .map_err(map_sqlite)?;
        n += 1;
    }
    Ok(n)
}

pub fn bulk_insert_bomb(
    tx: &Transaction,
    rows: &[serde_json::Value],
    match_id: u64,
    round_ids: &HashMap<i64, i64>,
) -> AppResult<usize> {
    let cols = [
        "match_id", "round_id", "tick", "event", "player", "site", "x", "y", "z",
    ];
    let placeholders = std::iter::repeat("?")
        .take(cols.len())
        .collect::<Vec<_>>()
        .join(",");
    let sql = format!(
        "INSERT INTO bomb_events ({}) VALUES ({})",
        cols.join(","),
        placeholders
    );
    let mut stmt = tx.prepare(&sql).map_err(map_sqlite)?;
    let mut n = 0;
    for v in rows {
        let round_num = json_i64(get(v, "round_num")).unwrap_or(0);
        let round_id = match round_ids.get(&round_num).copied() {
            Some(id) => id,
            None => continue,
        };
        stmt.execute(rusqlite::params![
            match_id as i64,
            round_id,
            json_i64(get(v, "tick")).unwrap_or(0),
            get(v, "event")
                .and_then(|x| x.as_str())
                .unwrap_or("")
                .to_string(),
            get(v, "player_name")
                .and_then(|x| x.as_str())
                .map(String::from),
            get(v, "site").and_then(|x| x.as_str()).map(String::from),
            json_f64(get(v, "x")).unwrap_or(0.0),
            json_f64(get(v, "y")).unwrap_or(0.0),
            json_f64(get(v, "z")).unwrap_or(0.0),
        ])
        .map_err(map_sqlite)?;
        n += 1;
    }
    Ok(n)
}

pub fn bulk_insert_ticks(
    tx: &Transaction,
    rows: &[serde_json::Value],
    match_id: u64,
    round_ids: &HashMap<i64, i64>,
) -> AppResult<usize> {
    let mut stmt = tx
        .prepare(
            "INSERT OR REPLACE INTO ticks (
                match_id, round_id, tick, player, x, y, z, yaw, pitch,
                health, armor, velocity_x, velocity_y, velocity_z,
                is_alive, is_planting, is_defusing
             ) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11, ?12, ?13, ?14, ?15, ?16, ?17)",
        )
        .map_err(map_sqlite)?;
    let mut n = 0;
    for v in rows {
        let round_num = json_i64(get(v, "round_num")).unwrap_or(0);
        let round_id = match round_ids.get(&round_num).copied() {
            Some(id) => id,
            None => continue,
        };
        stmt.execute(rusqlite::params![
            match_id as i64,
            round_id,
            json_i64(get(v, "tick")).unwrap_or(0),
            get(v, "player_name")
                .and_then(|x| x.as_str())
                .unwrap_or("")
                .to_string(),
            json_f64(get(v, "x")).unwrap_or(0.0),
            json_f64(get(v, "y")).unwrap_or(0.0),
            json_f64(get(v, "z")).unwrap_or(0.0),
            json_f64(get(v, "yaw")).unwrap_or(0.0),
            json_f64(get(v, "pitch")).unwrap_or(0.0),
            json_i64(get(v, "health")).unwrap_or(0),
            json_i64(get(v, "armor")).unwrap_or(0),
            json_f64(get(v, "velocity_x")).unwrap_or(0.0),
            json_f64(get(v, "velocity_y")).unwrap_or(0.0),
            json_f64(get(v, "velocity_z")).unwrap_or(0.0),
            json_bool(get(v, "is_alive")) as i64,
            json_bool(get(v, "is_planting")) as i64,
            json_bool(get(v, "is_defusing")) as i64,
        ])
        .map_err(map_sqlite)?;
        n += 1;
    }
    Ok(n)
}
