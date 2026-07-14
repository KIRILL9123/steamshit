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


def recompute_opening_stats(match_id: int, db_path: str = DB_PATH) -> dict[str, dict]:
    """Recompute opening duels and dependent ratings from persisted match data."""
    from backend.parser import calculate_hltv_rating_v2

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        stats_rows = conn.execute(
            "SELECT * FROM player_match_stats WHERE match_id = ?",
            (match_id,),
        ).fetchall()
        players = {row["player"]: row["team"] for row in stats_rows}
        total_rounds = conn.execute(
            "SELECT COUNT(*) FROM rounds WHERE match_id = ?",
            (match_id,),
        ).fetchone()[0]

        opening_by_round = {}
        kill_rows = conn.execute(
            "SELECT r.round_num, k.tick, k.id, k.attacker, k.victim "
            "FROM kills k JOIN rounds r ON r.id = k.round_id "
            "WHERE k.match_id = ? ORDER BY r.round_num, k.tick, k.id",
            (match_id,),
        ).fetchall()
        for kill in kill_rows:
            round_num = kill["round_num"]
            if round_num in opening_by_round:
                continue
            attacker = kill["attacker"]
            victim = kill["victim"]
            if attacker not in players or victim not in players or attacker == victim:
                continue
            if players[attacker] and players[victim] and players[attacker] == players[victim]:
                continue
            opening_by_round[round_num] = (attacker, victim)

        entry_kills = {player: 0 for player in players}
        entry_deaths = {player: 0 for player in players}
        for attacker, victim in opening_by_round.values():
            entry_kills[attacker] += 1
            entry_deaths[victim] += 1

        changes = {}
        for row in stats_rows:
            player = row["player"]
            stats = dict(row)
            old_rating = float(stats["rating"] or 0.0)
            stats["entry_kills"] = entry_kills[player]
            stats["entry_deaths"] = entry_deaths[player]
            stats["first_bloods"] = entry_kills[player]
            new_rating = calculate_hltv_rating_v2(stats, [], total_rounds)
            conn.execute(
                "UPDATE player_match_stats "
                "SET entry_kills = ?, entry_deaths = ?, first_bloods = ?, rating = ? "
                "WHERE match_id = ? AND player = ?",
                (
                    stats["entry_kills"],
                    stats["entry_deaths"],
                    stats["first_bloods"],
                    new_rating,
                    match_id,
                    player,
                ),
            )
            changes[player] = {
                "entry_kills": stats["entry_kills"],
                "entry_deaths": stats["entry_deaths"],
                "old_rating": old_rating,
                "new_rating": new_rating,
            }

        conn.commit()
        return changes
    finally:
        conn.close()


