import gzip
import datetime
import sqlite3
import json
import os
from typing import Optional
from contextlib import asynccontextmanager

import aiosqlite
import polars as pl

DB_PATH = "fragscope.db"


def _snake_to_camel(s: str) -> str:
    """Convert snake_case column name to camelCase for the frontend."""
    parts = s.split("_")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])


def _row_to_camel(row) -> dict:
    """Convert an aiosqlite.Row (or dict) to a camelCase dict."""
    return {_snake_to_camel(k): v for k, v in dict(row).items()}

# Schema creation SQL queries
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS matches (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path       TEXT UNIQUE NOT NULL,
    file_hash       TEXT NOT NULL,
    file_size       INTEGER,
    map_name        TEXT NOT NULL,
    server_name     TEXT,
    client_name     TEXT,
    demo_type       TEXT,
    match_date      TEXT,
    duration_ticks  INTEGER,
    parsed_at       TEXT NOT NULL,
    parse_version   INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS players (
    match_id        INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    steam_id        TEXT,
    name            TEXT NOT NULL,
    team            TEXT NOT NULL,
    initial_side    TEXT,
    user_id         INTEGER,
    PRIMARY KEY (match_id, name)
);

CREATE TABLE IF NOT EXISTS rounds (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id        INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    round_num       INTEGER NOT NULL,
    start_tick      INTEGER,
    freeze_end_tick INTEGER,
    end_tick        INTEGER,
    winner          TEXT,
    reason          TEXT,
    bomb_plant      INTEGER DEFAULT 0,
    bomb_site       TEXT,
    ct_score        INTEGER,
    t_score         INTEGER,
    movement_data   BLOB,
    UNIQUE(match_id, round_num)
);

CREATE TABLE IF NOT EXISTS kills (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id        INTEGER NOT NULL,
    round_id        INTEGER NOT NULL REFERENCES rounds(id) ON DELETE CASCADE,
    tick            INTEGER,
    attacker        TEXT NOT NULL,
    victim          TEXT NOT NULL,
    assister        TEXT,
    weapon          TEXT NOT NULL,
    headshot        INTEGER DEFAULT 0,
    wallbang        INTEGER DEFAULT 0,
    noscope         INTEGER DEFAULT 0,
    thru_smoke      INTEGER DEFAULT 0,
    thru_wall       INTEGER DEFAULT 0,
    blind_kill      INTEGER DEFAULT 0,
    attacker_x      REAL, attacker_y REAL, attacker_z REAL,
    victim_x        REAL, victim_y REAL, victim_z REAL,
    distance        REAL
);

CREATE TABLE IF NOT EXISTS damages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id        INTEGER NOT NULL,
    round_id        INTEGER NOT NULL REFERENCES rounds(id) ON DELETE CASCADE,
    tick            INTEGER,
    attacker        TEXT NOT NULL,
    victim          TEXT NOT NULL,
    weapon          TEXT,
    hp_damage       INTEGER,
    armor_damage    INTEGER,
    hitgroup        TEXT
);

CREATE TABLE IF NOT EXISTS grenades (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id        INTEGER NOT NULL,
    round_id        INTEGER NOT NULL REFERENCES rounds(id) ON DELETE CASCADE,
    throw_tick      INTEGER,
    thrower         TEXT NOT NULL,
    nade_type       TEXT NOT NULL,
    throw_x         REAL, throw_y REAL, throw_z REAL,
    land_x          REAL, land_y  REAL, land_z  REAL,
    land_tick       INTEGER,
    duration_ticks  INTEGER
);

CREATE TABLE IF NOT EXISTS weapon_fires (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id        INTEGER NOT NULL,
    round_id        INTEGER NOT NULL REFERENCES rounds(id) ON DELETE CASCADE,
    tick            INTEGER,
    attacker        TEXT NOT NULL,
    weapon          TEXT
);

CREATE TABLE IF NOT EXISTS bomb_events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id        INTEGER NOT NULL,
    round_id        INTEGER NOT NULL REFERENCES rounds(id) ON DELETE CASCADE,
    tick            INTEGER,
    event           TEXT NOT NULL,
    player          TEXT,
    site            TEXT,
    x REAL, y REAL, z REAL
);

