import sqlite3
import pytest
from unittest.mock import patch
from backend.analytics import compute_trade_stats

# Save a reference to the real connect to avoid infinite recursion
real_connect = sqlite3.connect

@pytest.fixture
def mock_db():
    # Use a shared cache URI so all connections to this URI share the same database
    uri = "file:memdb_trade?mode=memory&cache=shared"
    
    # Initialize the database schema
    conn = real_connect(uri, uri=True)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS kills (
        id INTEGER PRIMARY KEY,
        match_id INTEGER,
        round_id INTEGER,
        tick INTEGER,
        attacker TEXT,
        victim TEXT
    )""")
    conn.execute("""
    CREATE TABLE IF NOT EXISTS player_match_stats (
        match_id INTEGER,
        player TEXT,
        deaths INTEGER,
        team TEXT
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

def test_trade_stats_scenarios(mock_db):
    conn = mock_db
    
    # Clean up from any previous runs
    conn.execute("DELETE FROM player_match_stats")
    conn.execute("DELETE FROM kills")
    
    # Setup players:
    # Team T: PlayerA, PlayerB
    # Team CT: PlayerC, PlayerD
    conn.execute("INSERT INTO player_match_stats VALUES (1, 'PlayerA', 1, 'T')")
    conn.execute("INSERT INTO player_match_stats VALUES (1, 'PlayerB', 1, 'T')")
    conn.execute("INSERT INTO player_match_stats VALUES (1, 'PlayerC', 1, 'CT')")
    conn.execute("INSERT INTO player_match_stats VALUES (1, 'PlayerD', 1, 'CT')")
    
    # 1. Simple Trade scenario:
    # PlayerC kills PlayerA at tick 100
    # PlayerB (T) kills PlayerC (CT) at tick 200 (delta 100 < 320) -> Valid trade
    conn.execute("INSERT INTO kills (match_id, round_id, tick, attacker, victim) VALUES (1, 1, 100, 'PlayerC', 'PlayerA')")
    conn.execute("INSERT INTO kills (match_id, round_id, tick, attacker, victim) VALUES (1, 1, 200, 'PlayerB', 'PlayerC')")
    
    # 2. Out of time window scenario:
    # PlayerC kills PlayerB at tick 300
    # PlayerA kills PlayerC at tick 700 (delta 400 > 320) -> Invalid
    conn.execute("INSERT INTO kills (match_id, round_id, tick, attacker, victim) VALUES (1, 1, 300, 'PlayerC', 'PlayerB')")
    conn.execute("INSERT INTO kills (match_id, round_id, tick, attacker, victim) VALUES (1, 1, 700, 'PlayerA', 'PlayerC')")
    
    conn.commit()
    
    # Compute trade stats
    stats = compute_trade_stats(match_id=1)
    
    # Assertions for simple trade
    assert stats["PlayerA"]["traded_deaths"] == 1
    assert stats["PlayerB"]["trade_kills"] == 1
    assert stats["PlayerA"]["trade_rate"] == 1.0
    
    # Assertions for out-of-window trade (PlayerB's death at tick 300 was not traded by PlayerA at 700)
    assert stats["PlayerB"]["traded_deaths"] == 0
    assert stats["PlayerA"]["trade_kills"] == 0  # 0 because tick 700 was too late
