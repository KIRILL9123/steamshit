"""Advanced anticheat heuristics via Pandas/Polars."""

import json

from cs2_sidecar.db import load_kills, load_ticks


def run_heuristic(params: dict) -> list[dict]:
    match_id = params.get("match_id")
    db_path = params.get("db_path")
    if not match_id or not db_path:
        return []

    try:
        kills = load_kills(db_path, match_id)
        ticks = load_ticks(db_path, match_id)
    except Exception:
        return []

    if kills.is_empty() or ticks.is_empty():
        return []

    flags = []

    # 1. Snap Aim
    # Group by attacker and look for huge yaw changes near kill
    for player_name in kills["attacker"].unique():
        player_kills = kills.filter(kills["attacker"] == player_name)
        if player_kills.is_empty():
            continue

        player_ticks = ticks.filter(ticks["player"] == player_name)
        if player_ticks.is_empty():
            continue

        snap_count = 0
        total_kills = len(player_kills)

        for kill_tick in player_kills["tick"].to_list():
            # window of 5 ticks before the kill
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

    # 2. Reaction Time (Simplified for now without full visibility mesh)
    # We will flag it if there's an unusually high headshot ratio anomaly as well.
    for player_name in kills["attacker"].unique():
        player_kills = kills.filter(kills["attacker"] == player_name)
        hs_ratio = player_kills["headshot"].sum() / max(len(player_kills), 1)
        if len(player_kills) > 10 and hs_ratio > 0.8:
            flags.append({
                "player": player_name,
                "heuristic": "headshot_ratio_anomaly",
                "severity": min((hs_ratio - 0.8) * 5.0, 1.0),
                "evidence_count": player_kills["headshot"].sum(),
                "details_json": json.dumps({"hs_ratio": hs_ratio})
            })

    return flags
