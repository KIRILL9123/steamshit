//! Rule-based coaching tips generated from per-player match statistics.

use crate::core::db::DbPool;
use crate::core::repo::{self, CoachTipInsert};
use crate::error::AppResult;

/// Generate tips for all players in the match and write them to the DB.
pub fn generate_and_store(pool: &DbPool, match_id: u64) -> AppResult<()> {
    let tips = generate(pool, match_id)?;
    repo::upsert_coach_tips(pool, match_id, &tips)
}

/// Generate coaching tips for all players in the match.
pub fn generate(pool: &DbPool, match_id: u64) -> AppResult<Vec<CoachTipInsert>> {
    let stats = repo::list_match_stats(pool, match_id)?;
    if stats.is_empty() {
        return Ok(vec![]);
    }

    let total_rounds = {
        let conn = pool.get().map_err(|e| crate::error::AppError::Other(format!("db pool: {e}")))?;
        let count: i64 = conn
            .query_row("SELECT COUNT(*) FROM rounds WHERE match_id = ?1", [match_id as i64], |r| r.get(0))
            .map_err(|e| crate::error::AppError::Other(format!("sqlite: {e}")))?;
        count.max(1) as f32
    };

    let avg_adr: f32 = stats.iter().map(|s| s.adr).sum::<f32>() / stats.len() as f32;
    let avg_kast: f32 = stats.iter().map(|s| s.kast).sum::<f32>() / stats.len() as f32;

    let mut tips = Vec::new();

    for s in &stats {
        // ─── Rule 1: Low ADR ────────────────────────────────────────────────
        if s.adr < 50.0 && s.adr < avg_adr - 20.0 {
            tips.push(CoachTipInsert {
                player: Some(s.player.clone()),
                category: "aim".into(),
                priority: 80,
                title: "Низкий ADR".into(),
                body: format!(
                    "Ваш ADR составил {:.0}, что значительно ниже среднего ({:.0}). \
                     Стреляйте прицельнее, старайтесь наносить максимальный урон перед смертью.",
                    s.adr, avg_adr
                ),
                metric_name: Some("adr".into()),
                current_value: Some(s.adr),
                target_value: Some(75.0),
            });
        }

        // ─── Rule 2: Low KAST ───────────────────────────────────────────────
        if s.kast < 50.0 {
            tips.push(CoachTipInsert {
                player: Some(s.player.clone()),
                category: "trade".into(),
                priority: 75,
                title: "Низкий KAST".into(),
                body: format!(
                    "Ваш KAST составил {:.0}%, что говорит о неучастии в большинстве раундов. \
                     Старайтесь как минимум поддерживать союзников: трейдить убийства, давать дымы, ослеплять.",
                    s.kast
                ),
                metric_name: Some("kast".into()),
                current_value: Some(s.kast),
                target_value: Some(70.0),
            });
        }

        // ─── Rule 3: High deaths ────────────────────────────────────────────
        let deaths_per_round = s.deaths as f32 / total_rounds;
        if deaths_per_round > 0.8 {
            tips.push(CoachTipInsert {
                player: Some(s.player.clone()),
                category: "positioning".into(),
                priority: 70,
                title: "Слишком много смертей".into(),
                body: format!(
                    "Вы умирали {:.1} раза за раунд. Держитесь на более безопасных позициях, \
                     не пикайте в одиночку без информации.",
                    deaths_per_round
                ),
                metric_name: Some("deaths_per_round".into()),
                current_value: Some(deaths_per_round),
                target_value: Some(0.6),
            });
        }

        // ─── Rule 4: Low HS% (poor aim) ─────────────────────────────────────
        if s.kills >= 5 && s.hs_pct < 20.0 {
            tips.push(CoachTipInsert {
                player: Some(s.player.clone()),
                category: "aim".into(),
                priority: 65,
                title: "Мало хедшотов".into(),
                body: format!(
                    "Ваш % хедшотов — {:.0}%. Это говорит о неправильном позиционировании прицела. \
                     Тренируйте предицеливание: держите прицел на уровне головы.",
                    s.hs_pct
                ),
                metric_name: Some("hs_pct".into()),
                current_value: Some(s.hs_pct),
                target_value: Some(40.0),
            });
        }

        // ─── Rule 5: No multi-kills ──────────────────────────────────────────
        if s.kills >= 10 && s.multi_kills_2k == 0 && s.multi_kills_3k == 0 {
            tips.push(CoachTipInsert {
                player: Some(s.player.clone()),
                category: "trade".into(),
                priority: 50,
                title: "Нет мультикиллов".into(),
                body: "У вас не было ни одного двойного убийства за матч. Старайтесь дуэлировать двух противников в одном столкновении: сначала убейте одного, быстро переводите прицел.".into(),
                metric_name: Some("multi_kills_2k".into()),
                current_value: Some(0.0),
                target_value: Some(3.0),
            });
        }

        // ─── Rule 6: Clutch rate ─────────────────────────────────────────────
        if s.clutches_total >= 3 && s.clutches_won == 0 {
            tips.push(CoachTipInsert {
                player: Some(s.player.clone()),
                category: "timing".into(),
                priority: 60,
                title: "Не побеждаете в клатчах".into(),
                body: format!(
                    "Вы проиграли все {} клатчей. В ситуации 1vX: не торопитесь, ищите информацию, \
                     играйте от позиции и используйте время.",
                    s.clutches_total
                ),
                metric_name: Some("clutch_win_rate".into()),
                current_value: Some(0.0),
                target_value: Some(0.33),
            });
        }

        // ─── Rule 7: Utility usage ───────────────────────────────────────────
        if s.utility_damage == 0 && s.flash_assists == 0 {
            tips.push(CoachTipInsert {
                player: Some(s.player.clone()),
                category: "utility".into(),
                priority: 45,
                title: "Не используете утилити".into(),
                body: "За весь матч вы не нанесли урона гранатами и не дали ни одного флеш-асиста. \
                       Гранаты — это бесплатный урон и инициатива. Учите стандартные линап для вашей карты.".into(),
                metric_name: Some("utility_damage".into()),
                current_value: Some(0.0),
                target_value: Some(30.0),
            });
        }

        // ─── Rule 8: Entry kills ─────────────────────────────────────────────
        let entry_rate = if total_rounds > 0.0 { s.entry_kills as f32 / total_rounds } else { 0.0 };
        if entry_rate > 0.3 && s.entry_deaths > s.entry_kills * 2 {
            tips.push(CoachTipInsert {
                player: Some(s.player.clone()),
                category: "positioning".into(),
                priority: 55,
                title: "Плохой entry-процент".into(),
                body: format!(
                    "Вы часто открываете раунд (entry_deaths: {}), но побеждаете лишь {} раз. \
                     Смените тактику: не входите первым без подготовки. Используйте флеши и дымы.",
                    s.entry_deaths, s.entry_kills
                ),
                metric_name: Some("entry_success_rate".into()),
                current_value: Some(if s.entry_deaths > 0 { s.entry_kills as f32 / s.entry_deaths as f32 } else { 0.0 }),
                target_value: Some(0.5),
            });
        }
    }

    // Suppress unused variable warning
    let _ = avg_kast;

    // ─── Global team tip: Economy management ─────────────────────────────────
    tips.push(CoachTipInsert {
        player: None,
        category: "economy".into(),
        priority: 30,
        title: "Следите за экономикой команды".into(),
        body: "Согласовывайте закупки с тиммейтами. Если 3+ игрока сохраняют, остальным тоже стоит сохранить или сделать полный ЭКО.".into(),
        metric_name: None,
        current_value: None,
        target_value: None,
    });

    Ok(tips)
}
