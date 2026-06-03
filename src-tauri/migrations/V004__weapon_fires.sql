-- V004__weapon_fires.sql
-- One row per weapon_fire event (shots fired). Used for accuracy /
-- spray-pattern analytics in week 6.

CREATE TABLE weapon_fires (
    id              INTEGER PRIMARY KEY,
    match_id        INTEGER NOT NULL,
    round_id        INTEGER NOT NULL REFERENCES rounds(id) ON DELETE CASCADE,
    tick            INTEGER,
    attacker        TEXT NOT NULL,
    weapon          TEXT
);

CREATE INDEX idx_fires_match    ON weapon_fires(match_id);
CREATE INDEX idx_fires_round    ON weapon_fires(round_id);
CREATE INDEX idx_fires_attacker ON weapon_fires(match_id, attacker);
