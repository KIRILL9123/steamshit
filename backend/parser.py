import os
import math
import hashlib
import datetime
import logging
import polars as pl
from demoparser2 import DemoParser

log = logging.getLogger("backend.parser")

# Hitgroup mapping
HITGROUP_MAP = {
    0: "generic",
    1: "head",
    2: "chest",
    3: "stomach",
    4: "left arm",
    5: "right arm",
    6: "left leg",
    7: "right leg",
    8: "neck",
    10: "gear",
}

# Round end reasons mapping
ROUND_END_REASON_MAP = {
    0: "still in progress",
    1: "target bombed",
    2: "vip escaped",
    3: "vip killed",
    4: "t escaped",
    5: "ct stopped escape",
    6: "t stopped",
    7: "bomb defused",
    8: "t eliminated",
    9: "ct eliminated",
    10: "draw",
    11: "hostages rescued",
    12: "target saved",
    13: "hostages not rescued",
    14: "t not escaped",
    15: "vip not escaped",
    16: "game start",
    17: "t surrender",
    18: "ct surrender",
    19: "t planted",
    20: "ct reached hostage",
}

# Team mapping
TEAM_MAP = {
    0: "Unassigned",
    1: "Spectator",
    2: "T",
    3: "CT"
}

def get_file_hash(path: str) -> str:
    """Compute SHA-256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(8192):
            sha256.update(chunk)
    return sha256.hexdigest()

def parse_demo(demo_path: str, include_ticks: bool = False) -> dict:
    """Parse a CS2 demo file and return all structured data."""
    if not os.path.exists(demo_path):
        raise FileNotFoundError(f"Demo file not found: {demo_path}")

    log.info(f"Parsing demo file: {demo_path}")
    parser = DemoParser(demo_path)

    # 1. Header
    raw_header = parser.parse_header()
    map_name = raw_header.get("map_name", "unknown")
    server_name = raw_header.get("server_name")
    client_name = raw_header.get("client_name")
    demo_version_name = raw_header.get("demo_version_name")

    sn = (server_name or "").lower()
    cn = (client_name or "").lower()
    if "faceit" in sn or "faceit" in cn:
        demo_type = "faceit"
    elif "hltv" in sn or "hltv" in cn:
        demo_type = "hltv"
    elif "valve" in sn or "valve" in cn or demo_version_name:
        demo_type = "valve"
    else:
        demo_type = "unknown"

    # Match date from file mtime
    try:
        mtime = os.path.getmtime(demo_path)
        match_date = datetime.datetime.fromtimestamp(mtime, tz=datetime.timezone.utc).isoformat()
    except Exception:
        match_date = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # 2. Events & DataFrames
    # Get all available events
    avail_events = parser.list_game_events()

    # Rounds
    round_start = parser.parse_event("round_start") if "round_start" in avail_events else pl.DataFrame()
    round_end = parser.parse_event("round_end") if "round_end" in avail_events else pl.DataFrame()
    round_freeze_end = parser.parse_event("round_freeze_end") if "round_freeze_end" in avail_events else pl.DataFrame()
    round_officially_ended = parser.parse_event("round_officially_ended") if "round_officially_ended" in avail_events else pl.DataFrame()

    # Combine round boundaries
    rounds_list = []
    if not round_start.is_empty() and not round_end.is_empty():
        # Build round structures similar to awpy's rounds.py
        starts = round_start.select(["tick"]).with_columns(event=pl.lit("start"))
        ends = round_end.select(["tick"]).with_columns(event=pl.lit("end"))
        freezes = round_freeze_end.select(["tick"]).with_columns(event=pl.lit("freeze_end")) if not round_freeze_end.is_empty() else pl.DataFrame()
        officials = round_officially_ended.select(["tick"]).with_columns(event=pl.lit("official_end")) if not round_officially_ended.is_empty() else pl.DataFrame()

        dfs_to_concat = [starts, ends]
        if not freezes.is_empty():
            dfs_to_concat.append(freezes)
        if not officials.is_empty():
            dfs_to_concat.append(officials)

        rounds_df = pl.concat(dfs_to_concat).filter(~((pl.col("tick") == 0) & (pl.col("event") != "start")))
        rounds_df = rounds_df.unique(subset=["tick", "event"]).sort(by=["tick", "event"])

        # Group events into round sequences
        # Each round: start -> freeze_end -> end -> official_end
        current_round = None
        for row in rounds_df.to_dicts():
            evt = row["event"]
            tick = row["tick"]
            if evt == "start":
                if current_round:
                    # Save previous incomplete round
                    rounds_list.append(current_round)
                current_round = {
                    "round_num": len(rounds_list) + 1,
                    "start_tick": tick,
                    "freeze_end_tick": None,
                    "end_tick": None,
                    "official_end_tick": None,
                    "winner": None,
                    "reason": None,
                    "bomb_plant": 0,
                    "bomb_site": None,
                }
            elif current_round:
                if evt == "freeze_end":
                    current_round["freeze_end_tick"] = tick
                elif evt == "end":
                    current_round["end_tick"] = tick
                    # Query this round winner and reason from round_end df
                    match_end = round_end.filter(pl.col("tick") == tick)
                    if not match_end.is_empty():
                        w = match_end["winner"][0]
                        r = match_end["reason"][0]
                        current_round["winner"] = TEAM_MAP.get(w, "Spectator")
                        current_round["reason"] = ROUND_END_REASON_MAP.get(r, str(r))
                elif evt == "official_end":
                    current_round["official_end_tick"] = tick
                    rounds_list.append(current_round)
                    current_round = None

        if current_round:
            rounds_list.append(current_round)

    # Compute duration_ticks
    duration_ticks = 0
    if rounds_list:
        duration_ticks = max((r["end_tick"] or 0) for r in rounds_list)
    if not duration_ticks:
        duration_ticks = raw_header.get("playback_ticks", 0)

    # Convert to running score
    ct_score = 0
    t_score = 0
    for r in rounds_list:
        if r["winner"] == "CT":
            ct_score += 1
        elif r["winner"] == "T":
            t_score += 1
        r["ct_score"] = ct_score
        r["t_score"] = t_score

    # Helper to assign round_num based on tick
    def get_round_num_for_tick(tick: int) -> int:
        for r in rounds_list:
            start = r["start_tick"] or 0
            end = r["official_end_tick"] or r["end_tick"] or 999999999
            if start <= tick <= end:
                return r["round_num"]
        return 1  # Fallback

    # 3. Kills
    kills_list = []
    if "player_death" in avail_events:
        kills_df = parser.parse_event("player_death", player=["X", "Y", "Z", "attackerblind"])
        for row in kills_df.to_dicts():
            tick = row.get("tick", 0)
            # Distance
            ax, ay, az = row.get("attacker_X"), row.get("attacker_Y"), row.get("attacker_Z")
            vx, vy, vz = row.get("user_X"), row.get("user_Y"), row.get("user_Z")
            distance = 0.0
            if None not in (ax, ay, az, vx, vy, vz):
                distance = math.sqrt((ax-vx)**2 + (ay-vy)**2 + (az-vz)**2)

            kills_list.append({
                "round_num": get_round_num_for_tick(tick),
                "tick": tick,
                "attacker_name": row.get("attacker_name") or "Unknown",
                "victim_name": row.get("user_name") or "Unknown",
                "assister_name": row.get("assister_name"),
                "weapon": row.get("weapon") or "unknown",
                "headshot": 1 if row.get("headshot") else 0,
                "wallbang": 1 if row.get("penetrated", 0) > 0 else 0,
                "noscope": 1 if row.get("noscope") else 0,
                "thru_smoke": 1 if row.get("thrusmoke") else 0,
                "thru_wall": 1 if row.get("penetrated", 0) > 0 else 0,
                "blind_kill": 1 if row.get("attackerblind") else 0,
                "attacker_x": ax, "attacker_y": ay, "attacker_z": az,
                "victim_x": vx, "victim_y": vy, "victim_z": vz,
                "distance": distance
            })

    # 4. Damages
    damages_list = []
    if "player_hurt" in avail_events:
        damages_df = parser.parse_event("player_hurt")
        for row in damages_df.to_dicts():
            tick = row.get("tick", 0)
            hg = row.get("hitgroup", 0)
            damages_list.append({
                "round_num": get_round_num_for_tick(tick),
                "tick": tick,
                "attacker_name": row.get("attacker_name") or "Unknown",
                "victim_name": row.get("user_name") or "Unknown",
                "weapon": row.get("weapon"),
                "hp_damage": row.get("dmg_health") or 0,
                "armor_damage": row.get("dmg_armor") or 0,
                "hitgroup": HITGROUP_MAP.get(hg, str(hg))
            })

    # 5. Grenades (Aggregating trails)
    grenades_list = []
    try:
        # Use demoparser2's parse_grenades() which returns the trail positions
        grenades_df = parser.parse_grenades()
        if not grenades_df.is_empty():
            # Group by entity_id (or entityid)
            entity_col = "entity_id" if "entity_id" in grenades_df.columns else "entityid"
            grouped = grenades_df.sort([entity_col, "tick"]).group_by(entity_col, maintain_order=True).agg([
                pl.col("tick").first().alias("throw_tick"),
                pl.col("tick").last().alias("land_tick"),
                pl.col("X").first().alias("throw_x"),
                pl.col("Y").first().alias("throw_y"),
                pl.col("Z").first().alias("throw_z"),
                pl.col("X").last().alias("land_x"),
                pl.col("Y").last().alias("land_y"),
                pl.col("Z").last().alias("land_z"),
                pl.col("thrower_name").first().alias("thrower_name") if "thrower_name" in grenades_df.columns else pl.col("thrower").first().alias("thrower_name"),
                pl.col("grenade_type").first().alias("nade_type")
            ])
            
            for row in grouped.to_dicts():
                tt = row["throw_tick"]
                lt = row["land_tick"]
                dur = max(0, lt - tt)
                nt = row["nade_type"].lower()
                
                # Normalise nade type name
                if "smoke" in nt: nade_type = "smoke"
                elif "flash" in nt: nade_type = "flash"
                elif "molot" in nt or "inc" in nt: nade_type = "molotov"
                elif "decoy" in nt: nade_type = "decoy"
                elif "he" in nt: nade_type = "he"
                else: nade_type = nt

                grenades_list.append({
                    "round_num": get_round_num_for_tick(tt),
                    "throw_tick": tt,
                    "thrower_name": row["thrower_name"] or "Unknown",
                    "nade_type": nade_type,
                    "throw_x": row["throw_x"], "throw_y": row["throw_y"], "throw_z": row["throw_z"],
                    "land_x": row["land_x"], "land_y": row["land_y"], "land_z": row["land_z"],
                    "land_tick": lt,
                    "duration_ticks": dur
                })
    except Exception as e:
        log.warning(f"Failed to parse grenades trail: {e}")

    # 6. Weapon Fires (Shots)
    shots_list = []
    if "weapon_fire" in avail_events:
        shots_df = parser.parse_event("weapon_fire")
        for row in shots_df.to_dicts():
            tick = row.get("tick", 0)
            shots_list.append({
                "round_num": get_round_num_for_tick(tick),
                "tick": tick,
                "player_name": row.get("user_name") or "Unknown",
                "weapon": row.get("weapon") or "unknown"
            })

    # 7. Bomb Events
    bomb_list = []
    # Combine bomb_planted, bomb_defused, bomb_exploded, bomb_dropped, bomb_pickup
    for evt_name, db_evt in [
        ("bomb_planted", "plant"),
        ("bomb_defused", "defuse"),
        ("bomb_exploded", "explode"),
        ("bomb_dropped", "drop"),
        ("bomb_pickup", "pickup")
    ]:
        if evt_name in avail_events:
            df = parser.parse_event(evt_name)
            for row in df.to_dicts():
                tick = row.get("tick", 0)
                site_code = row.get("site")
                site = "A" if site_code in (220, 4) else ("B" if site_code else None)
                
                # Check for round bomb plant update
                if db_evt == "plant" and site:
                    for r in rounds_list:
                        if r["start_tick"] <= tick <= (r["official_end_tick"] or r["end_tick"] or 999999999):
                            r["bomb_plant"] = 1
                            r["bomb_site"] = site

                bomb_list.append({
                    "round_num": get_round_num_for_tick(tick),
                    "tick": tick,
                    "event": db_evt,
                    "player_name": row.get("user_name"),
                    "site": site,
                    "x": row.get("x", 0.0), "y": row.get("y", 0.0), "z": row.get("z", 0.0)
                })

    # 8. Ticks (if requested)
    ticks_list = []
    if include_ticks:
        try:
            ticks_df = parser.parse_ticks([
                "X", "Y", "Z", "yaw", "pitch", "health", "armor_value", 
                "velocity_X", "velocity_Y", "velocity_Z", "is_alive", 
                "is_planting", "is_defusing"
            ])
            for row in ticks_df.to_dicts():
                tick = row.get("tick", 0)
                ticks_list.append({
                    "round_num": get_round_num_for_tick(tick),
                    "tick": tick,
                    "player_name": row.get("name") or "Unknown",
                    "x": row.get("X"), "y": row.get("Y"), "z": row.get("Z"),
                    "yaw": row.get("yaw"), "pitch": row.get("pitch"),
                    "health": row.get("health", 0), "armor": row.get("armor_value", 0),
                    "velocity_x": row.get("velocity_X"), "velocity_y": row.get("velocity_Y"), "velocity_z": row.get("velocity_Z"),
                    "is_alive": 1 if row.get("is_alive") else 0,
                    "is_planting": 1 if row.get("is_planting") else 0,
                    "is_defusing": 1 if row.get("is_defusing") else 0
                })
        except Exception as e:
            log.warning(f"Failed to parse ticks: {e}")

    # 9. Roster/Players
    # Query ticks at round end ticks to get names, steamids and teams
    players_list = []
    try:
        round_end_ticks = [r["end_tick"] for r in rounds_list if r["end_tick"] is not None]
        if not round_end_ticks:
            round_end_ticks = [1000]
            
        roster_df = parser.parse_ticks(["team_num", "steamid"], ticks=round_end_ticks)
        seen_players = {}
        for row in roster_df.to_dicts():
            name = row.get("name")
            steamid = row.get("steamid")
            team_num = row.get("team_num")
            
            if name and name not in seen_players:
                seen_players[name] = {
                    "name": name,
                    "steam_id": str(steamid) if steamid else None,
                    "team": TEAM_MAP.get(team_num, "Spectator"),
                    "user_id": None
                }
        players_list = list(seen_players.values())
    except Exception as e:
        log.warning(f"Failed to extract roster from ticks: {e}")
        
    # Fallback to names in kills
    if not players_list:
        names = set()
        for k in kills_list:
            names.add(k["attacker_name"])
            names.add(k["victim_name"])
        players_list = [{"name": n, "steam_id": None, "team": "Spectator", "user_id": None} for n in names if n]

    return {
        "header": {
            "map_name": map_name,
            "server_name": server_name,
            "client_name": client_name,
            "demo_type": demo_type,
            "match_date": match_date,
            "duration_ticks": duration_ticks,
            "tick_rate": raw_header.get("tick_rate") or 64
        },
        "players": players_list,
        "rounds": rounds_list,
        "kills": kills_list,
        "damages": damages_list,
        "grenades": grenades_list,
        "shots": shots_list,
        "bomb": bomb_list,
        "ticks": ticks_list
    }

# ---------------------------------------------------------------------------
# Stats Aggregation (ADR, KAST, Rating 2.0)
# ---------------------------------------------------------------------------

def calculate_kast_approx(player_name: str, kills: list, total_rounds: int) -> float:
    """Calculate KAST percentage for a player."""
    if total_rounds == 0:
        return 0.0

    kast_rounds = set()
    death_rounds = set()

    for k in kills:
        r = k["round_num"]
        attacker = k["attacker_name"]
        victim = k["victim_name"]
        assister = k.get("assister_name")

        if attacker == player_name or assister == player_name:
            kast_rounds.add(r)
            
        if victim == player_name:
            death_rounds.add(r)
            # Trade detection: did attacker die in same round within 320 ticks?
            killer = attacker
            death_tick = k["tick"]
            
            was_traded = False
            for k2 in kills:
                if k2["round_num"] != r:
                    continue
                if k2["victim_name"] == killer and k2["tick"] > death_tick and (k2["tick"] - death_tick) <= 320:
                    was_traded = True
                    break
            if was_traded:
                kast_rounds.add(r)

    # Survival: round nums where player did not die
    for r in range(1, total_rounds + 1):
        if r not in death_rounds:
            kast_rounds.add(r)

    pct = (len(kast_rounds) / total_rounds) * 100.0
    return max(0.0, min(100.0, pct))

def calculate_hltv_rating_v2(stats: dict, kills: list, total_rounds: int) -> float:
    """Calculate approximated HLTV Rating 2.0."""
    if total_rounds == 0:
        return 0.0

    r = float(total_rounds)
    
    # Kill Rating
    kr = 0.679 * (stats["kills"] / r)
    
    # Survival Rating
    sr = max(0.0, 0.317 * (1.0 - (stats["deaths"] / r)))
    
    # KAST Rating
    kast_frac = stats["kast"] / 100.0
    kast = 0.7421 * kast_frac
    
    # Impact Rating
    multikill_weight = (
        (stats["multi_kills_2k"] * 0.0021) +
        (stats["multi_kills_3k"] * 0.0037) +
        (stats["multi_kills_4k"] * 0.0053) +
        (stats["multi_kills_5k"] * 0.0069)
    )
    avg_multikill = (stats["kills"] * multikill_weight) / r
    opening = 0.0065 * stats["entry_kills"] / r
    mult = 0.0037 * (stats["multi_kills_4k"] + stats["multi_kills_5k"]) / r
    duo = 0.0021 * stats["multi_kills_3k"] / r
    impact = 0.737 * (avg_multikill + opening + mult + duo)

    return kr + sr + kast + impact

def aggregate_player_stats(parsed_data: dict) -> list[dict]:
    """Aggregate per-player statistics from parsed demo data."""
    players = parsed_data["players"]
    kills = parsed_data["kills"]
    damages = parsed_data["damages"]
    rounds = parsed_data["rounds"]
    total_rounds = len(rounds)

    stats_map = {}
    for p in players:
        name = p["name"]
        stats_map[name] = {
            "player": name,
            "team": p["team"],
            "kills": 0,
            "deaths": 0,
            "assists": 0,
            "damage": 0,
            "adr": 0.0,
            "kast": 0.0,
            "rating": 0.0,
            "hs_pct": 0.0,
            "head_shots": 0,
            "multi_kills_2k": 0,
            "multi_kills_3k": 0,
            "multi_kills_4k": 0,
            "multi_kills_5k": 0,
            "clutches_won": 0,
            "clutches_total": 0,
            "entry_kills": 0,
            "entry_deaths": 0,
            "utility_damage": 0,
            "utility_enemies_flashed": 0,
            "flash_assists": 0,
            "first_bloods": 0,
            "mvp_count": 0
        }

    # Count kills, deaths, assists, headshots
    for k in kills:
        att = k["attacker_name"]
        vic = k["victim_name"]
        ast = k.get("assister_name")

        if att in stats_map:
            stats_map[att]["kills"] += 1
            if k["headshot"]:
                stats_map[att]["head_shots"] += 1
            if k["blind_kill"]:
                stats_map[att]["flash_assists"] += 1

        if vic in stats_map:
            stats_map[vic]["deaths"] += 1

        if ast and ast in stats_map:
            stats_map[ast]["assists"] += 1

    # Count damage
    for d in damages:
        att = d["attacker_name"]
        if att in stats_map:
            stats_map[att]["damage"] += max(0, d["hp_damage"])

    # Count multi-kills per round
    # Group kills by round_num and attacker
    round_kills = {}
    for k in kills:
        r = k["round_num"]
        att = k["attacker_name"]
        if r not in round_kills:
            round_kills[r] = {}
        round_kills[r][att] = round_kills[r].get(att, 0) + 1

    for r_num, att_counts in round_kills.items():
        for att, count in att_counts.items():
            if att in stats_map:
                if count == 2:
                    stats_map[att]["multi_kills_2k"] += 1
                elif count == 3:
                    stats_map[att]["multi_kills_3k"] += 1
                elif count == 4:
                    stats_map[att]["multi_kills_4k"] += 1
                elif count >= 5:
                    stats_map[att]["multi_kills_5k"] += 1

    # Calculate final variables
    for name, stats in stats_map.items():
        stats["adr"] = (stats["damage"] / total_rounds) if total_rounds > 0 else 0.0
        stats["hs_pct"] = (stats["head_shots"] / stats["kills"] * 100.0) if stats["kills"] > 0 else 0.0
        stats["kast"] = calculate_kast_approx(name, kills, total_rounds)
        stats["rating"] = calculate_hltv_rating_v2(stats, kills, total_rounds)

    return list(stats_map.values())
