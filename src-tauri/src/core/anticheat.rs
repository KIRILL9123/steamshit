//! Basic anticheat heuristics computed from match data in SQLite.
//!
//! These are STATISTICAL anomalies, not proof of cheating.
//! Always shown with a disclaimer in the UI.

use crate::core::db::DbPool;
use crate::core::models::{AnticheatFlag, AnticheatHeuristic};
use crate::error::AppResult;
use crate::core::repo;

/// Run all heuristics for the given match. Returns a list of flags (may be empty).
pub async fn analyse(pool: &DbPool, sidecar: &crate::sidecar::SidecarHandle, db_path: &str, match_id: u64) -> AppResult<Vec<AnticheatFlag>> {
    let stats = repo::list_match_stats(pool, match_id)?;
    if stats.is_empty() {
        return Ok(vec![]);
    }

    // Compute match averages for comparison
    let avg_hs_pct: f32 = stats.iter().filter(|s| s.kills > 0).map(|s| s.hs_pct).sum::<f32>()
        / stats.iter().filter(|s| s.kills > 0).count().max(1) as f32;
    let total_rounds = get_total_rounds(pool, match_id).unwrap_or(20) as f32;

    let mut flags: Vec<AnticheatFlag> = Vec::new();
    let mut flag_id: u64 = 1;

    for s in &stats {
        // Skip spectators and players with no kills
        if s.kills == 0 && s.deaths == 0 {
            continue;
        }

        // ─── Heuristic 1: HS ratio anomaly ───────────────────────────────────
        // Flag players whose HS% is significantly above match average
        if s.kills >= 5 && s.hs_pct > 70.0 && s.hs_pct > avg_hs_pct + 20.0 {
            let severity = ((s.hs_pct - 70.0) / 30.0).min(1.0);
            flags.push(AnticheatFlag {
                id: flag_id,
                match_id,
                player: s.player.clone(),
                heuristic: AnticheatHeuristic::HeadshotRatioAnomaly,
                severity,
                evidence_count: Some(s.head_shots),
                details_json: Some(serde_json::json!({
                    "hs_pct": s.hs_pct,
                    "avg_match_hs_pct": avg_hs_pct,
                    "kills": s.kills
                }).to_string()),
            });
            flag_id += 1;
        }

        // ─── Heuristic 2: Kills-per-round anomaly ───────────────────────────
        let kpr = if total_rounds > 0.0 { s.kills as f32 / total_rounds } else { 0.0 };
        if kpr > 1.2 && s.kills >= 15 {
            let severity = ((kpr - 1.0) / 1.0).min(1.0);
            flags.push(AnticheatFlag {
                id: flag_id,
                match_id,
                player: s.player.clone(),
                heuristic: AnticheatHeuristic::InconsistencyScore,
                severity,
                evidence_count: Some(s.kills),
                details_json: Some(serde_json::json!({
                    "kills_per_round": kpr,
                    "total_kills": s.kills,
                    "rounds": total_rounds as u32
                }).to_string()),
            });
            flag_id += 1;
        }

        // ─── Heuristic 3: Very high rating with low deaths ──────────────────
        if s.rating > 1.8 && s.deaths < 5 && s.kills > 10 {
            let severity = ((s.rating - 1.5) / 1.0).min(1.0);
            flags.push(AnticheatFlag {
                id: flag_id,
                match_id,
                player: s.player.clone(),
                heuristic: AnticheatHeuristic::CrosshairPlacement,
                severity,
                evidence_count: Some(s.kills),
                details_json: Some(serde_json::json!({
                    "rating": s.rating,
                    "deaths": s.deaths,
                    "kills": s.kills
                }).to_string()),
            });
            flag_id += 1;
        }

        // ─── Heuristic 4: Multi-kill anomaly ────────────────────────────────
        let multi_total = s.multi_kills_3k + s.multi_kills_4k + s.multi_kills_5k;
        let multi_rate = if total_rounds > 0.0 { multi_total as f32 / total_rounds } else { 0.0 };
        if multi_rate > 0.4 && multi_total >= 5 {
            let severity = (multi_rate / 0.8).min(1.0);
            flags.push(AnticheatFlag {
                id: flag_id,
                match_id,
                player: s.player.clone(),
                heuristic: AnticheatHeuristic::SnapAim,
                severity,
                evidence_count: Some(multi_total),
                details_json: Some(serde_json::json!({
                    "3k": s.multi_kills_3k,
                    "4k": s.multi_kills_4k,
                    "5k": s.multi_kills_5k,
                    "multi_rate": multi_rate
                }).to_string()),
            });
            flag_id += 1;
        }

        // ─── Heuristic 5: Flash-assisted kills anomaly ──────────────────────
        // Very high first-blood rate can indicate unusual game sense
        let fb_rate = if total_rounds > 0.0 { s.first_bloods as f32 / total_rounds } else { 0.0 };
        if fb_rate > 0.5 && s.first_bloods >= 8 {
            let severity = ((fb_rate - 0.4) / 0.6).min(1.0);
            flags.push(AnticheatFlag {
                id: flag_id,
                match_id,
                player: s.player.clone(),
                heuristic: AnticheatHeuristic::ReactionTimeAnomaly,
                severity,
                evidence_count: Some(s.first_bloods),
                details_json: Some(serde_json::json!({
                    "first_bloods": s.first_bloods,
                    "fb_rate": fb_rate,
                    "rounds": total_rounds as u32
                }).to_string()),
            });
            flag_id += 1;
        }
    }

    // Call Python sidecar for advanced heuristics
    let mut adv_flags = sidecar_analysis(sidecar, db_path, match_id, &mut flag_id).await.unwrap_or_default();
    flags.append(&mut adv_flags);

    Ok(flags)
}