CREATE TABLE IF NOT EXISTS flash_events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id        INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    round_id        INTEGER NOT NULL REFERENCES rounds(id) ON DELETE CASCADE,
    tick            INTEGER NOT NULL,
    attacker        TEXT NOT NULL,
    victim          TEXT NOT NULL,
    duration_seconds REAL NOT NULL,
    is_teammate     BOOLEAN NOT NULL
);

CREATE TABLE IF NOT EXISTS player_match_stats (
    match_id        INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    player          TEXT NOT NULL,
    team            TEXT,
    kills           INTEGER DEFAULT 0,
    deaths          INTEGER DEFAULT 0,
    assists         INTEGER DEFAULT 0,
    damage          INTEGER DEFAULT 0,
    adr             REAL DEFAULT 0,
    kast            REAL DEFAULT 0,
    rating          REAL DEFAULT 0,
    hs_pct          REAL DEFAULT 0,
    head_shots      INTEGER DEFAULT 0,
    multi_kills_2k  INTEGER DEFAULT 0,
    multi_kills_3k  INTEGER DEFAULT 0,
    multi_kills_4k  INTEGER DEFAULT 0,
    multi_kills_5k  INTEGER DEFAULT 0,
    clutches_won    INTEGER DEFAULT 0,
    clutches_total  INTEGER DEFAULT 0,
    entry_kills     INTEGER DEFAULT 0,
    entry_deaths    INTEGER DEFAULT 0,
    utility_damage  INTEGER DEFAULT 0,
    utility_enemies_flashed INTEGER DEFAULT 0,
    flash_assists   INTEGER DEFAULT 0,
    first_bloods    INTEGER DEFAULT 0,
    mvp_count       INTEGER DEFAULT 0,
    accuracy        REAL DEFAULT 0,
    headshot_accuracy REAL DEFAULT 0,
    avg_ttk_ms      REAL DEFAULT 0,
    first_bullet_accuracy REAL DEFAULT 0,
    utility_damage_dealt REAL DEFAULT 0,
    utility_damage_taken REAL DEFAULT 0,
    smokes_thrown   INTEGER DEFAULT 0,
    avg_enemy_flash_duration REAL DEFAULT 0,
    avg_teammate_flash_duration REAL DEFAULT 0,
    enemies_blinded INTEGER DEFAULT 0,
    teammates_blinded INTEGER DEFAULT 0,
    flashbangs_thrown INTEGER DEFAULT 0,
    PRIMARY KEY (match_id, player)
);

CREATE TABLE IF NOT EXISTS anticheat_flags (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id        INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    player          TEXT NOT NULL,
    heuristic       TEXT NOT NULL,
    severity        REAL NOT NULL,
    evidence_count  INTEGER,
    details_json    TEXT
);

CREATE TABLE IF NOT EXISTS coach_tips (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id        INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    player          TEXT,
    category        TEXT NOT NULL,
    priority        INTEGER DEFAULT 0,
    title           TEXT NOT NULL,
    body            TEXT NOT NULL,
    metric_name     TEXT,
    current_value   REAL,
    target_value    REAL,
    evidence_json   TEXT
);

CREATE TABLE IF NOT EXISTS app_settings (
    key             TEXT PRIMARY KEY,
    value           TEXT,
    updated_at      TEXT
);

CREATE TABLE IF NOT EXISTS map_calibrations (
    map_name        TEXT PRIMARY KEY,
    calibration_json TEXT NOT NULL,
    image_path      TEXT NOT NULL,
    updated_at      TEXT
);

