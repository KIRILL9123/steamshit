import sqlite3
import pytest
from unittest.mock import patch
from backend.analytics import compute_clutch_stats

# Save a reference to the real connect to avoid infinite recursion
real_connect = sqlite3.connect

@pytest.fixture
def mock_db():
    uri = "file:memdb_clutch?mode=memory&cache=shared"
    
    # Initialize the database schema
    conn = real_connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("""
    CREATE TABLE IF NOT EXISTS rounds (
        id INTEGER PRIMARY KEY,
        round_num INTEGER,
        winner TEXT,
        match_id INTEGER
    )""")
    conn.execute("""
    CREATE TABLE IF NOT EXISTS player_match_stats (
        match_id INTEGER,
        player TEXT,
        team TEXT,
        clutches_won INTEGER DEFAULT 0,
        clutches_total INTEGER DEFAULT 0
    )""")
    conn.execute("""
    CREATE TABLE IF NOT EXISTS kills (
        id INTEGER PRIMARY KEY,
        round_id INTEGER,
        tick INTEGER,
        attacker TEXT,
        victim TEXT,
        match_id INTEGER
    )""")
    conn.execute("""
    CREATE TABLE IF NOT EXISTS clutch_events (
        id INTEGER PRIMARY KEY,
        match_id INTEGER,
        round_id INTEGER,
        player TEXT,
        team TEXT,
        opponents_count INTEGER,
        won BOOLEAN
    )""")
    conn.commit()
    
    # Patch sqlite3.connect to return a connection to our shared in-memory database
    def mock_connect(database, *args, **kwargs):
        c = real_connect(uri, uri=True)
        c.row_factory = sqlite3.Row
        return c
    
    with patch("sqlite3.connect", side_effect=mock_connect):
        yield conn
        
    conn.close()

def test_clutch_stats_scenarios(mock_db):
    conn = sqlite3.connect("dummy.db")
    
    # Clean up from any previous runs
    conn.execute("DELETE FROM rounds")
    conn.execute("DELETE FROM player_match_stats")
    conn.execute("DELETE FROM kills")
    conn.execute("DELETE FROM clutch_events")
    
    # 1. Setup 10 players
    players = [
        ('PlayerT1', 'T'), ('PlayerT2', 'T'), ('PlayerT3', 'T'), ('PlayerT4', 'T'), ('PlayerT5', 'T'),
        ('PlayerCT1', 'CT'), ('PlayerCT2', 'CT'), ('PlayerCT3', 'CT'), ('PlayerCT4', 'CT'), ('PlayerCT5', 'CT')
    ]
    for name, team in players:
        conn.execute("INSERT INTO player_match_stats (match_id, player, team) VALUES (1, ?, ?)", (name, team))
        
    # 2. Setup Round 1: CT wins
    conn.execute("INSERT INTO rounds (id, round_num, winner, match_id) VALUES (1, 1, 'CT', 1)")
    
    # Kills progression:
    # 4 T players die (PlayerT5, PlayerT4, PlayerT3, PlayerT2)
    # This leaves PlayerT1 in a 1v5 situation.
    conn.execute("INSERT INTO kills (round_id, tick, victim) VALUES (1, 100, 'PlayerT5')")
    conn.execute("INSERT INTO kills (round_id, tick, victim) VALUES (1, 110, 'PlayerT4')")
    conn.execute("INSERT INTO kills (round_id, tick, victim) VALUES (1, 120, 'PlayerT3')")
    conn.execute("INSERT INTO kills (round_id, tick, victim) VALUES (1, 130, 'PlayerT2')")
    
    # PlayerT1 kills 4 CT players (PlayerCT5, PlayerCT4, PlayerCT3, PlayerCT2)
    # This leaves PlayerCT1 in a 1v1 situation.
    conn.execute("INSERT INTO kills (round_id, tick, victim) VALUES (1, 140, 'PlayerCT5')")
    conn.execute("INSERT INTO kills (round_id, tick, victim) VALUES (1, 150, 'PlayerCT4')")
    conn.execute("INSERT INTO kills (round_id, tick, victim) VALUES (1, 160, 'PlayerCT3')")
    conn.execute("INSERT INTO kills (round_id, tick, victim) VALUES (1, 170, 'PlayerCT2')")
    
    # PlayerCT1 kills PlayerT1 (CT wins the round)
    conn.execute("INSERT INTO kills (round_id, tick, victim) VALUES (1, 180, 'PlayerT1')")
    
    # Setup Round 2: Normal round, T wins, no clutches (only one death, leaving 4v5)
    conn.execute("INSERT INTO rounds (id, round_num, winner, match_id) VALUES (2, 2, 'T', 1)")
    conn.execute("INSERT INTO kills (round_id, tick, victim) VALUES (2, 200, 'PlayerT5')")
    
    conn.commit()
    
    # Compute
    compute_clutch_stats(1)
    
    # Verify clutch_events
    events = conn.execute("SELECT player, team, opponents_count, won, round_id FROM clutch_events ORDER BY id").fetchall()
    assert len(events) == 2
    
    # Event 1: PlayerCT1 (1v1 Won) - CT clutch is inserted first in the code
    assert events[0]["player"] == "PlayerCT1"
    assert events[0]["team"] == "CT"
    assert events[0]["opponents_count"] == 1
    assert events[0]["won"] == 1
    assert events[0]["round_id"] == 1
    
    # Event 2: PlayerT1 (1v5 Lost) - T clutch is inserted second in the code
    assert events[1]["player"] == "PlayerT1"
    assert events[1]["team"] == "T"
    assert events[1]["opponents_count"] == 5
    assert events[1]["won"] == 0
    assert events[1]["round_id"] == 1
    
    # Verify player_match_stats updates
    p_stats = conn.execute("SELECT player, clutches_won, clutches_total FROM player_match_stats").fetchall()
    stats_dict = {r["player"]: (r["clutches_won"], r["clutches_total"]) for r in p_stats}
    
    assert stats_dict["PlayerT1"] == (0, 1)
    assert stats_dict["PlayerCT1"] == (1, 1)
    assert stats_dict["PlayerT2"] == (0, 0)
