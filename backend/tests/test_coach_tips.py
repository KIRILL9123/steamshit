import sqlite3
import pytest
import aiosqlite
from contextlib import asynccontextmanager
from unittest.mock import patch
from backend.analytics import generate_coach_tips

# Save a reference to the real connect to avoid infinite recursion
real_connect = sqlite3.connect
SHARED_DB_URI = "file:memdb_coach_tips?mode=memory&cache=shared"

@asynccontextmanager
async def mock_get_connection():
    # Connect to the same shared memory DB using aiosqlite
    conn = await aiosqlite.connect(SHARED_DB_URI, uri=True)
    conn.row_factory = aiosqlite.Row
    try:
        yield conn
    finally:
        await conn.close()

@pytest.fixture
def mock_db():
    # Initialize the database schema
    conn = real_connect(SHARED_DB_URI, uri=True)
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
        deaths INTEGER DEFAULT 0,
        team TEXT,
        entry_deaths INTEGER DEFAULT 0,
        trade_rate REAL DEFAULT 0.0,
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
        match_id INTEGER,
        headshot BOOLEAN DEFAULT 0
    )""")
    conn.execute("""
    CREATE TABLE IF NOT EXISTS flash_events (
        id INTEGER PRIMARY KEY,
        match_id INTEGER,
        round_id INTEGER,
        tick INTEGER,
        attacker TEXT,
        victim TEXT,
        duration_seconds REAL,
        is_teammate BOOLEAN
    )""")
    conn.execute("""
    CREATE TABLE IF NOT EXISTS damages (
        id INTEGER PRIMARY KEY,
        match_id INTEGER,
        round_id INTEGER,
        tick INTEGER,
        attacker TEXT,
        victim TEXT,
        weapon TEXT,
        hp_damage INTEGER,
        hitgroup TEXT
    )""")
    conn.execute("""
    CREATE TABLE IF NOT EXISTS coach_tips (
        id INTEGER PRIMARY KEY,
        match_id INTEGER,
        player TEXT,
        category TEXT,
        priority INTEGER,
        title TEXT,
        body TEXT,
        metric_name TEXT,
        current_value REAL,
        target_value REAL,
        evidence_json TEXT
    )""")
    conn.commit()
    
    # Patch sqlite3.connect to return a connection to our shared in-memory database
    def mock_connect(database, *args, **kwargs):
        c = real_connect(SHARED_DB_URI, uri=True)
        c.row_factory = sqlite3.Row
        return c
    
    with patch("sqlite3.connect", side_effect=mock_connect), \
         patch("backend.analytics.get_connection", mock_get_connection):
        yield conn
        
    conn.close()

@pytest.mark.asyncio
async def test_teamflash_habit_tip(mock_db):
    conn = mock_db
    conn.execute("DELETE FROM kills")
    conn.execute("DELETE FROM flash_events")
    
    # Needs kills to not trigger 'No kills found' early return
    conn.execute("INSERT INTO kills (match_id, attacker, victim, tick) VALUES (1, 'PlayerA', 'PlayerB', 100)")
    
    # PlayerA blinds 3 teammates and 1 enemy -> 3/4 = 75% ratio (above 30% threshold and >= 3 teamflashes)
    conn.execute("INSERT INTO flash_events (match_id, round_id, tick, attacker, victim, duration_seconds, is_teammate) VALUES (1, 1, 10, 'PlayerA', 'Teammate1', 2.0, 1)")
    conn.execute("INSERT INTO flash_events (match_id, round_id, tick, attacker, victim, duration_seconds, is_teammate) VALUES (1, 1, 20, 'PlayerA', 'Teammate2', 2.0, 1)")
    conn.execute("INSERT INTO flash_events (match_id, round_id, tick, attacker, victim, duration_seconds, is_teammate) VALUES (1, 1, 30, 'PlayerA', 'Teammate3', 2.0, 1)")
    conn.execute("INSERT INTO flash_events (match_id, round_id, tick, attacker, victim, duration_seconds, is_teammate) VALUES (1, 1, 40, 'PlayerA', 'Enemy1', 2.0, 0)")
    conn.commit()
    
    tips = await generate_coach_tips(match_id=1)
    teamflash_tips = [t for t in tips if t["title"] == "Опасные световые (Teamflash Habit)"]
    assert len(teamflash_tips) == 1
    assert teamflash_tips[0]["player"] == "PlayerA"
    assert teamflash_tips[0]["current_value"] == 75.0

@pytest.mark.asyncio
async def test_lone_wolf_tip(mock_db):
    conn = mock_db
    conn.execute("DELETE FROM kills")
    conn.execute("DELETE FROM player_match_stats")
    
    # Insert players into player_match_stats
    conn.execute("INSERT INTO player_match_stats (match_id, player, deaths, team) VALUES (1, 'PlayerA', 10, 'T')")
    conn.execute("INSERT INTO player_match_stats (match_id, player, deaths, team) VALUES (1, 'PlayerB', 10, 'T')")
    
    # Mock compute_trade_stats to return pre-defined stats
    mock_trade_stats = {
        "PlayerA": {"traded_deaths": 1, "trade_kills": 0, "trade_rate": 0.1, "total_deaths": 10},
        "PlayerB": {"traded_deaths": 5, "trade_kills": 0, "trade_rate": 0.5, "total_deaths": 10}
    }
    
    # Kills to bypass early return
    conn.execute("INSERT INTO kills (match_id, attacker, victim, tick) VALUES (1, 'PlayerB', 'PlayerA', 100)")
    conn.commit()
    
    with patch("backend.analytics.compute_trade_stats", return_value=mock_trade_stats):
        tips = await generate_coach_tips(match_id=1)
        lone_wolf_tips = [t for t in tips if t["title"] == "Игра в соло (Lone Wolf)"]
        assert len(lone_wolf_tips) == 1
        assert lone_wolf_tips[0]["player"] == "PlayerA"

@pytest.mark.asyncio
async def test_missed_multikill_tip(mock_db):
    conn = mock_db
    conn.execute("DELETE FROM kills")
    conn.execute("DELETE FROM damages")
    
    conn.execute("INSERT INTO kills (match_id, attacker, victim, tick) VALUES (1, 'PlayerB', 'PlayerA', 100)")
    
    # Round 1: PlayerA deals damage to Enemy1 and Enemy2, but gets 0 kills
    conn.execute("INSERT INTO damages (match_id, round_id, tick, attacker, victim, hp_damage) VALUES (1, 1, 10, 'PlayerA', 'Enemy1', 50)")
    conn.execute("INSERT INTO damages (match_id, round_id, tick, attacker, victim, hp_damage) VALUES (1, 1, 20, 'PlayerA', 'Enemy2', 50)")
    
    # Round 2: PlayerA deals damage to Enemy1 and Enemy2, but gets 0 kills
    conn.execute("INSERT INTO damages (match_id, round_id, tick, attacker, victim, hp_damage) VALUES (1, 2, 10, 'PlayerA', 'Enemy1', 50)")
    conn.execute("INSERT INTO damages (match_id, round_id, tick, attacker, victim, hp_damage) VALUES (1, 2, 20, 'PlayerA', 'Enemy2', 50)")
    conn.commit()
    
    tips = await generate_coach_tips(match_id=1)
    multikill_tips = [t for t in tips if t["title"] == "Упущенные мультикиллы"]
    assert len(multikill_tips) == 1
    assert multikill_tips[0]["player"] == "PlayerA"
    assert multikill_tips[0]["current_value"] == 2

@pytest.mark.asyncio
async def test_entry_fragger_no_support_tip(mock_db):
    conn = mock_db
    conn.execute("DELETE FROM kills")
    conn.execute("DELETE FROM player_match_stats")
    
    # Kills to bypass early return
    conn.execute("INSERT INTO kills (match_id, attacker, victim, tick) VALUES (1, 'PlayerB', 'PlayerA', 100)")
    
    # PlayerA: entry_deaths = 4, trade_rate = 10% (0.1)
    conn.execute("INSERT INTO player_match_stats (match_id, player, entry_deaths, trade_rate) VALUES (1, 'PlayerA', 4, 0.1)")
    conn.commit()
    
    tips = await generate_coach_tips(match_id=1)
    entry_tips = [t for t in tips if t["title"] == "Вход без поддержки (Entry No Support)"]
    assert len(entry_tips) == 1
    assert entry_tips[0]["player"] == "PlayerA"
    assert entry_tips[0]["current_value"] == 10.0