-- Indices
CREATE INDEX IF NOT EXISTS idx_matches_date ON matches(match_date DESC);
CREATE INDEX IF NOT EXISTS idx_matches_map  ON matches(map_name);
CREATE INDEX IF NOT EXISTS idx_players_steam ON players(steam_id);
CREATE INDEX IF NOT EXISTS idx_rounds_match ON rounds(match_id);
CREATE INDEX IF NOT EXISTS idx_kills_match    ON kills(match_id);
CREATE INDEX IF NOT EXISTS idx_kills_round    ON kills(round_id);
CREATE INDEX IF NOT EXISTS idx_kills_attacker ON kills(match_id, attacker);
CREATE INDEX IF NOT EXISTS idx_kills_victim   ON kills(match_id, victim);
CREATE INDEX IF NOT EXISTS idx_dmg_round    ON damages(round_id);
CREATE INDEX IF NOT EXISTS idx_dmg_attacker ON damages(match_id, attacker);
CREATE INDEX IF NOT EXISTS idx_nades_round ON grenades(round_id);
CREATE INDEX IF NOT EXISTS idx_nades_type  ON grenades(nade_type);
CREATE INDEX IF NOT EXISTS idx_fires_match    ON weapon_fires(match_id);
CREATE INDEX IF NOT EXISTS idx_fires_round    ON weapon_fires(round_id);
CREATE INDEX IF NOT EXISTS idx_fires_attacker ON weapon_fires(match_id, attacker);
CREATE INDEX IF NOT EXISTS idx_bomb_round ON bomb_events(round_id);
CREATE INDEX IF NOT EXISTS idx_flashes_round ON flash_events(round_id);
CREATE INDEX IF NOT EXISTS idx_pms_match ON player_match_stats(match_id);
CREATE INDEX IF NOT EXISTS idx_ac_match_player ON anticheat_flags(match_id, player);
CREATE INDEX IF NOT EXISTS idx_ac_heuristic ON anticheat_flags(heuristic);
CREATE INDEX IF NOT EXISTS idx_ac_severity_desc ON anticheat_flags(severity DESC);
CREATE INDEX IF NOT EXISTS idx_coach_match ON coach_tips(match_id);
CREATE INDEX IF NOT EXISTS idx_coach_player ON coach_tips(player);
CREATE INDEX IF NOT EXISTS idx_coach_category ON coach_tips(category);
CREATE INDEX IF NOT EXISTS idx_coach_priority ON coach_tips(priority DESC);
"""

@asynccontextmanager
async def get_connection():
    """Create and configure a DB connection as an async context manager."""
    conn = await aiosqlite.connect(DB_PATH)
    try:
        await conn.execute("PRAGMA foreign_keys = ON")
        await conn.execute("PRAGMA journal_mode = WAL")
        await conn.execute("PRAGMA synchronous = NORMAL")
        conn.row_factory = aiosqlite.Row
        yield conn
    finally:
        await conn.close()

async def init_db():
    """Initialise the database and create tables/indices if they don't exist."""
    async with get_connection() as conn:
        await conn.executescript(SCHEMA_SQL)
        # Migration: Add new columns to player_match_stats if they don't exist
        for col, col_type in [
            ("accuracy", "REAL DEFAULT 0"),
            ("headshot_accuracy", "REAL DEFAULT 0"),
            ("avg_ttk_ms", "REAL DEFAULT 0"),
            ("first_bullet_accuracy", "REAL DEFAULT 0"),
            ("utility_damage_dealt", "REAL DEFAULT 0"),
            ("utility_damage_taken", "REAL DEFAULT 0"),
            ("smokes_thrown", "INTEGER DEFAULT 0"),
            ("avg_enemy_flash_duration", "REAL DEFAULT 0"),
            ("avg_teammate_flash_duration", "REAL DEFAULT 0"),
            ("enemies_blinded", "INTEGER DEFAULT 0"),
            ("teammates_blinded", "INTEGER DEFAULT 0"),
            ("flashbangs_thrown", "INTEGER DEFAULT 0")
        ]:
            try:
                await conn.execute(f"ALTER TABLE player_match_stats ADD COLUMN {col} {col_type}")
            except sqlite3.OperationalError:
                # Column already exists
                pass
        await conn.commit()

async def get_db():
    """FastAPI Dependency for database connection."""
    async with get_connection() as conn:
        yield conn

# ---------------------------------------------------------------------------
# Match operations
# ---------------------------------------------------------------------------

