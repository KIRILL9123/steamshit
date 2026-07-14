import sqlite3
import pytest
from unittest.mock import patch
from backend.analytics import compute_aim_stats

# Save a reference to the real connect to avoid infinite recursion
real_connect = sqlite3.connect

@pytest.fixture
def mock_db():
    uri = "file:memdb_aim?mode=memory&cache=shared"
    
    # Initialize the database schema
    conn = real_connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("""
    CREATE TABLE IF NOT EXISTS weapon_fires (
        round_id INTEGER,
        tick INTEGER,
        attacker TEXT,
        weapon TEXT,
        match_id INTEGER
    )""")
    conn.execute("""
    CREATE TABLE IF NOT EXISTS damages (
        round_id INTEGER,
        tick INTEGER,
        attacker TEXT,
        victim TEXT,
        weapon TEXT,
        hp_damage INTEGER,
        hitgroup TEXT,
        match_id INTEGER
    )""")
    conn.execute("""
    CREATE TABLE IF NOT EXISTS kills (
        round_id INTEGER,
        tick INTEGER,
        attacker TEXT,
        victim TEXT,
        match_id INTEGER
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

def test_aim_stats_computations(mock_db):
    conn = sqlite3.connect("dummy.db")
    
    # Clean up from any previous runs
    conn.execute("DELETE FROM weapon_fires")
    conn.execute("DELETE FROM damages")
    conn.execute("DELETE FROM kills")
    
    # PlayerA:
    # Shot 1 at tick 100
    # Damage hit (head) at tick 100
    # Kill at tick 105 (TTK = 5 ticks = 78.125 ms)
    conn.execute("INSERT INTO weapon_fires VALUES (1, 100, 'PlayerA', 'weapon_ak47', 1)")
    conn.execute("INSERT INTO damages VALUES (1, 100, 'PlayerA', 'PlayerB', 'ak47', 100, 'head', 1)")
    conn.execute("INSERT INTO kills VALUES (1, 105, 'PlayerA', 'PlayerB', 1)")
    
    # PlayerC (Outside 192-tick window check):
    # Shot 1 at tick 1000
    # Shot 2 at tick 1300
    # Damage 1 (chest) at tick 1000 (outside window of kill at 1310: 1310 - 192 = 1118)
    # Damage 2 (chest) at tick 1300 (inside window)
    # Kill at tick 1310 (TTK should use tick 1300, not 1000 -> TTK = 10 ticks = 156.25 ms)
    conn.execute("INSERT INTO weapon_fires VALUES (1, 1000, 'PlayerC', 'weapon_ak47', 1)")
    conn.execute("INSERT INTO weapon_fires VALUES (1, 1300, 'PlayerC', 'weapon_ak47', 1)")
    conn.execute("INSERT INTO damages VALUES (1, 1000, 'PlayerC', 'PlayerD', 'ak47', 50, 'chest', 1)")
    conn.execute("INSERT INTO damages VALUES (1, 1300, 'PlayerC', 'PlayerD', 'ak47', 50, 'chest', 1)")
    conn.execute("INSERT INTO kills VALUES (1, 1310, 'PlayerC', 'PlayerD', 1)")
    
    # PlayerB (No shots fired, only victim - check division by zero safety)
    
    conn.commit()
    
    stats = compute_aim_stats(match_id=1)
    
    # Assertions for PlayerA
    assert stats["PlayerA"]["accuracy"] == 1.0
    assert stats["PlayerA"]["headshot_accuracy"] == 1.0
    assert stats["PlayerA"]["avg_ttk_ms"] == pytest.approx(78.125)
    
    # Assertions for PlayerC
    # accuracy: 2 hits / 2 shots = 1.0
    # headshot_accuracy: 0 hits of head group / 2 hits = 0.0
    # avg_ttk: min tick inside [1118, 1310] is 1300. delta = 1310 - 1300 = 10 ticks -> 156.25 ms
    assert stats["PlayerC"]["accuracy"] == 1.0
    assert stats["PlayerC"]["headshot_accuracy"] == 0.0
    assert stats["PlayerC"]["avg_ttk_ms"] == pytest.approx(156.25)
    
    # Assertions for PlayerB (zero shots safety check)
    assert stats["PlayerB"]["accuracy"] == 0.0
    assert stats["PlayerB"]["headshot_accuracy"] == 0.0
    assert stats["PlayerB"]["avg_ttk_ms"] == 0.0
    assert stats["PlayerB"]["first_bullet_accuracy"] == 0.0
