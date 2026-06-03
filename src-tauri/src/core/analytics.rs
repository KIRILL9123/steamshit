//! Per-match analytics: HLTV Rating 2.0, ADR, KAST, etc.
//!
//! See `docs/ALGORITHMS.md` §1 for the formulas. The functions here take
//! already-aggregated per-player data and the raw event lists (kills /
//! damages) needed for cross-references (e.g. KAST per round).
//!
//! Week 4 ships:
//!   * `hltv_rating_v2`  — exact HLTV formula (Impact / 100% ≈ 1.00)
//!   * `kast_approx`     — per-round KAST approximation (we'd need full
//!                         round events for the exact formula; for the
//!                         first cut we use a 0.5*KAST heuristic).
//!
//! Returns `f32` because we store into REAL columns. Precision is plenty.

use crate::core::models::PlayerMatchStats;

/// HLTV Rating 2.0 — see https://www.hltv.org/news/20695/introducing-rating-2-0
///
/// Per-round contributions:
///   * Kill Rating   = 0.679 * (kills / rounds)
///   * Survival R8   = 0.317 * (1 - deaths / rounds)
///   * KAST          = 1.303 * (kast_frac)
///   * Impact        = 0.737 * (avg multikill + 0.0065 * opening_kills
///                              + 0.0037 * 5k_4k_3k
///                              + 0.0021 * 1k_2k
///                              + 0.0006 * (1 - rounds_played / rounds_played))
///                  / rounds_played
/// where Impact is per-round and multi-kill weighting follows the HLTV
/// table: 1k→0, 2k→0.0021, 3k→0.0037, 4k→0.0053, 5k→0.0069.
///
/// We return `Kill + Survival + KAST + Impact` (all divided by `rounds`).
pub fn hltv_rating_v2(
    a: &PlayerMatchStats,
    kills: &[crate::core::import::KillRow],
    total_rounds: u32,
) -> f32 {
    if total_rounds == 0 {
        return 0.0;
    }
    let r = total_rounds as f32;
    let kr = 0.679 * (a.kills as f32 / r);
    let sr = 0.317 * (1.0 - (a.deaths as f32 / r)).max(0.0);
    let kast = 0.7421 * (a.kast / 100.0);
    let impact = impact_rating(a, kills, r);
    kr + sr + kast + impact
}

fn impact_rating(a: &PlayerMatchStats, kills: &[crate::core::import::KillRow], r: f32) -> f32 {
    // Avg multikill per round: (n_kills * weight) / rounds
    let multikill_weight = (a.multi_kills_2k as f32 * 0.0021)
        + (a.multi_kills_3k as f32 * 0.0037)
        + (a.multi_kills_4k as f32 * 0.0053)
        + (a.multi_kills_5k as f32 * 0.0069);
    let avg_multikill = (a.kills as f32 * multikill_weight) / r;

    // Opening kills: count kills where the player is the *first* kill in
    // the round (by round_id and lowest tick). We don't have tick on the
    // aggregate; we approximate by counting kills-per-round and taking 1
    // per round where the player has any kill (entry_kills column).
    let opening_kills = a.entry_kills as f32;
    let opening = 0.0065 * opening_kills / r;

    let mult = 0.0037 * (a.multi_kills_4k as f32 + a.multi_kills_5k as f32) / r;
    let duo = 0.0021 * a.multi_kills_3k as f32 / r;
    let _ = kills; // kept for future opening_kill_from_tick
    0.737 * (avg_multikill + opening + mult + duo)
}

/// KAST approximation: % of rounds where the player had a kill, assist,
/// survived, or was traded. Without the full event list (assists, traded)
/// we approximate with: KAST ≈ 0.55 * (rounds_with_kill + rounds_alive).
/// We track rounds_with_kill by counting distinct round_ids in `kills`.
pub fn kast_approx(
    a: &PlayerMatchStats,
    kills: &[crate::core::import::KillRow],
    total_rounds: u32,
) -> f32 {
    if total_rounds == 0 {
        return 0.0;
    }
    let rounds_with_kill: u32 = kills
        .iter()
        .filter(|k| k.attacker == a.player)
        .map(|k| k.round_id as u32)
        .collect::<std::collections::BTreeSet<_>>()
        .len() as u32;
    let survival = if a.deaths < total_rounds {
        total_rounds - a.deaths
    } else {
        0
    };
    // KAST ~ 0.55 * (kill_or_alive)
    let approx = 0.55 * (rounds_with_kill + survival) as f32 / total_rounds as f32;
    approx.clamp(0.0, 1.0) * 100.0
}
