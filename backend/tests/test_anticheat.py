import pytest
import polars as pl
from unittest.mock import patch, AsyncMock
from backend.analytics import run_anticheat_analysis

# Helper to mock database save
class AsyncContextManagerMock:
    async def __aenter__(self):
        return AsyncMock()
    async def __aexit__(self, exc_type, exc, tb):
        pass

@pytest.fixture
def mock_db_save():
    with patch("backend.analytics.get_connection", return_value=AsyncContextManagerMock()) as mock_conn, \
         patch("backend.analytics.save_anticheat_flags", new_callable=AsyncMock) as mock_save:
        yield mock_save

@pytest.mark.asyncio
async def test_snap_aim_trigger(mock_db_save):
    # Attacker does a yaw jump from 0.0 to 50.0 degrees (diff > 45) right before the kill tick (tick 100)
    ticks_df = pl.DataFrame({
        "tick": [90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100],
        "player": ["PlayerA"] * 11,
        "yaw": [0.0, 0.0, 0.0, 0.0, 0.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0],
        "pitch": [0.0] * 11,
        "X": [0.0] * 11,
        "Y": [0.0] * 11,
    })

    # 1 kill at tick 100
    kills_df = pl.DataFrame({
        "attacker": ["PlayerA"],
        "victim": ["PlayerB"],
        "tick": [100],
        "headshot": [0],
        "round_id": [1],
    })

    with patch("backend.analytics.load_kills", return_value=kills_df):
        flags = await run_anticheat_analysis(match_id=1, ticks_df=ticks_df)
        
        # Check that snap_aim was triggered
        snap_aim_flags = [f for f in flags if f["heuristic"] == "snap_aim"]
        assert len(snap_aim_flags) == 1
        assert snap_aim_flags[0]["player"] == "PlayerA"
        assert snap_aim_flags[0]["severity"] > 0.3

@pytest.mark.asyncio
async def test_velocity_snap_freeze_time_exclusion(mock_db_save):
    # Suspicious movement of 500 units in 1 tick at tick 102
    ticks_df = pl.DataFrame({
        "tick": [100, 101, 102],
        "player": ["PlayerA"] * 3,
        "yaw": [0.0] * 3,
        "pitch": [0.0] * 3,
        "X": [0.0, 0.0, 500.0],  # 500 units jump in 1 tick
        "Y": [0.0, 0.0, 0.0],
    })

    kills_df = pl.DataFrame({
        "attacker": ["PlayerA"],
        "victim": ["PlayerB"],
        "tick": [100],
        "headshot": [0],
        "round_id": [1],
    })

    # Round freeze_end_tick is 100, so tick 102 (within freeze_end_tick + 5) is excluded
    rounds_df = pl.DataFrame({
        "id": [1],
        "round_num": [1],
        "start_tick": [0],
        "freeze_end_tick": [100],
    })

    with patch("backend.analytics.load_kills", return_value=kills_df), \
         patch("backend.analytics._load_rounds", return_value=rounds_df):
        flags = await run_anticheat_analysis(match_id=1, ticks_df=ticks_df)
        
        # Check that velocity_snap is NOT triggered because the suspicious movement happened in freeze time
        velocity_snap_flags = [f for f in flags if f["heuristic"] == "velocity_snap"]
        assert len(velocity_snap_flags) == 0

@pytest.mark.asyncio
async def test_silent_aim_one_tap_vs_double_dink(mock_db_save):
    # Case 1: One-tap kill. Only 1 damage event before the kill, or 0.
    # Should NOT trigger silent_aim.
    kills_df = pl.DataFrame({
        "attacker": ["PlayerA"] * 3,
        "victim": ["PlayerB", "PlayerC", "PlayerD"],
        "tick": [100, 200, 300],
        "headshot": [1, 1, 1],
        "round_id": [1, 1, 1],
    })

    # One hit on each victim at the same tick as the kill (so tick < kill_tick filter has 0 hits)
    damages_df_onetap = pl.DataFrame({
        "attacker": ["PlayerA"] * 3,
        "victim": ["PlayerB", "PlayerC", "PlayerD"],
        "tick": [100, 200, 300],
        "hp_damage": [100, 100, 100],
        "round_id": [1, 1, 1],
    })

    # Passing a simple non-empty ticks_df so it doesn't try to query matches table
    ticks_df = pl.DataFrame({
        "tick": [100, 200, 300],
        "player": ["PlayerA"] * 3,
        "yaw": [0.0] * 3,
        "pitch": [0.0] * 3,
        "X": [0.0] * 3,
        "Y": [0.0] * 3,
    })

    with patch("backend.analytics.load_kills", return_value=kills_df), \
         patch("backend.analytics._load_damages", return_value=damages_df_onetap):
        flags = await run_anticheat_analysis(match_id=1, ticks_df=ticks_df)
        silent_aim_flags = [f for f in flags if f["heuristic"] == "silent_aim"]
        assert len(silent_aim_flags) == 0

    # Case 2: Double dink. 2 hits before the kill on each of the 3 kills, within 13 ticks.
    # Should trigger silent_aim.
    damages_df_double = pl.DataFrame({
        "attacker": ["PlayerA"] * 6,
        "victim": ["PlayerB", "PlayerB", "PlayerC", "PlayerC", "PlayerD", "PlayerD"],
        "tick": [90, 95, 190, 195, 290, 295],
        "hp_damage": [50, 50, 50, 50, 50, 50],
        "round_id": [1, 1, 1, 1, 1, 1],
    })

    with patch("backend.analytics.load_kills", return_value=kills_df), \
         patch("backend.analytics._load_damages", return_value=damages_df_double):
        flags = await run_anticheat_analysis(match_id=1, ticks_df=ticks_df)
        silent_aim_flags = [f for f in flags if f["heuristic"] == "silent_aim"]
        assert len(silent_aim_flags) == 1
        assert silent_aim_flags[0]["player"] == "PlayerA"
        assert silent_aim_flags[0]["evidence_count"] == 3