async fn sidecar_analysis(
    sidecar: &crate::sidecar::SidecarHandle,
    db_path: &str,
    match_id: u64,
    flag_id: &mut u64,
) -> AppResult<Vec<AnticheatFlag>> {
    let mut flags = Vec::new();
    
    let params = serde_json::json!({
        "db_path": db_path,
        "match_id": match_id
    });
    
    if let Ok(res) = sidecar.call(crate::sidecar::methods::ANTICHEAT_RUN_HEURISTIC, params).await {
        if let Some(arr) = res.as_array() {
            for item in arr {
                if let Ok(mut flag) = serde_json::from_value::<AnticheatFlag>(item.clone()) {
                    flag.id = *flag_id;
                    *flag_id += 1;
                    flag.match_id = match_id;
                    flags.push(flag);
                }
            }
        }
    }
    
    Ok(flags)
}

fn get_total_rounds(pool: &DbPool, match_id: u64) -> AppResult<u32> {
    let conn = pool.get().map_err(|e| crate::error::AppError::Other(format!("db pool: {e}")))?;
    let count: i64 = conn
        .query_row(
            "SELECT COUNT(*) FROM rounds WHERE match_id = ?1",
            [match_id as i64],
            |r| r.get(0),
        )
        .map_err(|e| crate::error::AppError::Other(format!("sqlite: {e}")))?;
    Ok(count as u32)
}

/// Compute overall suspicion score (0.0–1.0) for a player across all their flags.
pub fn suspicion_score(flags: &[AnticheatFlag], player: &str) -> f32 {
    let player_flags: Vec<&AnticheatFlag> = flags.iter().filter(|f| f.player == player).collect();
    if player_flags.is_empty() {
        return 0.0;
    }
    // Weighted combination: max flag + number of distinct heuristics
    let max_severity: f32 = player_flags.iter().map(|f| f.severity).fold(0.0f32, f32::max);
    let distinct_heuristics = {
        let mut seen = std::collections::HashSet::new();
        for f in &player_flags {
            seen.insert(f.heuristic.as_str());
        }
        seen.len() as f32
    };
    let score = max_severity * 0.7 + (distinct_heuristics / 5.0).min(1.0) * 0.3;
    score.min(1.0)
}
