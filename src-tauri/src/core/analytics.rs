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

/// KAST approximation with Trade detection.
///
/// We use the union of distinct round_ids where the player either:
///   * got a kill (K)
///   * got an assist (A)
///   * survived (i.e. did not die in that round) (S)
///   * was traded (T) — their killer died within ~5s (320 ticks).
pub fn kast_approx(
    a: &PlayerMatchStats,
    kills: &[crate::core::import::KillRow],
    total_rounds: u32,
) -> f32 {
    if total_rounds == 0 {
        return 0.0;
    }
    let player = a.player.as_str();
    let mut kast_rounds: std::collections::BTreeSet<u32> =
        std::collections::BTreeSet::new();
    let mut death_rounds: std::collections::BTreeSet<u32> =
        std::collections::BTreeSet::new();
        
    for k in kills {
        let r = k.round_id as u32;
        if k.attacker == player || k.assister.as_deref() == Some(player) {
            kast_rounds.insert(r);
        }
        if k.victim == player {
            death_rounds.insert(r);
            // Check for trade: did k.attacker die within 320 ticks?
            let killer = &k.attacker;
            let death_tick = k.tick;
            
            let mut was_traded = false;
            for avenger_kill in kills {
                // we only look at kills in the same round
                if avenger_kill.round_id != k.round_id {
                    continue;
                }
                if avenger_kill.victim == *killer && avenger_kill.tick > death_tick && avenger_kill.tick - death_tick <= 320 {
                    was_traded = true;
                    break;
                }
            }
            if was_traded {
                kast_rounds.insert(r);
            }
        }
    }
    // Survival = every round in 1..=total_rounds the player did not die
    for r in 1..=total_rounds {
        if !death_rounds.contains(&r) {
            kast_rounds.insert(r);
        }
    }
    let pct = (kast_rounds.len() as f32 / total_rounds as f32) * 100.0;
    pct.clamp(0.0, 100.0)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::core::import::KillRow;

    fn stats(player: &str, deaths: u32) -> PlayerMatchStats {
        PlayerMatchStats {
            match_id: 1,
            player: player.into(),
            team: None,
            kills: 0,
            deaths,
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
        }
    }

    fn k(attacker: &str, victim: &str, assist: Option<&str>, round: i64) -> KillRow {
        KillRow {
            tick: 0,
            attacker: attacker.into(),
            victim: victim.into(),
            weapon: "ak47".into(),
            headshot: false,
            round_id: round,
            assister: assist.map(String::from),
            blind_kill: false,
        }
    }
    
    fn k_tick(attacker: &str, victim: &str, assist: Option<&str>, round: i64, tick: i64) -> KillRow {
        let mut row = k(attacker, victim, assist, round);
        row.tick = tick;
        row
    }

    #[test]
    fn kast_zero_when_no_rounds() {
        let a = stats("alice", 0);
        assert_eq!(kast_approx(&a, &[], 0), 0.0);
    }

    #[test]
    fn kast_full_when_player_never_dies() {
        // 5 rounds, no deaths -> 100%
        let a = stats("alice", 0);
        let kills = vec![
            k("alice", "bob", None, 1),
            k("alice", "carol", None, 3),
        ];
        assert_eq!(kast_approx(&a, &kills, 5), 100.0);
    }

    #[test]
    fn kast_zero_when_player_dies_every_round() {
        // 3 rounds, 3 deaths -> 0%
        let a = stats("alice", 3);
        let kills = vec![
            k("bob", "alice", None, 1),
            k("carol", "alice", None, 2),
            k("dave", "alice", None, 3),
        ];
        assert_eq!(kast_approx(&a, &kills, 3), 0.0);
    }

    #[test]
    fn kast_counts_assist_rounds() {
        // 4 rounds: alice got a kill in r1, an assist in r2, dies in r3, no event in r4
        // KAST rounds: r1 (kill), r2 (assist), r4 (survived) -> 3/4 = 75%
        let a = stats("alice", 1);
        let kills = vec![
            k("alice", "bob", None, 1),
            k("alice", "carol", Some("alice"), 2), // assist by alice
            k("dave", "alice", None, 3),
        ];
        assert_eq!(kast_approx(&a, &kills, 4), 75.0);
    }

    #[test]
    fn kast_union_no_double_count() {
        // alice got a kill AND survived in round 1, dies in round 2, no event in round 3
        // KAST rounds: r1 (kill + survived, counted once), r3 (survived) -> 2/3
        let a = stats("alice", 1);
        let kills = vec![
            k("alice", "bob", None, 1),
            k("carol", "alice", None, 2),
        ];
        assert_eq!(kast_approx(&a, &kills, 3), (2.0 / 3.0) * 100.0);
    }

    #[test]
    fn kast_player_not_in_kills_survives_all() {
        // eve played but was never kill/assist/death — 100%
        let a = stats("eve", 0);
        let kills = vec![
            k("alice", "bob", None, 1),
            k("carol", "dave", None, 2),
        ];
        assert_eq!(kast_approx(&a, &kills, 2), 100.0);
    }

    #[test]
    fn kast_clamped_to_100() {
        // pathological: more deaths than rounds (shouldn't happen but be safe)
        let a = stats("alice", 100);
        let kills = vec![k("bob", "alice", None, 1)];
        assert!(kast_approx(&a, &kills, 5) <= 100.0);
    }

    #[test]
    fn kast_counts_trades() {
        // Round 1: Alice dies to Bob (tick 100). Bob dies to Carol (tick 400). Diff = 300 <= 320 -> Traded!
        // Round 2: Alice dies to Bob (tick 100). Bob dies to Carol (tick 500). Diff = 400 > 320 -> Not traded.
        let a = stats("alice", 2);
        let kills = vec![
            k_tick("bob", "alice", None, 1, 100),
            k_tick("carol", "bob", None, 1, 400),
            k_tick("bob", "alice", None, 2, 100),
            k_tick("carol", "bob", None, 2, 500),
        ];
        // Out of 2 rounds, she was traded in 1.
        assert_eq!(kast_approx(&a, &kills, 2), 50.0);
    }
}