async def find_match_by_hash(conn: aiosqlite.Connection, file_hash: str):
    """Retrieve match by file hash (deduplication)."""
    async with conn.execute("SELECT * FROM matches WHERE file_hash = ? LIMIT 1", (file_hash,)) as cursor:
        row = await cursor.fetchone()
        return dict(row) if row else None

async def list_matches(conn: aiosqlite.Connection):
    """List all imported matches."""
    async with conn.execute(
        "SELECT * FROM matches ORDER BY match_date DESC NULLS LAST, parsed_at DESC"
    ) as cursor:
        rows = await cursor.fetchall()
        return [_row_to_camel(r) for r in rows]

async def get_match(conn: aiosqlite.Connection, match_id: int):
    """Get match details including header, players, and stats."""
    async with conn.execute("SELECT * FROM matches WHERE id = ?", (match_id,)) as cursor:
        match_row = await cursor.fetchone()
        if not match_row:
            return None

    async with conn.execute("SELECT * FROM players WHERE match_id = ?", (match_id,)) as cursor:
        players = await cursor.fetchall()

    async with conn.execute(
        "SELECT * FROM player_match_stats WHERE match_id = ? ORDER BY rating DESC, kills DESC",
        (match_id,)
    ) as cursor:
        stats = await cursor.fetchall()

    return {
        "header": _row_to_camel(match_row),
        "players": [_row_to_camel(p) for p in players],
        "stats": [_row_to_camel(s) for s in stats]
    }

async def delete_match(conn: aiosqlite.Connection, match_id: int):
    """Delete a match. Cascade deletes will clean up linked tables."""
    await conn.execute("DELETE FROM matches WHERE id = ?", (match_id,))
    await conn.commit()

async def list_round_progression(conn: aiosqlite.Connection, match_id: int):
    """List round scoring progression."""
    async with conn.execute(
        "SELECT round_num, ct_score, t_score, winner, reason, bomb_plant "
        "FROM rounds WHERE match_id = ? ORDER BY round_num ASC",
        (match_id,)
    ) as cursor:
        rows = await cursor.fetchall()
        return [
            {
                "roundNum": r["round_num"],
                "ctScore": r["ct_score"] or 0,
                "tScore": r["t_score"] or 0,
                "winner": r["winner"],
                "reason": r["reason"],
                "bombPlant": bool(r["bomb_plant"])
            }
            for r in rows
        ]

async def get_utility_throws(conn: aiosqlite.Connection, match_id: int):
    """Return utility throws aggregated per player."""
    async with conn.execute(
        "SELECT thrower, nade_type, COUNT(*) as count "
        "FROM grenades "
        "WHERE match_id = ? AND thrower IS NOT NULL "
        "GROUP BY thrower, nade_type",
        (match_id,)
    ) as cursor:
        rows = await cursor.fetchall()

    stats_map = {}
    for r in rows:
        thrower = r["thrower"]
        nade_type = r["nade_type"].lower()
        count = r["count"]

        if thrower not in stats_map:
            stats_map[thrower] = {
                "player": thrower,
                "he": 0,
                "flash": 0,
                "smoke": 0,
                "molly": 0,
                "decoy": 0
            }

        stats = stats_map[thrower]
        if nade_type in ("hegrenade", "he"):
            stats["he"] += count
        elif nade_type in ("flashbang", "flash"):
            stats["flash"] += count
        elif nade_type in ("smokegrenade", "smoke"):
            stats["smoke"] += count
        elif nade_type in ("molotov", "incgrenade", "incendiary"):
            stats["molly"] += count
        elif nade_type == "decoy":
            stats["decoy"] += count

    return list(stats_map.values())

async def get_heatmap_data(conn: aiosqlite.Connection, match_id: int, player: str = None):
    """Get kill coordinates for heatmaps."""
    query = "SELECT attacker_x, attacker_y, victim_x, victim_y FROM kills WHERE match_id = ?"
    params = [match_id]
    if player:
        query += " AND attacker = ?"
        params.append(player)

    async with conn.execute(query, params) as cursor:
        rows = await cursor.fetchall()

    points = []
    for r in rows:
        ax, ay, vx, vy = r["attacker_x"], r["attacker_y"], r["victim_x"], r["victim_y"]
        if ax is not None and ay is not None:
            points.append({"x": ax, "y": ay, "kind": "kill_attacker"})
        if vx is not None and vy is not None:
            points.append({"x": vx, "y": vy, "kind": "kill_victim"})

    return points

