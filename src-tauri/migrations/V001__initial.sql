-- V001__initial.sql
-- Initial schema: matches, players, rounds, kills, damages, grenades, utility_blinds,
-- bomb_events, equipment, ticks (position samples), player_match_stats, app_settings,
-- map_calibrations.
--
-- Conventions:
--   * Surrogate INTEGER PRIMARY KEY for fact tables (kills, damages, etc.)
--   * Composite natural keys for joined-fact rows (player_match_stats, ticks).
--   * All timestamps stored as ISO-8601 TEXT (UTC) for easy round-tripping.
--   * Boolean flags as INTEGER (0/1) to match demoparser2 outputs.
--   * Coordinates in Source engine units (1 unit = ~1 inch / 2.54 cm).

PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------------
-- matches: one row per imported .dem / .dem.zst file
-- ---------------------------------------------------------------------------
CREATE TABLE matches (
    id              INTEGER PRIMARY KEY,
    file_path       TEXT UNIQUE NOT NULL,
    file_hash       TEXT NOT NULL,            -- SHA-256 hex, used to dedupe re-imports
    file_size       INTEGER,
    map_name        TEXT NOT NULL,
    server_name     TEXT,
    client_name     TEXT,
    demo_type       TEXT,                     -- "valve" / "faceit" / "hltv" / "unknown"
    match_date      TEXT,                     -- ISO-8601
    duration_ticks  INTEGER,
    parsed_at       TEXT NOT NULL,
    parse_version   INTEGER NOT NULL          -- bumped when parser schema changes
);

CREATE INDEX idx_matches_date ON matches(match_date DESC);
CREATE INDEX idx_matches_map  ON matches(map_name);

-- ---------------------------------------------------------------------------
-- players: roster per match (10-10 players + spectators)
-- ---------------------------------------------------------------------------
CREATE TABLE players (
    match_id        INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    steam_id        TEXT,
    name            TEXT NOT NULL,
    team            TEXT NOT NULL,            -- "CT" / "T" / "Spectator"
    initial_side    TEXT,
    user_id         INTEGER,
    PRIMARY KEY (match_id, name)
);

CREATE INDEX idx_players_steam ON players(steam_id);

-- ---------------------------------------------------------------------------
-- rounds: one row per round (mr12 / mr15 etc.)
-- ---------------------------------------------------------------------------
CREATE TABLE rounds (
    id              INTEGER PRIMARY KEY,
    match_id        INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    round_num       INTEGER NOT NULL,
    start_tick      INTEGER,
    freeze_end_tick INTEGER,
    end_tick        INTEGER,
    winner          TEXT,                     -- "CT" / "T"
    reason          TEXT,
    bomb_plant      INTEGER DEFAULT 0,        -- 0/1
    bomb_site       TEXT,                     -- "A" / "B"
    ct_score        INTEGER,
    t_score         INTEGER,
    UNIQUE(match_id, round_num)
);

CREATE INDEX idx_rounds_match ON rounds(match_id);

