//! Import orchestrator: hash → sidecar parse → write to DB.
//!
//! The flow:
//!   1. SHA-256 the file (cheap dedupe key).
//!   2. If a match with the same hash exists, return it unchanged.
//!   3. Call the Python sidecar to parse the demo.
//!   4. Inside a single transaction:
//!        * insert `matches` row,
//!        * insert `players` roster,
//!        * bulk-insert rounds, kills, damages, grenades, smokes, infernos,
//!          shots, bomb events, ticks (if requested).
//!   5. Compute and insert per-player aggregate stats
//!      (`player_match_stats`) — KAST/ADR/HS%/Rating 2.0.
//!   6. Return the new `Match`.
//!
//! Progress is reported through Tauri events. See `ImportProgress`.

use std::path::Path;

use serde::Serialize;
use tauri::{AppHandle, Emitter};

use crate::core::db::DbPool;
use crate::core::import_helpers::{
    build_round_id_map, bulk_insert_bomb, bulk_insert_damages, bulk_insert_grenades,
    bulk_insert_infernos, bulk_insert_kills, bulk_insert_rounds, bulk_insert_shots,
    bulk_insert_smokes, bulk_insert_ticks, insert_match_in_tx, insert_players_in_tx,
};
use crate::core::models::{Match, PlayerMatchStats};
use crate::core::parser::DemoParser;
use crate::core::repo::{self, InsertMatch, PlayerRow};
use crate::error::{AppError, AppResult};
use crate::sidecar::SidecarHandle;

pub const PARSE_VERSION: u32 = 1;

/// Progress event payload sent to the frontend.
#[derive(Debug, Clone, Serialize)]
#[serde(tag = "stage", rename_all = "snake_case")]
pub enum ImportProgress {
    Start { path: String },
    Hashing { path: String },
    Parsing { path: String, fraction: f32 },
    Writing { match_id: u64, fraction: f32 },
    Stats { match_id: u64 },
    Done { match_id: u64 },
}

impl ImportProgress {
    pub fn emit(&self, app: &AppHandle) {
        if let Err(e) = app.emit("import:progress", self) {
            tracing::warn!("emit import:progress: {e}");
        }
    }
}

/// Top-level import function. Returns the new (or pre-existing) `Match`.
pub async fn import_demo(
    app: AppHandle,
    pool: DbPool,
    sidecar: SidecarHandle,
    path: &Path,
) -> AppResult<Match> {
    let path_str = path.to_string_lossy().into_owned();
    ImportProgress::Start {
        path: path_str.clone(),
    }
    .emit(&app);
    ImportProgress::Hashing {
        path: path_str.clone(),
    }
    .emit(&app);

    // 1. dedupe by hash
    let hash = repo::hash_file(path)?;
    if let Some(existing) = repo::find_match_by_hash(&pool, &hash)? {
        tracing::info!("demo already imported (match id={})", existing.id);
        ImportProgress::Done {
            match_id: existing.id,
        }
        .emit(&app);
        return Ok(existing);
    }

    // 2. sidecar parse
    ImportProgress::Parsing {
        path: path_str.clone(),
        fraction: 0.1,
    }
    .emit(&app);
    let parsed = parse_via_sidecar(&sidecar, path).await?;
    ImportProgress::Parsing {
        path: path_str.clone(),
        fraction: 0.6,
    }
    .emit(&app);

    // 3. write to DB (single transaction)
    let file_size = std::fs::metadata(path).ok().map(|m| m.len());
    let file_path = path.to_string_lossy().into_owned();
    let players_rows: Vec<PlayerRow> = parsed
        .players
        .iter()
        .map(|p| PlayerRow {
            name: p.name.clone(),
            steam_id: p.steam_id.clone(),
            team: p.team.clone(),
            user_id: p.user_id,
        })
        .collect();

    let match_id = write_to_db(
        pool.clone(),
        InsertMatch {
            file_path: file_path.clone(),
            file_hash: hash.clone(),
            file_size,
            map_name: parsed.header.map_name.clone(),
            server_name: parsed.header.server_name.clone(),
            client_name: parsed.header.client_name.clone(),
            demo_type: parsed.header.demo_type.clone(),
            match_date: parsed.header.match_date.clone(),
            duration_ticks: parsed.header.duration_ticks,
            parse_version: PARSE_VERSION,
        },
        players_rows.clone(),
        parsed.clone(),
    )
    .await?;

    ImportProgress::Writing {
        match_id,
        fraction: 0.85,
    }
    .emit(&app);

    // 4. compute per-player stats
    compute_and_store_stats(&pool, match_id).await?;
    ImportProgress::Stats { match_id }.emit(&app);

    let m = repo::get_match(&pool, match_id)?;
    ImportProgress::Done { match_id }.emit(&app);
    Ok(m)
}

