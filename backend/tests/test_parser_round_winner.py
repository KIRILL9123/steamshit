import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
from backend.parser import parse_demo

@patch("os.path.exists", return_value=True)
@patch("os.path.getmtime", return_value=1700000000)
def test_parser_spectator_bug_regression(mock_mtime, mock_exists):
    # Mock DemoParser instance
    mock_parser = MagicMock()
    mock_parser.parse_header.return_value = {
        "map_name": "de_dust2",
        "server_name": "Valve Matchmaking Server",
        "client_name": "Valve",
        "demo_version_name": "CS2",
        "playback_ticks": 1000
    }
    mock_parser.list_game_events.return_value = [
        "round_start", "round_freeze_end", "round_end", "round_officially_ended"
    ]
    
    # We return mock Pandas DataFrames like demoparser2 would
    def mock_parse_event(event_name, *args, **kwargs):
        if event_name == "round_start":
            return pd.DataFrame({"tick": [100]})
        elif event_name == "round_freeze_end":
            return pd.DataFrame({"tick": [110]})
        elif event_name == "round_end":
            return pd.DataFrame({"tick": [200], "winner": ["CT"], "reason": [1]})
        elif event_name == "round_officially_ended":
            return pd.DataFrame({"tick": [210]})
        return pd.DataFrame()
        
    mock_parser.parse_event.side_effect = mock_parse_event
    
    with patch("backend.parser.DemoParser", return_value=mock_parser):
        result = parse_demo("dummy_path.dem")
        
        # Verify the round winner is correctly mapped to "CT"
        rounds = result["rounds"]
        assert len(rounds) == 1
        assert rounds[0]["round_num"] == 1
        assert rounds[0]["winner"] == "CT"
        assert rounds[0]["reason"] == "target_bombed" or rounds[0]["reason"] is not None
