"""Advanced coaching rules via Pandas/Polars."""

import json

from cs2_sidecar.db import load_kills


def generate_tips(params: dict) -> list[dict]:
    match_id = params.get("match_id")
    db_path = params.get("db_path")
    if not match_id or not db_path:
        return []

    try:
        kills = load_kills(db_path, match_id)
    except Exception:
        return []

    if kills.is_empty():
        return []

    tips = []

    # 1. Low HS percentage (aim)
    for player_name in kills["attacker"].unique():
        if player_name is None:
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

    # 2. Pos first death / Too aggressive
    # Get all deaths for each player
    for player_name in kills["victim"].unique():
        if player_name is None:
            continue

        # find the first kill of each round
        first_kills = kills.group_by("round_id").first()
        if first_kills.is_empty():
            continue

        first_deaths_as_player = first_kills.filter(first_kills["victim"] == player_name)
        total_first_deaths = len(first_deaths_as_player)

        # total rounds player died
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

    return tips
