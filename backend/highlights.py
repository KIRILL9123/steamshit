import sqlite3
import os
import subprocess
import logging

log = logging.getLogger("uvicorn.error")
DB_PATH = "fragscope.db"

def detect_highlights(match_id: int) -> list[dict]:
    """Identify significant highlights (3K/4K/5K rounds) in a match."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        # Confirm match exists
        cur = conn.execute("SELECT id FROM matches WHERE id = ?", (match_id,))
        if not cur.fetchone():
            return []

        # Fetch round mappings
        cur = conn.execute("SELECT id, round_num FROM rounds WHERE match_id = ? ORDER BY round_num ASC", (match_id,))
        rounds = {r["id"]: r["round_num"] for r in cur.fetchall()}

        # Fetch kills
        cur = conn.execute(
            "SELECT tick, round_id, attacker, victim FROM kills WHERE match_id = ? ORDER BY tick ASC",
            (match_id,)
        )
        kill_rows = [dict(r) for r in cur.fetchall()]

        # Group kills by round and attacker
        round_attacker_kills = {}
        for k in kill_rows:
            rid = k["round_id"]
            att = k["attacker"]
            if not rid or not att:
                continue
            if rid not in round_attacker_kills:
                round_attacker_kills[rid] = {}
            if att not in round_attacker_kills[rid]:
                round_attacker_kills[rid][att] = []
            round_attacker_kills[rid][att].append(k)

        highlights_found = []
        for rid, att_kills in round_attacker_kills.items():
            r_num = rounds.get(rid)
            if not r_num:
                continue

            for att, kills_in_round in att_kills.items():
                cnt = len(kills_in_round)
                if cnt >= 3:
                    # Multi-kill highlight!
                    start_tick = kills_in_round[0]["tick"] - 320  # ~5 seconds before first kill
                    end_tick = kills_in_round[-1]["tick"] + 320   # ~5 seconds after last kill

                    description = f"{cnt}K round by {att}"
                    highlights_found.append({
                        "round_num": r_num,
                        "player": att,
                        "type": f"{cnt}K",
                        "start_tick": start_tick,
                        "end_tick": end_tick,
                        "tick": kills_in_round[0]["tick"],
                        "description": description
                    })

        return sorted(highlights_found, key=lambda x: x["round_num"])
    finally:
        conn.close()

def cut_highlight_clips(match_id: int, video_path: str) -> list[dict]:
    """Generate highlight clips from a video recording of the match using FFmpeg."""
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file not found at: {video_path}")

    highlights = detect_highlights(match_id)
    if not highlights:
        return []

    # Get tick rate
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        # CS2 demos are always 64 tick
        tick_rate = 64
        
        # Ensure output directory exists
        os.makedirs("output", exist_ok=True)
        
        cut_clips = []
        for h in highlights:
            start_sec = max(0.0, float(h["start_tick"]) / tick_rate)
            duration = float(h["end_tick"] - h["start_tick"]) / tick_rate
            if duration <= 0:
                duration = 15.0  # default 15s

            clean_player = "".join(c for c in h["player"] if c.isalnum() or c in ("-", "_"))
            clip_filename = f"match_{match_id}_round_{h['round_num']}_{clean_player}_{h['type']}.mp4"
            clip_filepath = os.path.join("output", clip_filename)

            # Run ffmpeg command
            cmd = [
                "ffmpeg", "-y",
                "-ss", f"{start_sec:.2f}",
                "-i", video_path,
                "-t", f"{duration:.2f}",
                "-c:v", "libx264", "-c:a", "aac", "-crf", "23", "-preset", "veryfast",
                clip_filepath
            ]
            try:
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                
                # Check if already exists in DB
                cur_check = conn.execute(
                    "SELECT id FROM highlight_clips WHERE match_id = ? AND clip_path = ?",
                    (match_id, clip_filename)
                )
                if not cur_check.fetchone():
                    conn.execute(
                        "INSERT INTO highlight_clips (match_id, round_num, player, type, clip_path, description) "
                        "VALUES (?, ?, ?, ?, ?, ?)",
                        (match_id, h["round_num"], h["player"], h["type"], clip_filename, h["description"])
                    )
                
                cut_clips.append({
                    "round_num": h["round_num"],
                    "player": h["player"],
                    "type": h["type"],
                    "clip_path": clip_filename,
                    "description": h["description"]
                })
            except Exception as e:
                log.error(f"Failed to cut clip for round {h['round_num']}: {e}")
                
        conn.commit()
        return cut_clips
    finally:
        conn.close()

def get_highlight_clips(match_id: int) -> list[dict]:
    """Retrieve already generated highlight clips for a match."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.execute(
            "SELECT round_num, player, type, clip_path, description, created_at "
            "FROM highlight_clips WHERE match_id = ? ORDER BY round_num ASC",
            (match_id,)
        )
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()
