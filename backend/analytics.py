import json
import logging
import math
import os
import sqlite3

import polars as pl
from backend.database import (
    DB_PATH,
    get_connection,
    load_kills,
    save_anticheat_flags,
    save_coach_tips,
)

log = logging.getLogger("backend.analytics")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_damages(db_path: str, match_id: int) -> pl.DataFrame:
    """Load damage events for a match (synchronous, for analytics)."""
    conn = sqlite3.connect(db_path)
    try:
        return pl.read_database(
            f"SELECT * FROM damages WHERE match_id = {match_id}", conn
        )
    finally:
        conn.close()


def _load_grenades(db_path: str, match_id: int) -> pl.DataFrame:
    """Load grenade events for a match (synchronous, for analytics)."""
    conn = sqlite3.connect(db_path)
    try:
        return pl.read_database(
            f"SELECT * FROM grenades WHERE match_id = {match_id}", conn
        )
    finally:
        conn.close()


def _load_rounds(db_path: str, match_id: int) -> pl.DataFrame:
    """Load rounds for a match (synchronous, for analytics)."""
    conn = sqlite3.connect(db_path)
    try:
        return pl.read_database(
            f"SELECT id, round_num, winner, ct_score, t_score, start_tick, freeze_end_tick, end_tick "
            f"FROM rounds WHERE match_id = {match_id} ORDER BY round_num", conn
        )
    finally:
        conn.close()