# ---------------------------------------------------------------------------
# Round operations
# ---------------------------------------------------------------------------

async def list_rounds(conn: aiosqlite.Connection, match_id: int):
    """List rounds for a match."""
    async with conn.execute(
        "SELECT id, match_id, round_num, start_tick, freeze_end_tick, end_tick, "
        "winner, reason, bomb_plant, bomb_site, ct_score, t_score "
        "FROM rounds WHERE match_id = ? ORDER BY round_num ASC",
        (match_id,)
    ) as cursor:
        rows = await cursor.fetchall()
        return [
            {
                "id": r["id"],
                "matchId": r["match_id"],
                "roundNum": r["round_num"],
                "startTick": r["start_tick"],
                "freezeEndTick": r["freeze_end_tick"],
                "endTick": r["end_tick"],
                "winner": r["winner"],
                "reason": r["reason"],
                "bombPlant": bool(r["bomb_plant"]),
                "bombSite": r["bomb_site"],
                "ctScore": r["ct_score"],
                "tScore": r["t_score"]
            }
            for r in rows
        ]

async def get_round_kills(conn: aiosqlite.Connection, round_id: int):
    """Get kills for a specific round."""
    async with conn.execute(
        "SELECT tick, attacker, victim, weapon, headshot, wallbang, thru_smoke, "
        "attacker_x, attacker_y, victim_x, victim_y, distance "
        "FROM kills WHERE round_id = ? ORDER BY tick ASC",
        (round_id,)
    ) as cursor:
        rows = await cursor.fetchall()
        return [
            {
                "tick": r["tick"],
                "attacker": r["attacker"],
                "victim": r["victim"],
                "weapon": r["weapon"],
                "headshot": bool(r["headshot"]),
                "wallbang": bool(r["wallbang"]),
                "thruSmoke": bool(r["thru_smoke"]),
                "attackerX": r["attacker_x"],
                "attackerY": r["attacker_y"],
                "victimX": r["victim_x"],
                "victimY": r["victim_y"],
                "distance": r["distance"]
            }
            for r in rows
        ]

async def get_round_grenades(conn: aiosqlite.Connection, round_id: int):
    """Get grenades for a specific round."""
    async with conn.execute(
        "SELECT throw_tick, thrower, nade_type, throw_x, throw_y, land_x, land_y "
        "FROM grenades WHERE round_id = ? ORDER BY throw_tick ASC",
        (round_id,)
    ) as cursor:
        rows = await cursor.fetchall()
        return [
            {
                "throwTick": r["throw_tick"],
                "thrower": r["thrower"],
                "nadeType": r["nade_type"],
                "throwX": r["throw_x"],
                "throwY": r["throw_y"],
                "landX": r["land_x"],
                "landY": r["land_y"]
            }
            for r in rows
        ]

async def get_round_movement(conn: aiosqlite.Connection, round_id: int):
    """Get decompressed movement data for a specific round."""
    async with conn.execute(
        "SELECT movement_data FROM rounds WHERE id = ?",
        (round_id,)
    ) as cursor:
        row = await cursor.fetchone()
        if not row or not row["movement_data"]:
            return []
        try:
            compressed = row["movement_data"]
            decompressed = gzip.decompress(compressed)
            return json.loads(decompressed.decode("utf-8"))
        except Exception as e:
            import logging
            logging.getLogger("uvicorn.error").error(f"Failed to decompress movement_data: {e}")
            return []

# ---------------------------------------------------------------------------
# Coach & Anticheat operations
# ---------------------------------------------------------------------------

