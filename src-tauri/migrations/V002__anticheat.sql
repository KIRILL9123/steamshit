-- V002__anticheat.sql
-- Per-(match,player,heuristic) flags emitted by the heuristic engine.
-- See docs/ALGORITHMS.md §2 for the 8 heuristics currently implemented.

CREATE TABLE anticheat_flags (
    id              INTEGER PRIMARY KEY,
    match_id        INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    player          TEXT NOT NULL,
    heuristic       TEXT NOT NULL,            -- e.g. "snap_aim", "pre_aim_through_wall"
    severity        REAL NOT NULL,            -- 0.0 .. 1.0 (normalized)
    evidence_count  INTEGER,
    details_json    TEXT                      -- structured evidence (samples, p-values, etc.)
);

CREATE INDEX idx_ac_match_player  ON anticheat_flags(match_id, player);
CREATE INDEX idx_ac_heuristic     ON anticheat_flags(heuristic);
CREATE INDEX idx_ac_severity_desc ON anticheat_flags(severity DESC);