def _load_weapon_fires(db_path: str, match_id: int) -> pl.DataFrame:
    """Load weapon_fires for a match (synchronous, for analytics)."""
    conn = sqlite3.connect(db_path)
    try:
        return pl.read_database(
            f"SELECT * FROM weapon_fires WHERE match_id = {match_id}", conn
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# ANTICHEAT
# ---------------------------------------------------------------------------

async def run_anticheat_analysis(match_id: int, ticks_df: pl.DataFrame | None = None):
    """Run anticheat heuristic analysis and store flags in the DB."""
    log.info(f"Running anticheat analysis for match {match_id}")

    ticks = ticks_df
    if ticks is None or ticks.is_empty():
        # Load match file_path and parse ticks on the fly
        file_path = None
        try:
            async with get_connection() as conn:
                async with conn.execute("SELECT file_path FROM matches WHERE id = ?", (match_id,)) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        file_path = row["file_path"]
        except Exception as e:
            log.error(f"Failed to query match file_path for anticheat: {e}")
            return []

        if not file_path or not os.path.exists(file_path):
            raise FileNotFoundError(f"Demo file not found on disk: {file_path}")

        try:
            log.info(f"Parsing ticks on the fly from {file_path} for anticheat")
            from demoparser2 import DemoParser
            parser = DemoParser(file_path)
            ticks = pl.from_pandas(parser.parse_ticks([
                "X", "Y", "Z", "yaw", "pitch", "health", "armor_value",
                "velocity_X", "velocity_Y", "velocity_Z", "is_alive",
                "is_planting", "is_defusing"
            ]))
            ticks = ticks.rename({"name": "player"})
        except Exception as e:
            log.error(f"Failed to parse ticks on the fly: {e}")
            return []

    try:
        kills = load_kills(DB_PATH, match_id)
    except Exception as e:
        log.error(f"Failed to load data for anticheat: {e}")
        return []

    if kills.is_empty() or ticks.is_empty():
        log.warning("No kills or ticks found for anticheat analysis")
        return []

    flags = []

    # ------------------------------------------------------------------
    # 1. Snap Aim — резкий разворот прицела перед убийством
    # Флаг: severity > 0.3
    # ------------------------------------------------------------------
    for player_name in kills["attacker"].unique():
        if not player_name:
            continue
        player_kills = kills.filter(kills["attacker"] == player_name)
        if player_kills.is_empty():
            continue

        player_ticks = ticks.filter(ticks["player"] == player_name)
        if player_ticks.is_empty():
            continue

        snap_count = 0
        total_kills = len(player_kills)
        max_observed_yaw = 0.0

        for kill_tick in player_kills["tick"].to_list():
            # window of 10 ticks before the kill
            window = player_ticks.filter(
                (player_ticks["tick"] <= kill_tick) & (player_ticks["tick"] > kill_tick - 10)
            )
            if len(window) < 2:
                continue

            yaw_diffs = window["yaw"].diff().fill_null(0).abs()
            max_yaw_change = yaw_diffs.max()

            if max_yaw_change is not None and max_yaw_change > 45.0:
                snap_count += 1
                if max_yaw_change > max_observed_yaw:
                    max_observed_yaw = float(max_yaw_change)

        if snap_count > 0:
            severity = min(snap_count / total_kills * 5.0, 1.0)
            if severity > 0.3:
                flags.append({
                    "player": player_name,
                    "heuristic": "snap_aim",
                    "severity": severity,
                    "evidence_count": snap_count,
                    "details_json": json.dumps({
                        "max_yaw_change_threshold": 45.0,
                        "max_observed_yaw_change": round(max_observed_yaw, 2),
                        "total_kills": total_kills,
                    })
                })

    # ------------------------------------------------------------------
    # 2. Headshot Ratio Anomaly — аномально высокий HS%
    # Флаг: severity > 0 (т.е. hs_ratio > 0.8 при >10 убийствах)
    # ------------------------------------------------------------------
    for player_name in kills["attacker"].unique():
        if not player_name:
            continue
        player_kills = kills.filter(kills["attacker"] == player_name)
        hs_ratio = player_kills["headshot"].sum() / max(len(player_kills), 1)
        if len(player_kills) > 10 and hs_ratio > 0.8:
            flags.append({
                "player": player_name,
                "heuristic": "headshot_ratio_anomaly",
                "severity": min((hs_ratio - 0.8) * 5.0, 1.0),
                "evidence_count": int(player_kills["headshot"].sum()),
                "details_json": json.dumps({"hs_ratio": round(hs_ratio, 3)})
            })

    # ------------------------------------------------------------------
    # 3. Velocity Snap — подозрительное мгновенное перемещение
    # Логика: скорость между соседними тиками (ΔXY / Δtick) > 400 юн/тик
    #   эквивалентно телепортации / speedhack.
    # severity = min(1.0, (max_speed - 400) / 400)
    # Флаг: severity > 0.3
    # ------------------------------------------------------------------
    try:
        rounds_df = _load_rounds(DB_PATH, match_id)
        exclude_ticks = set()
        if not rounds_df.is_empty():
            for r in rounds_df.iter_rows(named=True):
                st = r.get("start_tick")
                ft = r.get("freeze_end_tick")
                if st is not None:
                    for t in range(st, st + 5):
                        exclude_ticks.add(t)
                if ft is not None:
                    for t in range(ft, ft + 5):
                        exclude_ticks.add(t)
        exclude_list = list(exclude_ticks)

        for player_name in ticks["player"].unique():
            if not player_name:
                continue
            pt = ticks.filter(ticks["player"] == player_name).sort("tick")
            if len(pt) < 2:
                continue

            # Вычисляем дельты между соседними тиками
            dx = pt["X"].diff().fill_null(0)
            dy = pt["Y"].diff().fill_null(0)
            dt = pt["tick"].diff().fill_null(1).clip(lower_bound=1).cast(pl.Float64)
            speeds = ((dx ** 2 + dy ** 2) ** 0.5) / dt

            # Фильтруем телепортации респауна и пробелы в трекинге
            is_excluded = pt["tick"].is_in(exclude_list)
            speeds = pl.select(pl.when(is_excluded | (dt > 10.0)).then(0.0).otherwise(speeds)).to_series()

            max_speed = float(speeds.max() or 0.0)
            # Найдём тик с максимальной скоростью
            max_idx = int(speeds.arg_max() or 0)
            suspicious_tick = int(pt["tick"][max_idx]) if max_idx < len(pt) else 0

            if max_speed > 400.0:
                severity = min(1.0, (max_speed - 400.0) / 400.0)
                if severity > 0.3:
                    flags.append({
                        "player": player_name,
                        "heuristic": "velocity_snap",
                        "severity": round(severity, 3),
                        "evidence_count": int((speeds > 400.0).sum()),
                        "details_json": json.dumps({
                            "max_speed_ups": round(max_speed, 2),
                            "tick": suspicious_tick,
                            "threshold_ups": 400.0,
                        })
                    })
    except Exception as e:
        log.warning(f"velocity_snap heuristic failed: {e}")

    # ------------------------------------------------------------------
    # 4. Silent Aim — мгновенный хедшот с момента первого попадания
    # Логика: если (kill_tick - first_hit_tick) < 13 тиков И headshot=1 —
    #   подозрительное убийство.
    # severity = fast_hs_kills / total_kills игрока
    # Флаг: ratio > 0.4 И fast_hs_kills >= 3
    # ------------------------------------------------------------------
    try:
        damages = _load_damages(DB_PATH, match_id)
        if not damages.is_empty() and "attacker" in damages.columns and "victim" in damages.columns:
            for player_name in kills["attacker"].unique():
                if not player_name:
                    continue
                player_kills = kills.filter(kills["attacker"] == player_name)
                total_kills = len(player_kills)
                if total_kills == 0:
                    continue

                # Только HS-убийства
                hs_kills = player_kills.filter(player_kills["headshot"] == 1)
                if hs_kills.is_empty():
                    continue

                # Повреждения нанесённые этим игроком
                player_dmg = damages.filter(damages["attacker"] == player_name)

                fast_hs_count = 0
                for row in hs_kills.iter_rows(named=True):
                    kill_tick = row["tick"] or 0
                    rid = row["round_id"]
                    victim = row["victim"]

                    # Попадания по этому victim строго до тика убийства
                    relevant_hits = player_dmg.filter(
                        (player_dmg["round_id"] == rid) &
                        (player_dmg["victim"] == victim) &
                        (player_dmg["tick"] < kill_tick)
                    )
                    if len(relevant_hits) < 2:
                        continue
                    first_hit_tick = int(relevant_hits["tick"].min() or 0)
                    delta = kill_tick - first_hit_tick

                    # < 13 тиков (~200 мс при 64 tick)
                    if 0 <= delta < 13:
                        fast_hs_count += 1

                if fast_hs_count >= 3:
                    ratio = fast_hs_count / total_kills
                    if ratio > 0.4:
                        flags.append({
                            "player": player_name,
                            "heuristic": "silent_aim",
                            "severity": round(min(1.0, (ratio - 0.4) * 3.0 + 0.3), 3),
                            "evidence_count": fast_hs_count,
                            "details_json": json.dumps({
                                "fast_hs_kills": fast_hs_count,
                                "total_kills": total_kills,
                                "ratio": round(ratio, 3),
                                "tick_window": 13,
                            })
                        })
    except Exception as e:
        log.warning(f"silent_aim heuristic failed: {e}")

    # ------------------------------------------------------------------
    # 5. No Recoil — аномально стабильный pitch между выстрелами очереди
    # Логика: очередь = выстрелы с Δtick < ~32 (≈ 0.5 с при 64 tick).
    #   std(pitch) внутри очереди длиной > 5 выстрелов < 0.5 градуса —
    #   подозрительно.
    # severity = suspicious_bursts / total_bursts
    # Флаг: severity > 0.3
    # ------------------------------------------------------------------
    try:
        weapon_fires = _load_weapon_fires(DB_PATH, match_id)
        if (not weapon_fires.is_empty()
                and "attacker" in weapon_fires.columns
                and "pitch" in ticks.columns):
            # Для каждого выстрела из weapon_fires найдём pitch из ticks
            # (ближайший тик ≤ tick выстрела)
            for player_name in weapon_fires["attacker"].unique() if "attacker" in weapon_fires.columns else []:
                if not player_name:
                    continue
                pf = weapon_fires.filter(weapon_fires["attacker"] == player_name).sort("tick")
                pt = ticks.filter(ticks["player"] == player_name).sort("tick")
                if pf.is_empty() or pt.is_empty():
                    continue

                # Быстрый join: для каждого выстрела — ближайший pitch из ticks
                fire_ticks = pf["tick"].to_list()
                tick_arr = pt["tick"].to_list()
                pitch_arr = pt["pitch"].to_list()

                # Map: tick → pitch (ближайший предшествующий)
                pitches_for_fires = []
                j = 0
                for ft in fire_ticks:
                    while j + 1 < len(tick_arr) and tick_arr[j + 1] <= ft:
                        j += 1
                    pitches_for_fires.append(pitch_arr[j] if j < len(pitch_arr) else None)

                # Нарезаем очереди: новая очередь если Δtick > 32
                BURST_GAP = 32
                MIN_BURST_LEN = 5
                STD_THRESHOLD = 0.5

                suspicious_bursts = 0
                total_bursts = 0
                pitch_stds = []

                burst_pitches: list[float] = []
                prev_tick = None
                for ft, pp in zip(fire_ticks, pitches_for_fires):
                    if pp is None:
                        continue
                    if prev_tick is not None and (ft - prev_tick) > BURST_GAP:
                        # Конец очереди
                        if len(burst_pitches) >= MIN_BURST_LEN:
                            total_bursts += 1
                            mean_p = sum(burst_pitches) / len(burst_pitches)
                            variance = sum((x - mean_p) ** 2 for x in burst_pitches) / len(burst_pitches)
                            std_p = math.sqrt(variance)
                            pitch_stds.append(std_p)
                            if std_p < STD_THRESHOLD:
                                suspicious_bursts += 1
                        burst_pitches = []
                    burst_pitches.append(pp)
                    prev_tick = ft

                # Последняя очередь
                if len(burst_pitches) >= MIN_BURST_LEN:
                    total_bursts += 1
                    mean_p = sum(burst_pitches) / len(burst_pitches)
                    variance = sum((x - mean_p) ** 2 for x in burst_pitches) / len(burst_pitches)
                    std_p = math.sqrt(variance)
                    pitch_stds.append(std_p)
                    if std_p < STD_THRESHOLD:
                        suspicious_bursts += 1

                if total_bursts > 0:
                    severity = suspicious_bursts / total_bursts
                    avg_pitch_std = sum(pitch_stds) / len(pitch_stds) if pitch_stds else 0.0
                    if severity > 0.3:
                        flags.append({
                            "player": player_name,
                            "heuristic": "no_recoil",
                            "severity": round(min(1.0, severity), 3),
                            "evidence_count": suspicious_bursts,
                            "details_json": json.dumps({
                                "suspicious_bursts": suspicious_bursts,
                                "total_bursts": total_bursts,
                                "avg_pitch_std": round(avg_pitch_std, 4),
                                "std_threshold": STD_THRESHOLD,
                            })
                        })
    except Exception as e:
        log.warning(f"no_recoil heuristic failed: {e}")

    # ------------------------------------------------------------------
    # 6. Position Exploit — убийства из аномально низкой Z-позиции
    # Логика: attacker_z < (median_z - 3 * std_z) для карты.
    # severity = underground_kills / total_kills
    # Флаг: severity > 0.25 И underground_kills >= 2
    # ------------------------------------------------------------------
    try:
        if "attacker_z" in kills.columns:
            all_z = kills["attacker_z"].drop_nulls()
            if len(all_z) >= 10:
                z_values = all_z.to_list()
                median_z = float(pl.Series(z_values).median() or 0.0)
                mean_z = sum(z_values) / len(z_values)
                variance_z = sum((v - mean_z) ** 2 for v in z_values) / len(z_values)
                std_z = math.sqrt(variance_z)
                threshold_z = median_z - 3.0 * std_z

                for player_name in kills["attacker"].unique():
                    if not player_name:
                        continue
                    player_kills = kills.filter(kills["attacker"] == player_name)
                    total_kills = len(player_kills)
                    if total_kills < 5:
                        continue

                    player_z = player_kills["attacker_z"].drop_nulls()
                    underground_kills = int((player_z < threshold_z).sum())

                    if underground_kills >= 2:
                        severity = underground_kills / total_kills
                        if severity > 0.25:
                            flags.append({
                                "player": player_name,
                                "heuristic": "position_exploit",
                                "severity": round(min(1.0, severity * 2.0), 3),
                                "evidence_count": underground_kills,
                                "details_json": json.dumps({
                                    "underground_kills": underground_kills,
                                    "total_kills": total_kills,
                                    "median_z": round(median_z, 2),
                                    "threshold_z": round(threshold_z, 2),
                                })
                            })
    except Exception as e:
        log.warning(f"position_exploit heuristic failed: {e}")

    # Save to database
    async with get_connection() as conn:
        await save_anticheat_flags(conn, match_id, flags)

    log.info(f"Anticheat analysis complete: {len(flags)} flags for match {match_id}")
    return flags


# ---------------------------------------------------------------------------
# COACH TIPS
# ---------------------------------------------------------------------------

async def generate_coach_tips(match_id: int):
    """Generate coaching tips and store them in the DB."""
    log.info(f"Generating coaching tips for match {match_id}")
    try:
        kills = load_kills(DB_PATH, match_id)
    except Exception as e:
        log.error(f"Failed to load kills for coaching tips: {e}")
        return []

    if kills.is_empty():
        log.warning("No kills found for coaching tips")
        return []

    tips = []

    # Загружаем дополнительные данные один раз
    try:
        grenades = _load_grenades(DB_PATH, match_id)
    except Exception:
        grenades = pl.DataFrame()

    try:
        rounds = _load_rounds(DB_PATH, match_id)
    except Exception:
        rounds = pl.DataFrame()

    total_rounds = len(rounds) if not rounds.is_empty() else 0

    # ------------------------------------------------------------------
    # 1. Низкий HS% — совет по аиму
    # Порог: HS% < 25% при > 10 убийствах
    # ------------------------------------------------------------------
    for player_name in kills["attacker"].unique():
        if not player_name:
            continue
        player_kills = kills.filter(kills["attacker"] == player_name)
        total_kills = len(player_kills)
        if total_kills > 10:
            hs_pct = player_kills["headshot"].sum() / total_kills
            if hs_pct < 0.25:
                tips.append({
                    "player": player_name,
                    "category": "aim",
                    "priority": 7,
                    "title": "Низкий процент хедшотов",
                    "body": (
                        "Тренируй crosshair placement. Aim Botz с фокусом на хедшоты, "
                        "15 минут перед игрой — заметный эффект за неделю."
                    ),
                    "metric_name": "hs_pct",
                    "current_value": round(hs_pct * 100.0, 1),
                    "target_value": 40.0,
                    "evidence_json": json.dumps({"kills": total_kills, "hs_pct": round(hs_pct, 3)})
                })

    # ------------------------------------------------------------------
    # 2. Слишком часто умираешь первым — агрессия без трейда
    # Порог: first_death_rate > 40% при > 5 смертях
    # ------------------------------------------------------------------
    for player_name in kills["victim"].unique():
        if not player_name:
            continue

        first_kills = kills.sort("tick").group_by("round_id").first()
        if first_kills.is_empty():
            continue

        first_deaths_as_player = first_kills.filter(first_kills["victim"] == player_name)
        total_first_deaths = len(first_deaths_as_player)
        player_deaths = len(kills.filter(kills["victim"] == player_name))

        if player_deaths > 5 and (total_first_deaths / player_deaths) > 0.4:
            tips.append({
                "player": player_name,
                "category": "positioning",
                "priority": 8,
                "title": "Слишком часто умираешь первым",
                "body": (
                    "Позиционируйся для трейда. Часто первая смерть = "
                    "выход в пустое пространство без поддержки."
                ),
                "metric_name": "first_death_rate",
                "current_value": round((total_first_deaths / player_deaths) * 100.0, 1),
                "target_value": 20.0,
                "evidence_json": json.dumps({
                    "first_deaths": total_first_deaths,
                    "total_deaths": player_deaths,
                })
            })

    # ------------------------------------------------------------------
    # 3. Utility Underuse — редко бросает гранаты
    # Порог: avg grenades/round < 0.5 при total_rounds > 15
    # ------------------------------------------------------------------
    try:
        if not grenades.is_empty() and total_rounds > 15 and "thrower" in grenades.columns:
            all_throwers = set(kills["attacker"].drop_nulls().to_list() +
                               kills["victim"].drop_nulls().to_list())
            for player_name in all_throwers:
                if not player_name:
                    continue
                player_nades = grenades.filter(grenades["thrower"] == player_name)
                nades_per_round = len(player_nades) / total_rounds
                if nades_per_round < 0.5:
                    tips.append({
                        "player": player_name,
                        "category": "utility",
                        "priority": 6,
                        "title": "Мало используешь гранаты",
                        "body": (
                            f"В среднем {nades_per_round:.1f} гранаты за раунд — это мало. "
                            "Smoke + flash перед входом на сайт даёт существенное преимущество. "
                            "Выучи 3-4 стандартных раскидки для любимых карт."
                        ),
                        "metric_name": "grenades_per_round",
                        "current_value": round(nades_per_round, 2),
                        "target_value": 1.2,
                        "evidence_json": json.dumps({
                            "total_grenades": len(player_nades),
                            "total_rounds": total_rounds,
                            "grenades_per_round": round(nades_per_round, 3),
                        })
                    })
    except Exception as e:
        log.warning(f"utility_underuse tip failed: {e}")

    # ------------------------------------------------------------------
    # 4. Low Trade Efficiency — умирает без трейда
    # Логика: смерть "трейдована" если тиммейт убил врага в течение
    #   320 тиков (~5 сек при 64 tick) после смерти игрока.
    # Порог: trade_rate < 30% при > 5 смертях
    # ------------------------------------------------------------------
    try:
        # Строим таблицу смертей и убийств с командами
        # Нам нужны колонки: round_id, tick, attacker, victim
        if "attacker" in kills.columns and "victim" in kills.columns:
            TRADE_WINDOW = 320  # тики

            # Для каждого игрока считаем его смерти и пытаемся найти трейд
            for player_name in kills["victim"].unique():
                if not player_name:
                    continue
                player_deaths_df = kills.filter(kills["victim"] == player_name)
                total_deaths = len(player_deaths_df)
                if total_deaths < 5:
                    continue

                traded = 0
                for death_row in player_deaths_df.iter_rows(named=True):
                    death_tick = death_row["tick"] or 0
                    death_rid = death_row["round_id"]
                    killer = death_row["attacker"]

                    # Тиммейт трейдует если в этом раунде после death_tick
                    # кто-то (не сам player_name) убивает killer
                    window_kills = kills.filter(
                        (kills["round_id"] == death_rid) &
                        (kills["attacker"] != player_name) &
                        (kills["victim"] == killer) &
                        (kills["tick"] >= death_tick) &
                        (kills["tick"] <= death_tick + TRADE_WINDOW)
                    )
                    if len(window_kills) > 0:
                        traded += 1

                trade_rate = traded / total_deaths
                if trade_rate < 0.3:
                    tips.append({
                        "player": player_name,
                        "category": "teamplay",
                        "priority": 6,
                        "title": "Умираешь без трейда",
                        "body": (
                            f"Только {trade_rate * 100:.0f}% твоих смертей трейдуются тиммейтами. "
                            "Занимай позиции рядом с союзниками — это и защита, и возможность "
                            "для тиммейтов ответить на твою смерть."
                        ),
                        "metric_name": "trade_rate",
                        "current_value": round(trade_rate * 100.0, 1),
                        "target_value": 50.0,
                        "evidence_json": json.dumps({
                            "traded_deaths": traded,
                            "total_deaths": total_deaths,
                            "trade_rate": round(trade_rate, 3),
                            "trade_window_ticks": TRADE_WINDOW,
                        })
                    })
    except Exception as e:
        log.warning(f"low_trade_efficiency tip failed: {e}")

    # ------------------------------------------------------------------
    # 5. CT Passive — мало убийств на CT при хорошем CT winrate команды
    # Логика: считаем CT-раунды (по rounds.winner и начальной стороне),
    #   kills/CT-round игрока < 0.3 при ct_winrate > 50%.
    # Порог: kills_per_ct_round < 0.3 И ct_rounds >= 10
    # ------------------------------------------------------------------
    try:
        if not rounds.is_empty() and "winner" in rounds.columns:
            ct_rounds = rounds.filter(rounds["winner"] == "CT")
            t_rounds = rounds.filter(rounds["winner"] == "T")
            ct_round_ids = set(ct_rounds["id"].to_list()) if "id" in ct_rounds.columns else set()
            total_ct = len(ct_rounds)
            total_t = len(t_rounds)
            total_played = total_ct + total_t

            if total_played > 0:
                ct_winrate = total_ct / total_played

                if ct_winrate > 0.5 and total_ct >= 10:
                    # Для каждого игрока считаем убийства в CT-раундах
                    for player_name in kills["attacker"].unique():
                        if not player_name:
                            continue
                        ct_kills = kills.filter(
                            (kills["attacker"] == player_name) &
                            (kills["round_id"].is_in(list(ct_round_ids)))
                        )
                        kills_per_ct_round = len(ct_kills) / total_ct
                        if kills_per_ct_round < 0.3:
                            tips.append({
                                "player": player_name,
                                "category": "aggression",
                                "priority": 5,
                                "title": "Пассивная игра на CT",
                                "body": (
                                    f"{kills_per_ct_round:.2f} убийств за CT-раунд — "
                                    "команда выигрывает CT-сторону, а ты остаёшься слишком пассивным. "
                                    "Попробуй агрессивные информационные пики: "
                                    "одно агрессивное действие в раунде даёт инфо и давление на T."
                                ),
                                "metric_name": "ct_kills_per_round",
                                "current_value": round(kills_per_ct_round, 3),
                                "target_value": 0.7,
                                "evidence_json": json.dumps({
                                    "ct_kills": len(ct_kills),
                                    "ct_rounds": total_ct,
                                    "ct_winrate": round(ct_winrate, 3),
                                    "kills_per_ct_round": round(kills_per_ct_round, 3),
                                })
                            })
    except Exception as e:
        log.warning(f"ct_passive tip failed: {e}")

    # ------------------------------------------------------------------
    # 6. Late Round Die — опять же первые смерти (alias: eco aggression)
    # Уточнение: игрок умирает в топ-3 первых смертей раунда,
    #   но здесь считаем rank смерти (1-я, 2-я, 3-я) — если в топ-3
    #   в > 40% раундов.
    # Порог: > 5 смертей И top3_rate > 0.4
    # ------------------------------------------------------------------
    try:
        # Ранжируем смерти внутри каждого раунда по тику
        if "tick" in kills.columns and "round_id" in kills.columns:
            kills_ranked = kills.sort("tick").with_columns(
                pl.col("tick").rank("ordinal").over("round_id").alias("death_rank_in_round")
            )

            for player_name in kills_ranked["victim"].unique():
                if not player_name:
                    continue
                player_deaths_r = kills_ranked.filter(kills_ranked["victim"] == player_name)
                total_d = len(player_deaths_r)
                if total_d < 5:
                    continue

                top3_deaths = player_deaths_r.filter(
                    player_deaths_r["death_rank_in_round"] <= 3
                )
                top3_rate = len(top3_deaths) / total_d

                # Только если это НЕ задублировано с уже существующим советом
                already_has_first_death_tip = any(
                    t["player"] == player_name and t["metric_name"] == "first_death_rate"
                    for t in tips
                )
                if top3_rate > 0.4 and not already_has_first_death_tip:
                    tips.append({
                        "player": player_name,
                        "category": "positioning",
                        "priority": 5,
                        "title": "Часто умираешь в начале раунда",
                        "body": (
                            f"В {top3_rate * 100:.0f}% раундов ты входишь в топ-3 первых смертей. "
                            "Дай информации больше времени накапливаться перед первым контактом — "
                            "patience в первые 10-15 секунд раунда спасает жизни."
                        ),
                        "metric_name": "top3_early_death_rate",
                        "current_value": round(top3_rate * 100.0, 1),
                        "target_value": 25.0,
                        "evidence_json": json.dumps({
                            "top3_deaths": len(top3_deaths),
                            "total_deaths": total_d,
                            "top3_rate": round(top3_rate, 3),
                        })
                    })
    except Exception as e:
        log.warning(f"late_round_die tip failed: {e}")

    # Save to database
    async with get_connection() as conn:
        await save_coach_tips(conn, match_id, tips)

    log.info(f"Coach tips complete: {len(tips)} tips for match {match_id}")
    return tips


def compute_aim_stats(match_id: int) -> dict[str, dict]:
    """Compute accuracy, headshot_accuracy, avg_ttk_ms, and first_bullet_accuracy per player."""
    log.info(f"Computing aim stats for match {match_id}")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        tick_rate = 64
        non_shootable = {
            'weapon_knife', 'weapon_knife_t', 'weapon_bayonet', 'weapon_hegrenade', 
            'weapon_flashbang', 'weapon_smokegrenade', 'weapon_molotov', 'weapon_incgrenade', 
            'weapon_decoy', 'weapon_taser', 'weapon_c4', 'weapon_bumpmine', 'weapon_breachcharge'
        }
        cur = conn.execute("SELECT round_id, tick, attacker, weapon FROM weapon_fires WHERE match_id = ?", (match_id,))
        fires_list = [dict(r) for r in cur.fetchall()]
        
        # Load damages (hits)
        non_shootable_dmg = {
            'hegrenade', 'flashbang', 'smokegrenade', 'molotov', 'incgrenade', 'decoy', 
            'knife', 'taser', 'inferno'
        }
        cur = conn.execute("SELECT round_id, tick, attacker, victim, weapon, hp_damage, hitgroup FROM damages WHERE match_id = ?", (match_id,))
        damages_list = [dict(r) for r in cur.fetchall()]
        
        # Load kills
        cur = conn.execute("SELECT round_id, tick, attacker, victim FROM kills WHERE match_id = ?", (match_id,))
        kills_list = [dict(r) for r in cur.fetchall()]
        
        # We need a list of players
        players = set()
        for f in fires_list:
            if f["attacker"]: players.add(f["attacker"])
        for d in damages_list:
            if d["attacker"]: players.add(d["attacker"])
            if d["victim"]: players.add(d["victim"])
        for k in kills_list:
            if k["attacker"]: players.add(k["attacker"])
            if k["victim"]: players.add(k["victim"])
            
        aim_stats = {}
        for player in players:
            aim_stats[player] = {
                "accuracy": 0.0,
                "headshot_accuracy": 0.0,
                "avg_ttk_ms": 0.0,
                "first_bullet_accuracy": 0.0
            }
            
        # 1. Compute ACCURACY and HEADSHOT ACCURACY
        for player in players:
            player_shots = [
                f for f in fires_list 
                if f["attacker"] == player and f["weapon"] and f["weapon"].lower() not in non_shootable
            ]
            shots_count = len(player_shots)
            
            player_hits = [
                d for d in damages_list 
                if d["attacker"] == player and d["weapon"] and d["weapon"].lower() not in non_shootable_dmg
            ]
            hits_count = len(player_hits)
            
            accuracy = hits_count / shots_count if shots_count > 0 else 0.0
            headshot_hits = [d for d in player_hits if d["hitgroup"] == "head"]
            hs_accuracy = len(headshot_hits) / hits_count if hits_count > 0 else 0.0
            
            aim_stats[player]["accuracy"] = accuracy
            aim_stats[player]["headshot_accuracy"] = hs_accuracy
            
        # 2. Compute TTK (Time to Kill)
        for player in players:
            player_kills = [k for k in kills_list if k["attacker"] == player]
            ttk_values = []
            
            for kill in player_kills:
                victim = kill["victim"]
                round_id = kill["round_id"]
                kill_tick = kill["tick"]
                

                duel_damages = [
                    d for d in damages_list
                    if d["attacker"] == player 
                    and d["victim"] == victim 
                    and d["round_id"] == round_id
                    and kill_tick - 192 <= d["tick"] <= kill_tick
                    and d["weapon"] and d["weapon"].lower() not in non_shootable_dmg
                ]
                
                if duel_damages:
                    first_damage_tick = min(d["tick"] for d in duel_damages)
                    delta_ticks = kill_tick - first_damage_tick
                    ttk_ms = (delta_ticks / tick_rate) * 1000.0
                    ttk_values.append(ttk_ms)
                    
            avg_ttk = sum(ttk_values) / len(ttk_values) if ttk_values else 0.0
            aim_stats[player]["avg_ttk_ms"] = avg_ttk
            
        # 3. Compute FIRST BULLET ACCURACY
        for player in players:
            player_shots = [
                f for f in fires_list 
                if f["attacker"] == player and f["weapon"] and f["weapon"].lower() not in non_shootable
            ]
            player_shots.sort(key=lambda x: x["tick"])
            
            burst_starts = []
            last_tick = -9999
            for shot in player_shots:
                if shot["tick"] - last_tick > 45:
                    burst_starts.append(shot["tick"])
                last_tick = shot["tick"]
                
            player_hits_all = [
                d for d in damages_list 
                if d["attacker"] == player and d["weapon"] and d["weapon"].lower() not in non_shootable_dmg
            ]
            hit_ticks = {d["tick"] for d in player_hits_all}
            
            successful_first_bullets = 0
            for start_tick in burst_starts:
                if any(t in hit_ticks for t in (start_tick, start_tick + 1, start_tick + 2)):
                    successful_first_bullets += 1
                    
            fba = successful_first_bullets / len(burst_starts) if burst_starts else 0.0
            aim_stats[player]["first_bullet_accuracy"] = fba
            
        return aim_stats
    finally:
        conn.close()