async def get_anticheat_flags(conn: aiosqlite.Connection, match_id: int):
    """Get anticheat flags."""
    async with conn.execute(
        "SELECT id, match_id, player, heuristic, severity, evidence_count, details_json "
        "FROM anticheat_flags WHERE match_id = ? ORDER BY severity DESC",
        (match_id,)
    ) as cursor:
        rows = await cursor.fetchall()
        return [
            {
                "id": r["id"],
                "matchId": r["match_id"],
                "player": r["player"],
                "heuristic": r["heuristic"],
                "severity": r["severity"],
                "evidenceCount": r["evidence_count"],
                "detailsJson": r["details_json"]
            }
            for r in rows
        ]

async def save_anticheat_flags(conn: aiosqlite.Connection, match_id: int, flags: list):
    """Save anticheat flags (deleting old ones first)."""
    await conn.execute("DELETE FROM anticheat_flags WHERE match_id = ?", (match_id,))
    for f in flags:
        await conn.execute(
            "INSERT INTO anticheat_flags (match_id, player, heuristic, severity, evidence_count, details_json) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (match_id, f["player"], f["heuristic"], f["severity"], f["evidence_count"], f["details_json"])
        )
    await conn.commit()

async def get_coach_tips(conn: aiosqlite.Connection, match_id: int, player: str = None):
    """Get coaching tips, optionally filtered by player."""
    query = (
        "SELECT id, match_id, player, category, priority, title, body, metric_name, current_value, target_value, evidence_json "
        "FROM coach_tips WHERE match_id = ?"
    )
    params = [match_id]
    if player:
        query += " AND (player = ? OR player IS NULL)"
        params.append(player)
    query += " ORDER BY priority DESC"

    async with conn.execute(query, params) as cursor:
        rows = await cursor.fetchall()
        return [
            {
                "id": r["id"],
                "matchId": r["match_id"],
                "player": r["player"],
                "category": r["category"],
                "priority": r["priority"],
                "title": r["title"],
                "body": r["body"],
                "metricName": r["metric_name"],
                "currentValue": r["current_value"],
                "targetValue": r["target_value"],
                "evidenceJson": r["evidence_json"]
            }
            for r in rows
        ]

async def save_coach_tips(conn: aiosqlite.Connection, match_id: int, tips: list):
    """Save coaching tips (deleting old ones first)."""
    await conn.execute("DELETE FROM coach_tips WHERE match_id = ?", (match_id,))
    for t in tips:
        await conn.execute(
            "INSERT INTO coach_tips (match_id, player, category, priority, title, body, "
            "metric_name, current_value, target_value, evidence_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                match_id, t.get("player"), t["category"], t.get("priority", 0), t["title"], t["body"],
                t.get("metric_name"), t.get("current_value"), t.get("target_value"), t.get("evidence_json")
            )
        )
    await conn.commit()

# ---------------------------------------------------------------------------
# Insert Parsed Demo Transaction
# ---------------------------------------------------------------------------