// ---------------------------------------------------------------------------
// Async sidecar parse
// ---------------------------------------------------------------------------

async fn parse_via_sidecar(
    sidecar: &SidecarHandle,
    path: &Path,
) -> AppResult<crate::core::parser::ParsedDemo> {
    let parser = DemoParser::new(sidecar, path);
    parser.parse().await
}

// ---------------------------------------------------------------------------
// DB write (single transaction)
// ---------------------------------------------------------------------------

#[allow(clippy::too_many_arguments)]
async fn write_to_db(
    pool: DbPool,
    m: InsertMatch,
    players_rows: Vec<PlayerRow>,
    parsed: crate::core::parser::ParsedDemo,
) -> AppResult<u64> {
    tokio::task::spawn_blocking(move || {
        let conn = pool
            .get()
            .map_err(|e| AppError::Other(format!("db pool: {e}")))?;
        let tx = conn.unchecked_transaction().map_err(map_sqlite)?;

        let match_id = insert_match_in_tx(&tx, m)?;
        insert_players_in_tx(&tx, match_id, &players_rows)?;

        // Rounds MUST be inserted before `build_round_id_map` so the lookup
        // by `round_num` returns valid ids; kills/damages/grenades/etc. all
        // reference a `round_id` derived from that map and silently skip
        // rows whose `round_num` is missing.
        bulk_insert_rounds(&tx, &parsed.rounds, match_id)?;
        let round_ids = build_round_id_map(&tx, match_id)?;

        bulk_insert_kills(&tx, &parsed.kills, match_id, &round_ids)?;
        bulk_insert_damages(&tx, &parsed.damages, match_id, &round_ids)?;
        bulk_insert_grenades(&tx, &parsed.grenades, match_id, &round_ids)?;
        bulk_insert_smokes(&tx, &parsed.smokes, match_id, &round_ids)?;
        bulk_insert_infernos(&tx, &parsed.infernos, match_id, &round_ids)?;
        bulk_insert_shots(&tx, &parsed.shots, match_id, &round_ids)?;
        bulk_insert_bomb(&tx, &parsed.bomb, match_id, &round_ids)?;
        if !parsed.ticks.is_empty() {
            bulk_insert_ticks(&tx, &parsed.ticks, match_id, &round_ids)?;
        }

        tx.commit().map_err(map_sqlite)?;
        Ok::<u64, AppError>(match_id)
    })
    .await
    .map_err(|e| AppError::Other(format!("join write_to_db: {e}")))?
}

// ---------------------------------------------------------------------------
// Per-player stats aggregation (uses core::analytics)
// ---------------------------------------------------------------------------