def recompute_cheap_stats(match_id: int, db_path: str = DB_PATH) -> dict[str, dict]:
    """Backfill KPR, longest kill distance, and max killstreak from persisted events."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        players = [
            row["player"]
            for row in conn.execute(
                "SELECT player FROM player_match_stats WHERE match_id = ?",
                (match_id,),
            )
        ]
        total_rounds = conn.execute(
            "SELECT COUNT(*) FROM rounds WHERE match_id = ?",
            (match_id,),
        ).fetchone()[0]
        aggregates = {
            row["attacker"]: row
            for row in conn.execute(
                "SELECT attacker, COUNT(*) AS kills, "
                "COALESCE(MAX(CASE WHEN distance > 0 THEN distance END), 0) AS longest_kill_distance "
                "FROM kills WHERE match_id = ? GROUP BY attacker",
                (match_id,),
            )
        }

        current_streaks = {player: 0 for player in players}
        max_streaks = {player: 0 for player in players}
        for event in conn.execute(
            "SELECT attacker, victim FROM kills WHERE match_id = ? ORDER BY tick, id",
            (match_id,),
        ):
            attacker = event["attacker"]
            victim = event["victim"]
            if victim in current_streaks:
                current_streaks[victim] = 0
            if attacker in current_streaks and attacker != victim:
                current_streaks[attacker] += 1
                max_streaks[attacker] = max(max_streaks[attacker], current_streaks[attacker])

        result = {}
        for player in players:
            aggregate = aggregates.get(player)
            kills = int(aggregate["kills"]) if aggregate else 0
            longest = float(aggregate["longest_kill_distance"]) if aggregate else 0.0
            kpr = kills / total_rounds if total_rounds else 0.0
            conn.execute(
                "UPDATE player_match_stats "
                "SET kpr = ?, longest_kill_distance = ?, max_killstreak = ? "
                "WHERE match_id = ? AND player = ?",
                (kpr, longest, max_streaks[player], match_id, player),
            )
            result[player] = {
                "kpr": kpr,
                "longest_kill_distance": longest,
                "max_killstreak": max_streaks[player],
            }

        conn.commit()
        return result
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
    # Порог: trade_rate < 30% при > 5 смертях
    # ------------------------------------------------------------------
    try:
        trade_stats = compute_trade_stats(match_id)
        for player_name, data in trade_stats.items():
            total_deaths = data["total_deaths"]
            if total_deaths < 5:
                continue
            trade_rate = data["trade_rate"]
            if trade_rate < 0.3:
                tips.append({
                    "player": player_name,
                    "category": "trade",
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
                        "traded_deaths": data["traded_deaths"],
                        "total_deaths": total_deaths,
                        "trade_rate": round(trade_rate, 3),
                        "trade_window_ticks": 320,
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

    # ------------------------------------------------------------------
    # 7. Teamflash Habit — игрок систематически слепит тиммейтов.
    # Порог: teammates_blinded >= 3 AND ratio > 0.3
    # ------------------------------------------------------------------
    try:
        async with get_connection() as conn:
            async with conn.execute(
                "SELECT attacker, is_teammate FROM flash_events WHERE match_id = ?",
                (match_id,)
            ) as cursor:
                flash_rows = await cursor.fetchall()
        
        player_flashes = {}
        for row in flash_rows:
            att = row["attacker"]
            is_team = bool(row["is_teammate"])
            if not att:
                continue
            if att not in player_flashes:
                player_flashes[att] = {"teammate": 0, "enemy": 0}
            if is_team:
                player_flashes[att]["teammate"] += 1
            else:
                player_flashes[att]["enemy"] += 1

        for player_name, f_data in player_flashes.items():
            team_blind = f_data["teammate"]
            enemy_blind = f_data["enemy"]
            total_blind = team_blind + enemy_blind
            if team_blind >= 3 and total_blind > 0 and (team_blind / total_blind) > 0.3:
                ratio = team_blind / total_blind
                tips.append({
                    "player": player_name,
                    "category": "utility",
                    "priority": 7,
                    "title": "Опасные световые (Teamflash Habit)",
                    "body": (
                        f"Ты ослепил {team_blind} тиммейтов в этом матче ({ratio * 100:.0f}% от всех твоих флешек). "
                        "Старайся предупреждать команду перед броском флешки или используй моментальные гранаты (pop-flashes) за спину тиммейтам."
                    ),
                    "metric_name": "teamflash_ratio",
                    "current_value": round(ratio * 100.0, 1),
                    "target_value": 15.0,
                    "evidence_json": json.dumps({
                         "teammates_blinded": team_blind,
                         "enemies_blinded": enemy_blind,
                         "teamflash_ratio": round(ratio, 3)
                    })
                })
    except Exception as e:
        log.warning(f"teamflash_habit tip failed: {e}")

    # ------------------------------------------------------------------
    # 8. Died Holding Utility (SKIPPED):
    # Inventory data on player death is not parsed/stored in our database. 
    # Requiring a full demoparser2 run on the fly would be extremely slow 
    # and depend on having the raw .dem file locally.
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # 9. Lone Wolf (Traded Poorly) — игрок умирает вдали от союзников
    # Порог: trade_rate < 0.5 * avg_rate по матчу, при deaths >= 8
    # ------------------------------------------------------------------
    try:
        trade_stats = compute_trade_stats(match_id)
        rates = [d["trade_rate"] for d in trade_stats.values() if d["total_deaths"] > 0]
        if rates:
            avg_rate = sum(rates) / len(rates)
            for player_name, data in trade_stats.items():
                deaths_count = data["total_deaths"]
                trade_rate = data["trade_rate"]
                if deaths_count >= 8 and trade_rate < 0.5 * avg_rate:
                    tips.append({
                        "player": player_name,
                        "category": "trade",
                        "priority": 6,
                        "title": "Игра в соло (Lone Wolf)",
                        "body": (
                            f"Твой процент разменов ({trade_rate * 100:.0f}%) значительно ниже среднего по матчу ({avg_rate * 100:.0f}%). "
                            "Постарайся играть ближе к команде, чтобы твои смерти приносили пользу в виде ответных убийств."
                        ),
                        "metric_name": "trade_rate",
                        "current_value": round(trade_rate * 100.0, 1),
                        "target_value": round(avg_rate * 100.0, 1),
                        "evidence_json": json.dumps({
                            "traded_deaths": data["traded_deaths"],
                            "total_deaths": deaths_count,
                            "trade_rate": round(trade_rate, 3),
                            "avg_match_trade_rate": round(avg_rate, 3)
                        })
                    })
    except Exception as e:
        log.warning(f"lone_wolf tip failed: {e}")

    # ------------------------------------------------------------------
    # 10. Missed Multikill Opportunity — урон по 2+ противникам без киллов
    # Порог: 2+ missed rounds в матче
    # ------------------------------------------------------------------
    try:
        async with get_connection() as conn:
            async with conn.execute(
                "SELECT round_id, attacker, victim, hp_damage FROM damages WHERE match_id = ?",
                (match_id,)
            ) as cursor:
                damage_rows = await cursor.fetchall()
            async with conn.execute(
                "SELECT round_id, attacker FROM kills WHERE match_id = ?",
                (match_id,)
            ) as cursor:
                kill_rows = await cursor.fetchall()

        round_attacker_kills = {}
        for row in kill_rows:
            r_id = row["round_id"]
            att = row["attacker"]
            if not att:
                continue
            if (r_id, att) not in round_attacker_kills:
                round_attacker_kills[(r_id, att)] = 0
            round_attacker_kills[(r_id, att)] += 1

        round_attacker_victims = {}
        for row in damage_rows:
            r_id = row["round_id"]
            att = row["attacker"]
            vic = row["victim"]
            dmg = row["hp_damage"]
            if not att or not vic or dmg <= 0:
                continue
            if (r_id, att) not in round_attacker_victims:
                round_attacker_victims[(r_id, att)] = set()
            round_attacker_victims[(r_id, att)].add(vic)

        missed_rounds_count = {}
        for (r_id, att), victims in round_attacker_victims.items():
            if len(victims) >= 2:
                kills_in_round = round_attacker_kills.get((r_id, att), 0)
                if kills_in_round == 0:
                    if att not in missed_rounds_count:
                         missed_rounds_count[att] = 0
                    missed_rounds_count[att] += 1

        for player_name, missed_count in missed_rounds_count.items():
            if missed_count >= 2:
                tips.append({
                    "player": player_name,
                    "category": "aim",
                    "priority": 6,
                    "title": "Упущенные мультикиллы",
                    "body": (
                        f"В {missed_count} раундах ты наносил урон 2+ противникам, но не смог совершить ни одного убийства. "
                        "Это указывает на проблемы со спреем или переводом прицела. Работай над target switching."
                    ),
                    "metric_name": "missed_multikill_rounds",
                    "current_value": missed_count,
                    "target_value": 0,
                    "evidence_json": json.dumps({
                        "missed_multikill_rounds": missed_count
                    })
                })
    except Exception as e:
        log.warning(f"missed_multikill tip failed: {e}")

    # ------------------------------------------------------------------
    # 11. Entry Fragger No Support — умер первым без размена
    # Порог: entry_deaths >= 3 AND trade_rate < 0.2
    # ------------------------------------------------------------------
    try:
        async with get_connection() as conn:
            async with conn.execute(
                "SELECT player, entry_deaths, trade_rate FROM player_match_stats WHERE match_id = ?",
                (match_id,)
            ) as cursor:
                stat_rows = await cursor.fetchall()
                 
        for row in stat_rows:
            player_name = row["player"]
            entry_deaths = row["entry_deaths"] or 0
            trade_rate = row["trade_rate"] or 0.0
            if entry_deaths >= 3 and trade_rate < 0.2:
                tips.append({
                    "player": player_name,
                    "category": "trade",
                    "priority": 7,
                    "title": "Вход без поддержки (Entry No Support)",
                    "body": (
                        f"Ты умер первым в {entry_deaths} раундах на входе, но твой процент разменов составляет всего {trade_rate * 100:.0f}%. "
                        "Либо координируй свои выходы с тиммейтами, либо проси их идти вторым темпом для размена."
                    ),
                    "metric_name": "entry_no_support_rate",
                    "current_value": round(trade_rate * 100.0, 1),
                    "target_value": 40.0,
                    "evidence_json": json.dumps({
                        "entry_deaths": entry_deaths,
                        "trade_rate": round(trade_rate, 3)
                    })
                })
    except Exception as e:
        log.warning(f"entry_fragger_no_support tip failed: {e}")

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


def compute_utility_stats(match_id: int) -> dict[str, dict]:
    """Compute utility metrics (damage dealt/taken, smokes thrown, flash durations) per player."""
    log.info(f"Computing utility stats for match {match_id}")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        # 1. Utility Damage Dealt / Taken
        cur = conn.execute(
            "SELECT attacker, SUM(hp_damage) as dealt FROM damages "
            "WHERE match_id = ? AND weapon IN ('hegrenade', 'inferno', 'molotov') GROUP BY attacker",
            (match_id,)
        )
        dealt_map = {r["attacker"]: r["dealt"] for r in cur.fetchall() if r["attacker"]}
        
        cur = conn.execute(
            "SELECT victim, SUM(hp_damage) as taken FROM damages "
            "WHERE match_id = ? AND weapon IN ('hegrenade', 'inferno', 'molotov') GROUP BY victim",
            (match_id,)
        )
        taken_map = {r["victim"]: r["taken"] for r in cur.fetchall() if r["victim"]}
        
        # 2. Smokes thrown
        cur = conn.execute(
            "SELECT thrower, COUNT(*) as smokes FROM grenades "
            "WHERE match_id = ? AND nade_type = 'smoke' GROUP BY thrower",
            (match_id,)
        )
        smokes_map = {r["thrower"]: r["smokes"] for r in cur.fetchall() if r["thrower"]}
        
        # 2.5 Flashbangs thrown
        cur = conn.execute(
            "SELECT thrower, COUNT(*) as flashes FROM grenades "
            "WHERE match_id = ? AND nade_type = 'flash' GROUP BY thrower",
            (match_id,)
        )
        flashes_map = {r["thrower"]: r["flashes"] for r in cur.fetchall() if r["thrower"]}
        
        # 3. Flash durations and counts from flash_events
        cur = conn.execute(
            "SELECT attacker, "
            "SUM(CASE WHEN is_teammate = 0 THEN duration_seconds ELSE 0 END) as enemy_dur_sum, "
            "SUM(CASE WHEN is_teammate = 1 THEN duration_seconds ELSE 0 END) as teammate_dur_sum, "
            "SUM(CASE WHEN is_teammate = 0 THEN 1 ELSE 0 END) as enemy_flashes, "
            "SUM(CASE WHEN is_teammate = 1 THEN 1 ELSE 0 END) as teammate_flashes "
            "FROM flash_events WHERE match_id = ? GROUP BY attacker",
            (match_id,)
        )
        flash_map = {}
        for r in cur.fetchall():
            if not r["attacker"]: continue
            attacker = r["attacker"]
            enemy_flashes = r["enemy_flashes"] or 0
            teammate_flashes = r["teammate_flashes"] or 0
            enemy_dur = (r["enemy_dur_sum"] / enemy_flashes) if enemy_flashes > 0 else 0.0
            teammate_dur = (r["teammate_dur_sum"] / teammate_flashes) if teammate_flashes > 0 else 0.0
            flash_map[attacker] = {
                "enemy_dur": enemy_dur,
                "teammate_dur": teammate_dur,
                "enemy_flashes": enemy_flashes,
                "teammate_flashes": teammate_flashes
            }
            
        # Get all players
        cur = conn.execute("SELECT player FROM player_match_stats WHERE match_id = ?", (match_id,))
        players = [r["player"] for r in cur.fetchall()]
        
        utility_stats = {}
        for p in players:
            f = flash_map.get(p, {"enemy_dur": 0.0, "teammate_dur": 0.0, "enemy_flashes": 0, "teammate_flashes": 0})
            utility_stats[p] = {
                "utility_damage_dealt": dealt_map.get(p, 0.0),
                "utility_damage_taken": taken_map.get(p, 0.0),
                "smokes_thrown": smokes_map.get(p, 0),
                "avg_enemy_flash_duration": f["enemy_dur"],
                "avg_teammate_flash_duration": f["teammate_dur"],
                "enemies_blinded": f["enemy_flashes"],
                "teammates_blinded": f["teammate_flashes"],
                "flashbangs_thrown": flashes_map.get(p, 0)
            }
            
        return utility_stats
    finally:
        conn.close()


def compute_trade_stats(match_id: int) -> dict[str, dict]:
    """Compute trade metrics (traded_deaths, trade_kills, trade_rate) per player."""
    log.info(f"Computing trade stats for match {match_id}")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        # Load all kills in the match
        cur = conn.execute(
            "SELECT round_id, tick, attacker, victim FROM kills WHERE match_id = ? ORDER BY tick ASC",
            (match_id,)
        )
        kills = [dict(r) for r in cur.fetchall()]
        
        # Load total deaths and teams per player from player_match_stats
        cur = conn.execute(
            "SELECT player, deaths, team FROM player_match_stats WHERE match_id = ?",
            (match_id,)
        )
        rows = cur.fetchall()
        player_deaths = {r["player"]: r["deaths"] for r in rows}
        player_teams = {r["player"]: r["team"].upper() for r in rows if r["player"] and r["team"]}
        
        trade_stats = {}
        for p, d in player_deaths.items():
            trade_stats[p] = {
                "traded_deaths": 0,
                "trade_kills": 0,
                "trade_rate": 0.0,
                "total_deaths": d
            }
            
        TRADE_WINDOW = 320
        
        for i, death in enumerate(kills):
            victim = death["victim"]
            killer = death["attacker"]
            d_tick = death["tick"]
            r_id = death["round_id"]
            
            if not victim or not killer:
                continue
                
            for j in range(i + 1, len(kills)):
                tr = kills[j]
                if tr["round_id"] != r_id or tr["tick"] > d_tick + TRADE_WINDOW:
                    break
                if tr["victim"] == killer and tr["attacker"] != victim:
                    # Check if trade killer and victim are on the same team
                    v_team = player_teams.get(victim)
                    tr_team = player_teams.get(tr["attacker"])
                    if v_team and tr_team and v_team == tr_team:
                        trade_stats[victim]["traded_deaths"] += 1
                        tr_attacker = tr["attacker"]
                        if tr_attacker in trade_stats:
                            trade_stats[tr_attacker]["trade_kills"] += 1
                        break
                    
        for p, stats in trade_stats.items():
            deaths_count = stats["total_deaths"]
            stats["trade_rate"] = stats["traded_deaths"] / deaths_count if deaths_count > 0 else 0.0
            
        return trade_stats
    finally:
        conn.close()


def compute_clutch_stats(match_id: int):
    """Detect and record clutch situations (1vX) and update player match stats."""
    log.info(f"Computing clutch stats for match {match_id}")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        # 1. Reset existing clutch events for this match
        conn.execute("DELETE FROM clutch_events WHERE match_id = ?", (match_id,))
        conn.execute(
            "UPDATE player_match_stats SET clutches_won = 0, clutches_total = 0 WHERE match_id = ?",
            (match_id,)
        )
        conn.commit()

        # 2. Get rounds in match
        cur = conn.execute(
            "SELECT id, round_num, winner FROM rounds WHERE match_id = ? ORDER BY round_num ASC",
            (match_id,)
        )
        rounds = [dict(r) for r in cur.fetchall()]
        if not rounds:
            return

        # Get player starting teams
        cur = conn.execute(
            "SELECT player, team FROM player_match_stats WHERE match_id = ?",
            (match_id,)
        )
        player_teams = {r["player"]: r["team"].upper() for r in cur.fetchall() if r["player"] and r["team"]}

        # Halftime side swap detection
        max_round = max(r["round_num"] for r in rounds)
        halftime = 15 if max_round > 24 else 12

        for r in rounds:
            r_id = r["id"]
            r_num = r["round_num"]
            winner = r["winner"] # 'CT' or 'T'
            if not winner:
                continue

            # Determine team sides in this round
            if r_num <= halftime:
                is_second_half = False
            elif r_num <= halftime * 2:
                is_second_half = True
            else:
                ot_round = r_num - halftime * 2 - 1
                is_second_half = (ot_round // 3) % 2 == 1

            # Build sets of CT and T players alive at start of round
            alive_ct = set()
            alive_t = set()
            for p, team in player_teams.items():
                is_ct = (team == 'CT') if not is_second_half else (team == 'T')
                if is_ct:
                    alive_ct.add(p)
                else:
                    alive_t.add(p)

            # Enforce 5v5 start check (only count if they started with > 1 player alive)
            had_more_than_one_ct = len(alive_ct) > 1
            had_more_than_one_t = len(alive_t) > 1

            # Load kills in this round ordered by tick
            cur = conn.execute(
                "SELECT tick, victim FROM kills WHERE round_id = ? ORDER BY tick ASC",
                (r_id,)
            )
            kills = [dict(k) for k in cur.fetchall()]

            ct_clutch = None # Will store dict if triggered
            t_clutch = None

            for k in kills:
                victim = k["victim"]
                alive_ct.discard(victim)
                alive_t.discard(victim)

                # Check CT clutch trigger
                if len(alive_ct) == 1 and len(alive_t) >= 1 and ct_clutch is None and had_more_than_one_ct:
                    ct_clutch = {
                        "player": list(alive_ct)[0],
                        "opponents": len(alive_t)
                    }
                # Check T clutch trigger
                if len(alive_t) == 1 and len(alive_ct) >= 1 and t_clutch is None and had_more_than_one_t:
                    t_clutch = {
                        "player": list(alive_t)[0],
                        "opponents": len(alive_ct)
                    }

            # Record clutches triggered in this round
            # Outcome: won if their side won
            if ct_clutch:
                won = (winner == 'CT')
                conn.execute(
                    "INSERT INTO clutch_events (match_id, round_id, player, team, opponents_count, won) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (match_id, r_id, ct_clutch["player"], "CT", ct_clutch["opponents"], won)
                )
                conn.execute(
                    "UPDATE player_match_stats SET clutches_total = clutches_total + 1, "
                    "clutches_won = clutches_won + ? WHERE match_id = ? AND player = ?",
                    (1 if won else 0, match_id, ct_clutch["player"])
                )

            if t_clutch:
                won = (winner == 'T')
                conn.execute(
                    "INSERT INTO clutch_events (match_id, round_id, player, team, opponents_count, won) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (match_id, r_id, t_clutch["player"], "T", t_clutch["opponents"], won)
                )
                conn.execute(
                    "UPDATE player_match_stats SET clutches_total = clutches_total + 1, "
                    "clutches_won = clutches_won + ? WHERE match_id = ? AND player = ?",
                    (1 if won else 0, match_id, t_clutch["player"])
                )

        conn.commit()
    finally:
        conn.close()