async def insert_parsed_demo(conn: aiosqlite.Connection, parsed_data: dict, file_path: str, file_hash: str, file_size: int) -> int:
    """Insert parsed demo data into the database in a transaction."""
    header = parsed_data["header"]
    parsed_at = datetime.datetime.now(datetime.UTC).isoformat()

    # 1. Insert match
    cursor = await conn.execute(
        "INSERT INTO matches (file_path, file_hash, file_size, map_name, server_name, client_name, "
        "demo_type, match_date, duration_ticks, parsed_at, parse_version) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            file_path, file_hash, file_size, header["map_name"], header["server_name"], header["client_name"],
            header["demo_type"], header["match_date"], header["duration_ticks"], parsed_at, 1
        )
    )
    match_id = cursor.lastrowid

    # 2. Insert players
    for p in parsed_data["players"]:
        await conn.execute(
            "INSERT OR IGNORE INTO players (match_id, steam_id, name, team, initial_side, user_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (match_id, p["steam_id"], p["name"], p["team"], p.get("initial_side"), p.get("user_id"))
        )

    # 3. Insert rounds
    round_id_map = {}  # round_num -> round_id
    for r in parsed_data["rounds"]:
        cur = await conn.execute(
            "INSERT INTO rounds (match_id, round_num, start_tick, freeze_end_tick, end_tick, winner, reason, bomb_plant, bomb_site, ct_score, t_score, movement_data) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                match_id, r["round_num"], r["start_tick"], r["freeze_end_tick"], r["end_tick"],
                r["winner"], r["reason"], r["bomb_plant"], r["bomb_site"], r["ct_score"], r["t_score"],
                r.get("movement_data")
            )
        )
        round_id_map[r["round_num"]] = cur.lastrowid

    # 4. Insert kills
    for k in parsed_data["kills"]:
        round_id = round_id_map.get(k["round_num"])
        if not round_id:
            continue
        await conn.execute(
            "INSERT INTO kills (match_id, round_id, tick, attacker, victim, assister, weapon, headshot, wallbang, noscope, thru_smoke, thru_wall, blind_kill, "
            "attacker_x, attacker_y, attacker_z, victim_x, victim_y, victim_z, distance) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                match_id, round_id, k["tick"], k["attacker_name"], k["victim_name"], k["assister_name"], k["weapon"],
                k["headshot"], k["wallbang"], k["noscope"], k["thru_smoke"], k["thru_wall"], k["blind_kill"],
                k["attacker_x"], k["attacker_y"], k["attacker_z"], k["victim_x"], k["victim_y"], k["victim_z"], k["distance"]
            )
        )

    # 5. Insert damages
    for d in parsed_data["damages"]:
        round_id = round_id_map.get(d["round_num"])
        if not round_id:
            continue
        await conn.execute(
            "INSERT INTO damages (match_id, round_id, tick, attacker, victim, weapon, hp_damage, armor_damage, hitgroup) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                match_id, round_id, d["tick"], d["attacker_name"], d["victim_name"], d["weapon"],
                d["hp_damage"], d["armor_damage"], d["hitgroup"]
            )
        )

    # 6. Insert grenades
    for g in parsed_data["grenades"]:
        round_id = round_id_map.get(g["round_num"])
        if not round_id:
            continue
        await conn.execute(
            "INSERT INTO grenades (match_id, round_id, throw_tick, thrower, nade_type, throw_x, throw_y, throw_z, land_x, land_y, land_z, land_tick, duration_ticks) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                match_id, round_id, g["throw_tick"], g["thrower_name"], g["nade_type"],
                g["throw_x"], g["throw_y"], g["throw_z"], g["land_x"], g["land_y"], g["land_z"], g["land_tick"], g["duration_ticks"]
            )
        )

    # 7. Insert weapon fires
    for s in parsed_data["shots"]:
        round_id = round_id_map.get(s["round_num"])
        if not round_id:
            continue
        await conn.execute(
            "INSERT INTO weapon_fires (match_id, round_id, tick, attacker, weapon) VALUES (?, ?, ?, ?, ?)",
            (match_id, round_id, s["tick"], s["player_name"], s["weapon"])
        )

    # 8. Insert bomb events
    for b in parsed_data["bomb"]:
        round_id = round_id_map.get(b["round_num"])
        if not round_id:
            continue
        await conn.execute(
            "INSERT INTO bomb_events (match_id, round_id, tick, event, player, site, x, y, z) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                match_id, round_id, b["tick"], b["event"], b["player_name"], b["site"],
                b["x"], b["y"], b["z"]
            )
        )

    # 8.5 Insert flash events
    player_teams = {p["name"]: p["team"].upper() for p in parsed_data["players"] if p.get("name") and p.get("team")}
    for f in parsed_data.get("flashes", []):
        round_id = round_id_map.get(f["round_num"])
        if not round_id:
            continue
        team_a = player_teams.get(f["attacker"])
        team_v = player_teams.get(f["victim"])
        is_teammate = (team_a == team_v) if (team_a and team_v) else False
        await conn.execute(
            "INSERT INTO flash_events (match_id, round_id, tick, attacker, victim, duration_seconds, is_teammate) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (match_id, round_id, f["tick"], f["attacker"], f["victim"], f["duration"], is_teammate)
        )

    # 10. Insert player stats overview
    from backend.parser import aggregate_player_stats
    stats = aggregate_player_stats(parsed_data)
    for s in stats:
        await conn.execute(
            "INSERT OR REPLACE INTO player_match_stats (match_id, player, team, kills, deaths, assists, damage, "
            "adr, kast, rating, hs_pct, head_shots, multi_kills_2k, multi_kills_3k, multi_kills_4k, multi_kills_5k, "
            "clutches_won, clutches_total, entry_kills, entry_deaths, utility_damage, utility_enemies_flashed, "
            "flash_assists, first_bloods, mvp_count) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                match_id, s["player"], s["team"], s["kills"], s["deaths"], s["assists"], s["damage"],
                s["adr"], s["kast"], s["rating"], s["hs_pct"], s["head_shots"], s["multi_kills_2k"], s["multi_kills_3k"],
                s["multi_kills_4k"], s["multi_kills_5k"], s["clutches_won"], s["clutches_total"], s["entry_kills"],
                s["entry_deaths"], s["utility_damage"], s["utility_enemies_flashed"], s["flash_assists"],
                s["first_bloods"], s["mvp_count"]
            )
        )

    await conn.commit()

    # Compute and update AIM and UTILITY metrics
    try:
        from backend.analytics import compute_aim_stats, compute_utility_stats
        
        # 1. Update AIM stats
        aim_stats = compute_aim_stats(match_id)
        for player, stats_dict in aim_stats.items():
            await conn.execute(
                "UPDATE player_match_stats SET accuracy = ?, headshot_accuracy = ?, avg_ttk_ms = ?, first_bullet_accuracy = ? "
                "WHERE match_id = ? AND player = ?",
                (
                    stats_dict["accuracy"],
                    stats_dict["headshot_accuracy"],
                    stats_dict["avg_ttk_ms"],
                    stats_dict["first_bullet_accuracy"],
                    match_id,
                    player
                )
            )
            
        # 2. Update UTILITY stats
        utility_stats = compute_utility_stats(match_id)
        for player, stats_dict in utility_stats.items():
            await conn.execute(
                "UPDATE player_match_stats SET utility_damage_dealt = ?, utility_damage_taken = ?, smokes_thrown = ?, "
                "avg_enemy_flash_duration = ?, avg_teammate_flash_duration = ?, "
                "enemies_blinded = ?, teammates_blinded = ?, flashbangs_thrown = ? "
                "WHERE match_id = ? AND player = ?",
                (
                    stats_dict["utility_damage_dealt"],
                    stats_dict["utility_damage_taken"],
                    stats_dict["smokes_thrown"],
                    stats_dict["avg_enemy_flash_duration"],
                    stats_dict["avg_teammate_flash_duration"],
                    stats_dict["enemies_blinded"],
                    stats_dict["teammates_blinded"],
                    stats_dict["flashbangs_thrown"],
                    match_id,
                    player
                )
            )
        await conn.commit()
    except Exception as e:
        import logging
        logging.getLogger("uvicorn.error").error(f"Failed to compute aim/utility stats: {e}")

    return match_id

# ---------------------------------------------------------------------------
# App Settings Helpers
# ---------------------------------------------------------------------------

async def get_setting(conn: aiosqlite.Connection, key: str) -> str | None:
    """Retrieve setting value by key."""
    async with conn.execute("SELECT value FROM app_settings WHERE key = ?", (key,)) as cursor:
        row = await cursor.fetchone()
        return row[0] if row else None

async def set_setting(conn: aiosqlite.Connection, key: str, value: str | None):
    """Insert or update setting value."""
    updated_at = datetime.datetime.now(datetime.UTC).isoformat()
    await conn.execute(
        "INSERT OR REPLACE INTO app_settings (key, value, updated_at) VALUES (?, ?, ?)",
        (key, value, updated_at)
    )
    await conn.commit()

# ---------------------------------------------------------------------------
# Polars Helper DB Reader
# ---------------------------------------------------------------------------

def load_kills(db_path: str, match_id: int) -> pl.DataFrame:
    """Load kills for coach / anticheat processing."""
    conn = sqlite3.connect(db_path)
    try:
        query = f"SELECT * FROM kills WHERE match_id = {match_id}"
        return pl.read_database(query, conn)
    finally:
        conn.close()


