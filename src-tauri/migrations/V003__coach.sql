-- V003__coach.sql
-- AI coaching tips: per-match, optionally per-player, with priority and
-- structured evidence for "why this tip?" tooltips in the UI.

CREATE TABLE coach_tips (
    id              INTEGER PRIMARY KEY,
    match_id        INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    player          TEXT,                     -- NULL = team-wide tip
    category        TEXT NOT NULL,            -- "positioning" / "utility" / "economy" / "aim" / "trade"
    priority        INTEGER DEFAULT 0,        -- higher = more important
    title           TEXT NOT NULL,
    body            TEXT NOT NULL,
    metric_name     TEXT,
    current_value   REAL,
    target_value    REAL,
    evidence_json   TEXT
);

CREATE INDEX idx_coach_match      ON coach_tips(match_id);
CREATE INDEX idx_coach_player     ON coach_tips(player);
CREATE INDEX idx_coach_category   ON coach_tips(category);
CREATE INDEX idx_coach_priority   ON coach_tips(priority DESC);
