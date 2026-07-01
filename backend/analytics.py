import json
import logging
import polars as pl
from backend.database import load_kills, load_ticks, DB_PATH, save_anticheat_flags, save_coach_tips, get_connection

log = logging.getLogger("backend.analytics")

async def run_anticheat_analysis(match_id: int):
    """Run anticheat heuristic analysis and store flags in the DB."""
    log.info(f"Running anticheat analysis for match {match_id}")
    try:
        kills = load_kills(DB_PATH, match_id)
        ticks = load_ticks(DB_PATH, match_id)
    except Exception as e:
        log.error(f"Failed to load data for anticheat: {e}")
        return []

    if kills.is_empty() or ticks.is_empty():
        log.warning("No kills or ticks found for anticheat analysis")
        return []

    flags = []

    # 1. Snap Aim
    # Group by attacker and look for huge yaw changes near kill
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

        for kill_tick in player_kills["tick"].to_list():
            # window of 10 ticks before the kill
            window = player_ticks.filter((player_ticks["tick"] <= kill_tick) & (player_ticks["tick"] > kill_tick - 10))
            if len(window) < 2:
                continue

            yaw_diffs = window["yaw"].diff().fill_null(0).abs()
            max_yaw_change = yaw_diffs.max()

            if max_yaw_change is not None and max_yaw_change > 45.0:
                snap_count += 1

        if snap_count > 0:
            severity = min(snap_count / total_kills * 5.0, 1.0)
            if severity > 0.3:
                flags.append({
                    "player": player_name,
                    "heuristic": "snap_aim",
                    "severity": severity,
                    "evidence_count": snap_count,
                    "details_json": json.dumps({"max_yaw_change_threshold": 45.0, "total_kills": total_kills})
                })

    # 2. Headshot Ratio Anomaly
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
                "details_json": json.dumps({"hs_ratio": hs_ratio})
            })

    # Save to database
    async with await get_connection() as conn:
        await save_anticheat_flags(conn, match_id, flags)

    return flags


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

    # 1. Low HS percentage (aim)
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
                    "body": "Тренируй crosshair placement. Aim Botz с фокусом на хедшоты, 15 минут перед игрой — заметный эффект за неделю.",
                    "metric_name": "hs_pct",
                    "current_value": hs_pct * 100.0,
                    "target_value": 40.0,
                    "evidence_json": json.dumps({"kills": total_kills, "hs_pct": hs_pct})
                })

    # 2. First death / Too aggressive
    for player_name in kills["victim"].unique():
        if not player_name:
            continue

        # Find the first kill of each round
        first_kills = kills.group_by("round_id").first()
        if first_kills.is_empty():
            continue

        first_deaths_as_player = first_kills.filter(first_kills["victim"] == player_name)
        total_first_deaths = len(first_deaths_as_player)

        # Total rounds player died
        player_deaths = len(kills.filter(kills["victim"] == player_name))

        if player_deaths > 5 and (total_first_deaths / player_deaths) > 0.4:
            tips.append({
                "player": player_name,
                "category": "positioning",
                "priority": 8,
                "title": "Слишком часто умираешь первым",
                "body": "Позиционируйся для трейда. Часто первая смерть = выход в пустое пространство без поддержки.",
                "metric_name": "first_death_rate",
                "current_value": (total_first_deaths / player_deaths) * 100.0,
                "target_value": 20.0,
                "evidence_json": json.dumps({"first_deaths": total_first_deaths, "total_deaths": player_deaths})
            })

    # Save to database
    async with await get_connection() as conn:
        await save_coach_tips(conn, match_id, tips)

    return tips