async fn compute_and_store_stats(pool: &DbPool, match_id: u64) -> AppResult<()> {
    use crate::core::models::{PlayerMatchStats, Team};
    use crate::core::repo;

    let pool = pool.clone();
    let match_id = match_id;
    tokio::task::spawn_blocking(move || -> AppResult<()> {
        let conn = pool.get().map_err(map_pool_err)?;

        // Rounds (counted by round_num > 0).
        let total_rounds: i64 = {
            let mut stmt = conn
                .prepare("SELECT COUNT(*) FROM rounds WHERE match_id = ?1")
                .map_err(map_sqlite)?;
            stmt.query_row([match_id as i64], |r| r.get::<_, i64>(0))
                .map_err(map_sqlite)?
        };

        // Kills.
        let kills: Vec<KillRow> = {
            let mut stmt = conn
                .prepare(
                    "SELECT tick, attacker, victim, weapon, headshot, round_id, assister, blind_kill
                 FROM kills WHERE match_id = ?1",
                )
                .map_err(map_sqlite)?;
            let rows = stmt
                .query_map([match_id as i64], |r| {
                    Ok(KillRow {
                        tick: r.get::<_, Option<i64>>(0)?.unwrap_or(0),
                        attacker: r.get(1)?,
                        victim: r.get(2)?,
                        weapon: r.get(3)?,
                        headshot: r.get::<_, i64>(4)? != 0,
                        round_id: r.get(5)?,
                        assister: r.get(6)?,
                        blind_kill: r.get::<_, i64>(7)? != 0,
                    })
                })
                .map_err(map_sqlite)?;
            rows.filter_map(|x| x.ok()).collect()
        };

        // Damages.
        let damages: Vec<DamageRow> = {
            let mut stmt = conn
                .prepare(
                    "SELECT attacker, victim, hp_damage, round_id
                 FROM damages WHERE match_id = ?1",
                )
                .map_err(map_sqlite)?;
            let rows = stmt
                .query_map([match_id as i64], |r| {
                    Ok(DamageRow {
                        attacker: r.get(0)?,
                        victim: r.get(1)?,
                        hp_damage: r.get::<_, Option<i64>>(2)?.unwrap_or(0),
                        round_id: r.get(3)?,
                    })
                })
                .map_err(map_sqlite)?;
            rows.filter_map(|x| x.ok()).collect()
        };

        // Roster.
        let players = repo::list_players(&pool, match_id)?;
        let team_of = |name: &str| {
            players
                .iter()
                .find(|p| p.name == name)
                .map(|p| p.team)
                .unwrap_or(Team::Spectator)
        };

        let mut aggregates: std::collections::BTreeMap<String, PlayerMatchStats> =
            std::collections::BTreeMap::new();
        for p in &players {
            let team = team_of(&p.name);
            aggregates.insert(
                p.name.clone(),
                PlayerMatchStats {
                    match_id,
                    player: p.name.clone(),
                    team: Some(team),
                    kills: 0,
                    deaths: 0,
                    assists: 0,
                    damage: 0,
                    adr: 0.0,
                    kast: 0.0,
                    rating: 0.0,
                    hs_pct: 0.0,
                    head_shots: 0,
                    multi_kills_2k: 0,
                    multi_kills_3k: 0,
                    multi_kills_4k: 0,
                    multi_kills_5k: 0,
                    clutches_won: 0,
                    clutches_total: 0,
                    entry_kills: 0,
                    entry_deaths: 0,
                    utility_damage: 0,
                    utility_enemies_flashed: 0,
                    flash_assists: 0,
                    first_bloods: 0,
                    mvp_count: 0,
                },
            );
        }

        for k in &kills {
            apply_kill_to_aggregates(k, &mut aggregates);
        }
        for d in &damages {
            if let Some(a) = aggregates.get_mut(&d.attacker) {
                a.damage += d.hp_damage.max(0) as u32;
            }
        }

        // Multi-kills (per round).
        let mut per_round: std::collections::BTreeMap<i64, Vec<&KillRow>> =
            std::collections::BTreeMap::new();
        for k in &kills {
            per_round.entry(k.round_id).or_default().push(k);
        }
        for ks in per_round.values() {
            let mut counts: std::collections::BTreeMap<&str, u32> =
                std::collections::BTreeMap::new();
            for k in ks {
                *counts.entry(k.attacker.as_str()).or_default() += 1;
            }
            for (name, count) in counts {
                if let Some(a) = aggregates.get_mut(name) {
                    match count {
                        2 => a.multi_kills_2k += 1,
                        3 => a.multi_kills_3k += 1,
                        4 => a.multi_kills_4k += 1,
                        _ if count >= 5 => a.multi_kills_5k += 1,
                        _ => {}
                    }
                }
            }
        }

        // Finalise: ADR, HS%, KAST, Rating 2.0.
        for a in aggregates.values_mut() {
            a.adr = if total_rounds > 0 {
                a.damage as f32 / total_rounds as f32
            } else {
                0.0
            };
            a.hs_pct = if a.kills > 0 {
                a.head_shots as f32 / a.kills as f32 * 100.0
            } else {
                0.0
            };
            a.kast = crate::core::analytics::kast_approx(a, &kills, total_rounds as u32);
            a.rating = crate::core::analytics::hltv_rating_v2(a, &kills, total_rounds as u32);
        }

        // Persist.
        let mut stmt = conn
            .prepare(
                "INSERT OR REPLACE INTO player_match_stats (
                match_id, player, team, kills, deaths, assists, damage,
                adr, kast, rating, hs_pct, head_shots,
                multi_kills_2k, multi_kills_3k, multi_kills_4k, multi_kills_5k,
                clutches_won, clutches_total, entry_kills, entry_deaths,
                utility_damage, utility_enemies_flashed, flash_assists,
                first_bloods, mvp_count
             ) VALUES (
                ?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11, ?12,
                ?13, ?14, ?15, ?16, ?17, ?18, ?19, ?20, ?21, ?22, ?23,
                ?24, ?25
             )",
            )
            .map_err(map_sqlite)?;
        for a in aggregates.values() {
            stmt.execute(rusqlite::params![
                a.match_id as i64,
                a.player,
                a.team.map(|t| t.as_str()).unwrap_or("Spectator"),
                a.kills as i64,
                a.deaths as i64,
                a.assists as i64,
                a.damage as i64,
                a.adr as f64,
                a.kast as f64,
                a.rating as f64,
                a.hs_pct as f64,
                a.head_shots as i64,
                a.multi_kills_2k as i64,
                a.multi_kills_3k as i64,
                a.multi_kills_4k as i64,
                a.multi_kills_5k as i64,
                a.clutches_won as i64,
                a.clutches_total as i64,
                a.entry_kills as i64,
                a.entry_deaths as i64,
                a.utility_damage as i64,
                a.utility_enemies_flashed as i64,
                a.flash_assists as i64,
                a.first_bloods as i64,
                a.mvp_count as i64,
            ])
            .map_err(map_sqlite)?;
        }
        Ok(())
    })
    .await
    .map_err(|e| AppError::Other(format!("join compute_and_store_stats: {e}")))?
}