-- ---------------------------------------------------------------------------
-- kills: aggregated kill events (denormalized positions for fast heatmaps)
-- ---------------------------------------------------------------------------
CREATE TABLE kills (
    id              INTEGER PRIMARY KEY,
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

CREATE INDEX idx_kills_match    ON kills(match_id);
CREATE INDEX idx_kills_round    ON kills(round_id);
CREATE INDEX idx_kills_attacker ON kills(match_id, attacker);
CREATE INDEX idx_kills_victim   ON kills(match_id, victim);

-- ---------------------------------------------------------------------------
-- damages: every damage instance (one kill = N damages)
-- ---------------------------------------------------------------------------
CREATE TABLE damages (
    id              INTEGER PRIMARY KEY,
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

CREATE INDEX idx_dmg_round    ON damages(round_id);
CREATE INDEX idx_dmg_attacker ON damages(match_id, attacker);

-- ---------------------------------------------------------------------------
-- grenades: one row per thrown utility (smoke/flash/molotov/decoy)
-- ---------------------------------------------------------------------------
CREATE TABLE grenades (
    id              INTEGER PRIMARY KEY,
    match_id        INTEGER NOT NULL,
    round_id        INTEGER NOT NULL REFERENCES rounds(id) ON DELETE CASCADE,
    throw_tick      INTEGER,
    thrower         TEXT NOT NULL,
    nade_type       TEXT NOT NULL,            -- "smoke" / "flash" / "molotov" / "decoy" / "he"
    throw_x REAL, throw_y REAL, throw_z REAL,
    land_x  REAL, land_y  REAL, land_z  REAL,
    land_tick       INTEGER,
    duration_ticks  INTEGER
);

CREATE INDEX idx_nades_round ON grenades(round_id);
CREATE INDEX idx_nades_type  ON grenades(nade_type);

-- ---------------------------------------------------------------------------
-- utility_blinds: per-victim flash duration (denormalized for filtering)
-- ---------------------------------------------------------------------------
CREATE TABLE utility_blinds (
    id              INTEGER PRIMARY KEY,
    match_id        INTEGER NOT NULL,
    round_id        INTEGER NOT NULL REFERENCES rounds(id) ON DELETE CASCADE,
    flasher         TEXT NOT NULL,
    victim          TEXT NOT NULL,
    duration_ticks  INTEGER,
    tick            INTEGER
);

CREATE INDEX idx_blinds_round ON utility_blinds(round_id);

-- ---------------------------------------------------------------------------
-- bomb_events: plant / defuse / explode (low-volume table)
-- ---------------------------------------------------------------------------
CREATE TABLE bomb_events (
    id              INTEGER PRIMARY KEY,
    match_id        INTEGER NOT NULL,
    round_id        INTEGER NOT NULL REFERENCES rounds(id) ON DELETE CASCADE,
    tick            INTEGER,
    event           TEXT NOT NULL,            -- "plant" / "defuse" / "explode" / "pickup" / "drop"
    player          TEXT,
    site            TEXT,
    x REAL, y REAL, z REAL
);

CREATE INDEX idx_bomb_round ON bomb_events(round_id);

-- ---------------------------------------------------------------------------
-- equipment: per-tick equipment snapshots (sample rate ≈ 1 Hz)
-- ---------------------------------------------------------------------------
CREATE TABLE equipment (
    id              INTEGER PRIMARY KEY,
    match_id        INTEGER NOT NULL,
    round_id        INTEGER NOT NULL REFERENCES rounds(id) ON DELETE CASCADE,
    player          TEXT NOT NULL,
    tick            INTEGER,
    weapon          TEXT,
    weapon_class    TEXT,
    armor           INTEGER DEFAULT 0,
    helmet          INTEGER DEFAULT 0,
    has_kit         INTEGER DEFAULT 0,
    money_spent     INTEGER
);

CREATE INDEX idx_equip_round_player ON equipment(round_id, player);

-- ---------------------------------------------------------------------------
-- ticks: per-player position samples (highest-volume table).
-- WITHOUT ROWID + composite PK for compact storage and fast range scans.
-- ---------------------------------------------------------------------------
CREATE TABLE ticks (
    match_id        INTEGER NOT NULL,
    round_id        INTEGER NOT NULL,
    tick            INTEGER NOT NULL,
    player          TEXT NOT NULL,
    x REAL, y REAL, z REAL,
    yaw REAL, pitch REAL,
    health INTEGER, armor INTEGER,
    velocity_x REAL, velocity_y REAL, velocity_z REAL,
    is_alive        INTEGER,
    is_planting     INTEGER DEFAULT 0,
    is_defusing     INTEGER DEFAULT 0,
    PRIMARY KEY (round_id, player, tick)
) WITHOUT ROWID;

CREATE INDEX idx_ticks_match_player ON ticks(match_id, player);

-- ---------------------------------------------------------------------------
-- player_match_stats: aggregated per-(match,player) — used by Overview/Coach
-- ---------------------------------------------------------------------------
CREATE TABLE player_match_stats (
    match_id        INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    player          TEXT NOT NULL,
    team            TEXT,
    kills           INTEGER DEFAULT 0,
    deaths          INTEGER DEFAULT 0,
    assists         INTEGER DEFAULT 0,
    damage          INTEGER DEFAULT 0,
    adr             REAL DEFAULT 0,
    kast            REAL DEFAULT 0,
    rating          REAL DEFAULT 0,           -- HLTV Rating 2.0
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
    PRIMARY KEY (match_id, player)
);

CREATE INDEX idx_pms_match ON player_match_stats(match_id);

-- ---------------------------------------------------------------------------
-- app_settings: simple key-value store for user preferences / paths
-- ---------------------------------------------------------------------------
CREATE TABLE app_settings (
    key             TEXT PRIMARY KEY,
    value           TEXT,
    updated_at      TEXT
);

-- ---------------------------------------------------------------------------
-- map_calibrations: per-map radar image + coord calibration
-- ---------------------------------------------------------------------------
CREATE TABLE map_calibrations (
    map_name        TEXT PRIMARY KEY,
    calibration_json TEXT NOT NULL,           -- scale, offset, rotation
    image_path      TEXT NOT NULL,            -- absolute path inside data dir
    updated_at      TEXT
);
