import sqlite3
import os
import logging

log = logging.getLogger("uvicorn.error")
DB_PATH = "fragscope.db"

def get_player_map_stats(player_name: str) -> list[dict]:
    """Retrieve career map statistics for a player, including CT/T round win rates."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.execute(
            "SELECT pms.*, m.map_name, m.match_date "
            "FROM player_match_stats pms "
            "JOIN matches m ON pms.match_id = m.id "
            "WHERE pms.player = ?",
            (player_name,)
        )
        matches = [dict(r) for r in cur.fetchall()]
        if not matches:
            return []
            
        maps_data = {}
        for m in matches:
            m_id = m["match_id"]
            map_name = m["map_name"]
            starting_team = m["team"].upper() if m.get("team") else 'CT'
            
            # Load round outcomes for this match
            cur = conn.execute(
                "SELECT round_num, winner FROM rounds WHERE match_id = ? ORDER BY round_num ASC",
                (m_id,)
            )
            rounds = [dict(r) for r in cur.fetchall()]
            if not rounds:
                continue
                
            max_round = max(r["round_num"] for r in rounds)
            halftime = 15 if max_round > 24 else 12
            
            ct_rounds_played = 0
            ct_rounds_won = 0
            t_rounds_played = 0
            t_rounds_won = 0
            
            for r in rounds:
                r_num = r["round_num"]
                winner = r["winner"]
                if not winner:
                    continue
                    
                # Halftime / OT side swap checks
                if r_num <= halftime:
                    is_second_half = False
                elif r_num <= halftime * 2:
                    is_second_half = True
                else:
                    ot_round = r_num - halftime * 2 - 1
                    is_second_half = (ot_round // 3) % 2 == 1
                    
                player_team_is_ct = (starting_team == 'CT') if not is_second_half else (starting_team == 'T')
                player_team_won = (winner == 'CT') if player_team_is_ct else (winner == 'T')
                
                if player_team_is_ct:
                    ct_rounds_played += 1
                    if player_team_won:
                        ct_rounds_won += 1
                else:
                    t_rounds_played += 1
                    if player_team_won:
                        t_rounds_won += 1
                        
            total_won = ct_rounds_won + t_rounds_won
            total_played = ct_rounds_played + t_rounds_played
            is_win = 1 if total_won > total_played / 2 else 0
            
            if map_name not in maps_data:
                maps_data[map_name] = {
                    "mapName": map_name,
                    "matchesPlayed": 0,
                    "wins": 0,
                    "adrSum": 0.0,
                    "killsSum": 0,
                    "deathsSum": 0,
                    "ratingSum": 0.0,
                    "hsPctSum": 0.0,
                    "ctRoundsPlayed": 0,
                    "ctRoundsWon": 0,
                    "tRoundsPlayed": 0,
                    "tRoundsWon": 0
                }
                
            d = maps_data[map_name]
            d["matchesPlayed"] += 1
            d["wins"] += is_win
            d["adrSum"] += m.get("adr") or 0.0
            d["killsSum"] += m.get("kills") or 0
            d["deathsSum"] += m.get("deaths") or 0
            d["ratingSum"] += m.get("rating") or 0.0
            d["hsPctSum"] += m.get("hs_pct") or 0.0
            d["ctRoundsPlayed"] += ct_rounds_played
            d["ctRoundsWon"] += ct_rounds_won
            d["tRoundsPlayed"] += t_rounds_played
            d["tRoundsWon"] += t_rounds_won
            
        result = []
        for map_name, d in maps_data.items():
            played = d["matchesPlayed"]
            avg_kd = d["killsSum"] / d["deathsSum"] if d["deathsSum"] > 0 else float(d["killsSum"])
            winrate_ct = d["ctRoundsWon"] / d["ctRoundsPlayed"] if d["ctRoundsPlayed"] > 0 else 0.0
            winrate_t = d["tRoundsWon"] / d["tRoundsPlayed"] if d["tRoundsPlayed"] > 0 else 0.0
            
            result.append({
                "mapName": map_name,
                "matchesPlayed": played,
                "winRate": d["wins"] / played,
                "avgAdr": d["adrSum"] / played,
                "avgKd": avg_kd,
                "avgRating": d["ratingSum"] / played,
                "hsPercent": d["hsPctSum"] / played,
                "winRateCt": winrate_ct,
                "winRateT": winrate_t
            })
            
        return result
    finally:
        conn.close()

def get_player_trend_stats(player_name: str, limit: int = 20) -> list[dict]:
    """Retrieve historical career performance trend stats for a player."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.execute(
            "SELECT pms.match_id, m.match_date, m.map_name, pms.adr, pms.rating, pms.kills, pms.deaths, pms.accuracy "
            "FROM player_match_stats pms "
            "JOIN matches m ON pms.match_id = m.id "
            "WHERE pms.player = ? "
            "ORDER BY m.id DESC LIMIT ?",
            (player_name, limit)
        )
        rows = [dict(r) for r in cur.fetchall()]
        rows.reverse() # chronological order
        
        result = []
        for r in rows:
            kd = r["kills"] / r["deaths"] if r["deaths"] > 0 else float(r["kills"])
            result.append({
                "matchId": r["match_id"],
                "date": r["match_date"],
                "map": r["map_name"],
                "adr": r["adr"],
                "rating": r["rating"],
                "kd": kd,
                "accuracy": r["accuracy"]
            })
        return result
    finally:
        conn.close()