#[derive(Debug)]
pub struct KillRow {
    pub tick: i64,
    pub attacker: String,
    pub victim: String,
    pub weapon: String,
    pub headshot: bool,
    pub round_id: i64,
    pub assister: Option<String>,
    pub blind_kill: bool,
}

#[derive(Debug)]
#[allow(dead_code)]
struct DamageRow {
    attacker: String,
    victim: String,
    hp_damage: i64,
    round_id: i64,
}

// ---------------------------------------------------------------------------
// Error mapping
// ---------------------------------------------------------------------------

fn map_sqlite(e: rusqlite::Error) -> AppError {
    AppError::Other(format!("sqlite: {e}"))
}

fn map_pool_err(e: r2d2::Error) -> AppError {
    AppError::Other(format!("db pool: {e}"))
}

// ---------------------------------------------------------------------------
// Pure helpers (testable without DB)
// ---------------------------------------------------------------------------

/// Apply a single kill to the per-player aggregates map. Safe to call
/// against kill rows whose `attacker` / `victim` / `assister` may or may
/// not be present in the roster — missing keys are silently ignored.
fn apply_kill_to_aggregates(
    k: &KillRow,
    aggregates: &mut std::collections::BTreeMap<String, PlayerMatchStats>,
) {
    if let Some(a) = aggregates.get_mut(&k.attacker) {
        a.kills += 1;
        if k.headshot {
            a.head_shots += 1;
        }
        if k.blind_kill {
            a.flash_assists += 1;
        }
    }
    if let Some(d) = aggregates.get_mut(&k.victim) {
        d.deaths += 1;
    }
    if let Some(assist_name) = &k.assister {
        if let Some(a) = aggregates.get_mut(assist_name) {
            a.assists += 1;
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn make_aggregates(players: &[&str]) -> std::collections::BTreeMap<String, PlayerMatchStats> {
        players
            .iter()
            .map(|p| {
                (
                    p.to_string(),
                    PlayerMatchStats {
                        match_id: 1,
                        player: (*p).to_string(),
                        team: None,
                        kills: 0,
                        deaths: 0,
                        assists: 0,
                        damage: 0,
                        adr: 0.0,
                        kast: 0.0,
                        rating: 0.0,
                        hs_pct: 0.0,
                        head_shots: 0,
                        multi_kills_2k: 0,
                        multi_kills_3k: 0,
                        multi_kills_4k: 0,
                        multi_kills_5k: 0,
                        clutches_won: 0,
                        clutches_total: 0,
                        entry_kills: 0,
                        entry_deaths: 0,
                        utility_damage: 0,
                        utility_enemies_flashed: 0,
                        flash_assists: 0,
                        first_bloods: 0,
                        mvp_count: 0,
                    },
                )
            })
            .collect()
    }

    fn k(attacker: &str, victim: &str, headshot: bool, blind: bool, assist: Option<&str>) -> KillRow {
        KillRow {
            tick: 0,
            attacker: attacker.into(),
            victim: victim.into(),
            weapon: "ak47".into(),
            headshot,
            round_id: 1,
            assister: assist.map(String::from),
            blind_kill: blind,
        }
    }

    #[test]
    fn kill_increments_attacker_kills_and_victim_deaths() {
        let mut agg = make_aggregates(&["alice", "bob"]);
        apply_kill_to_aggregates(&k("alice", "bob", false, false, None), &mut agg);
        assert_eq!(agg["alice"].kills, 1);
        assert_eq!(agg["alice"].head_shots, 0);
        assert_eq!(agg["alice"].flash_assists, 0);
        assert_eq!(agg["bob"].deaths, 1);
        assert_eq!(agg["bob"].assists, 0);
    }

    #[test]
    fn headshot_kill_increments_head_shots() {
        let mut agg = make_aggregates(&["alice", "bob"]);
        apply_kill_to_aggregates(&k("alice", "bob", true, false, None), &mut agg);
        assert_eq!(agg["alice"].kills, 1);
        assert_eq!(agg["alice"].head_shots, 1);
    }

    #[test]
    fn blind_kill_increments_flash_assists() {
        let mut agg = make_aggregates(&["alice", "bob"]);
        apply_kill_to_aggregates(&k("alice", "bob", false, true, None), &mut agg);
        assert_eq!(agg["alice"].kills, 1);
        assert_eq!(agg["alice"].flash_assists, 1);
    }

    #[test]
    fn assist_increments_assister() {
        let mut agg = make_aggregates(&["alice", "bob", "carol"]);
        apply_kill_to_aggregates(&k("alice", "bob", false, false, Some("carol")), &mut agg);
        assert_eq!(agg["alice"].kills, 1);
        assert_eq!(agg["bob"].deaths, 1);
        assert_eq!(agg["carol"].assists, 1);
    }

    #[test]
    fn missing_player_in_kill_is_ignored() {
        let mut agg = make_aggregates(&["alice"]);
        // bob is the victim but not in the roster
        apply_kill_to_aggregates(&k("alice", "bob", false, false, Some("eve")), &mut agg);
        assert_eq!(agg["alice"].kills, 1);
        // eve is not in roster, so no assist is added
        // alice and the only key exists; nothing crashes
    }

    #[test]
    fn multiple_kills_aggregate() {
        let mut agg = make_aggregates(&["alice", "bob", "carol"]);
        for _ in 0..3 {
            apply_kill_to_aggregates(&k("alice", "bob", false, false, Some("carol")), &mut agg);
        }
        assert_eq!(agg["alice"].kills, 3);
        assert_eq!(agg["bob"].deaths, 3);
        assert_eq!(agg["carol"].assists, 3);
    }
}
