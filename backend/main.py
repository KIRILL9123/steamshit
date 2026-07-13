import asyncio
import logging
import os

import aiosqlite
from backend.analytics import generate_coach_tips, run_anticheat_analysis
from backend.database import (
    delete_match,
    find_match_by_hash,
    get_anticheat_flags,
    get_coach_tips,
    get_connection,
    get_db,
    get_heatmap_data,
    get_match,
    get_round_grenades,
    get_round_kills,
    get_round_movement,
    get_setting,
    get_utility_throws,
    init_db,
    insert_parsed_demo,
    list_matches,
    list_round_progression,
    list_rounds,
    set_setting,
)
from backend.parser import get_file_hash, parse_demo
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from watchfiles import Change, awatch

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("uvicorn.error")

app = FastAPI(title="Fragscope CS2 Demo Analyzer API")

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

watch_task: asyncio.Task | None = None
current_watch_path: str | None = None

async def scan_and_import_folder(path: str):
    """Scan folder for any .dem or .dem.zst files and import them if not already in the database."""
    log.info(f"Scanning watch folder for existing demos: {path}")
    if not os.path.exists(path) or not os.path.isdir(path):
        return

    try:
        for filename in os.listdir(path):
            if filename.endswith(".dem") or filename.endswith(".dem.zst"):
                filepath = os.path.join(path, filename)
                if os.path.isdir(filepath):
                    continue
                try:
                    file_hash = get_file_hash(filepath)
                    file_size = os.path.getsize(filepath)
                    async with get_connection() as db:
                        existing = await find_match_by_hash(db, file_hash)
                        if existing:
                            continue

                        log.info(f"Auto-importing existing demo from scan: {filepath}")
                        parsed_data = parse_demo(filepath, include_ticks=True)
                        match_id = await insert_parsed_demo(db, parsed_data, filepath, file_hash, file_size)
                        await run_anticheat_analysis(match_id, parsed_data.get("ticks_df"))
                        await generate_coach_tips(match_id)
                        log.info(f"Auto-imported existing match ID: {match_id}")
                except Exception as e:
                    log.error(f"Error auto-importing existing demo {filepath}: {e}")
    except Exception as e:
        log.error(f"Error scanning watch folder {path}: {e}")

async def watch_folder_loop(path: str):
    global current_watch_path
    current_watch_path = path
    log.info(f"Starting directory watcher for: {path}")

    # Run initial scan for existing demos
    await scan_and_import_folder(path)

    try:
        async for changes in awatch(path):
            for change_type, filepath in changes:
                if change_type == Change.added and (filepath.endswith(".dem") or filepath.endswith(".dem.zst")):
                    log.info(f"Directory watcher detected new demo: {filepath}")
                    await asyncio.sleep(2)  # Wait for file copy/write to finish
                    try:
                        file_hash = get_file_hash(filepath)
                        file_size = os.path.getsize(filepath)
                        async with get_connection() as db:
                            existing = await find_match_by_hash(db, file_hash)
                            if existing:
                                log.info(f"Demo already imported (deduplicated): {filepath}")
                                continue

                            log.info(f"Auto-importing demo: {filepath}")
                            parsed_data = parse_demo(filepath, include_ticks=True)
                            match_id = await insert_parsed_demo(db, parsed_data, filepath, file_hash, file_size)
                            await run_anticheat_analysis(match_id, parsed_data.get("ticks_df"))
                            await generate_coach_tips(match_id)
                            log.info(f"Auto-imported match ID: {match_id}")
                    except Exception as e:
                        log.error(f"Error during auto-import for {filepath}: {e}")
    except asyncio.CancelledError:
        log.info(f"Directory watcher task cancelled for: {path}")
        current_watch_path = None
    except Exception as e:
        log.error(f"Error in directory watcher: {e}")
        current_watch_path = None

async def restart_watch_folder(path: str | None):
    global watch_task, current_watch_path
    if watch_task:
        log.info("Stopping existing directory watcher")
        watch_task.cancel()
        try:
            await watch_task
        except asyncio.CancelledError:
            pass
        watch_task = None
        current_watch_path = None

    if path and os.path.exists(path) and os.path.isdir(path):
        watch_task = asyncio.create_task(watch_folder_loop(path))
    else:
        if path:
            log.warning(f"Watch folder path does not exist or is not a directory: {path}")

@app.on_event("startup")
async def startup():
    """Initialise the DB on startup and start folder watcher if configured."""
    await init_db()
    async with get_connection() as db:
        watch_path = await get_setting(db, "watch_folder")
        if watch_path:
            await restart_watch_folder(watch_path)

@app.on_event("shutdown")
async def shutdown():
    """Clean up background tasks on shutdown."""
    await restart_watch_folder(None)

# Pydantic models
class ImportRequest(BaseModel):
    path: str

class WatchSettingsRequest(BaseModel):
    watch_folder: str | None

# Endpoints
@app.get("/api/ping")
def ping():
    return "pong"

@app.get("/api/app_info")
def app_info():
    return {
        "name": "CS2 Analyzer",
        "version": "0.1.2",
        "data_dir": os.path.abspath("."),
        "db_path": os.path.abspath("fragscope.db"),
        "backend": "FastAPI + demoparser2",
        "sidecar_alive": True
    }

@app.get("/api/matches")
async def get_matches_endpoint(db: aiosqlite.Connection = Depends(get_db)):
    return await list_matches(db)

@app.get("/api/matches/{match_id}")
async def get_match_detail_endpoint(match_id: int, db: aiosqlite.Connection = Depends(get_db)):
    detail = await get_match(db, match_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Match not found")
    return detail

@app.delete("/api/matches/{match_id}")
async def delete_match_endpoint(match_id: int, db: aiosqlite.Connection = Depends(get_db)):
    await delete_match(db, match_id)
    return {"status": "success"}

@app.post("/api/matches/import")
async def import_match_endpoint(req: ImportRequest):
    if not os.path.exists(req.path):
        raise HTTPException(status_code=404, detail=f"Demo file not found at: {req.path}")

    file_hash = get_file_hash(req.path)
    file_size = os.path.getsize(req.path)

    async with get_connection() as db:
        # Check deduplication
        existing = await find_match_by_hash(db, file_hash)
        if existing:
            # Match detail format
            detail = await get_match(db, existing["id"])
            return detail["header"]

        # Parse demo
        parsed_data = parse_demo(req.path, include_ticks=True)

        # Save to DB
        match_id = await insert_parsed_demo(db, parsed_data, req.path, file_hash, file_size)

        # Run anticheat & coaching
        await run_anticheat_analysis(match_id, parsed_data.get("ticks_df"))
        await generate_coach_tips(match_id)

        # Fetch and return match header
        detail = await get_match(db, match_id)
        return detail["header"]

@app.get("/api/matches/{match_id}/round_progression")
async def get_round_progression_endpoint(match_id: int, db: aiosqlite.Connection = Depends(get_db)):
    return await list_round_progression(db, match_id)

@app.get("/api/matches/{match_id}/utility_throws")
async def get_utility_throws_endpoint(match_id: int, db: aiosqlite.Connection = Depends(get_db)):
    return await get_utility_throws(db, match_id)

@app.get("/api/matches/{match_id}/anticheat_flags")
async def get_anticheat_flags_endpoint(match_id: int, db: aiosqlite.Connection = Depends(get_db)):
    flags = await get_anticheat_flags(db, match_id)
    # Map model enum values to match expectations if needed
    return [
        {
            "id": f["id"],
            "matchId": f["matchId"],
            "player": f["player"],
            "heuristic": f["heuristic"],
            "severity": f["severity"],
            "evidenceCount": f["evidenceCount"],
            "detailsJson": f["detailsJson"]
        }
        for f in flags
    ]

@app.post("/api/matches/{match_id}/compute_anticheat")
async def compute_anticheat_endpoint(match_id: int):
    # Run analysis
    try:
        await run_anticheat_analysis(match_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    async with get_connection() as db:
        return await get_anticheat_flags(db, match_id)

@app.get("/api/matches/{match_id}/coach_tips")
async def get_coach_tips_endpoint(
    match_id: int,
    player: str | None = Query(None),
    db: aiosqlite.Connection = Depends(get_db)
):
    return await get_coach_tips(db, match_id, player)

@app.post("/api/matches/{match_id}/regenerate_coach_tips")
async def regenerate_coach_tips_endpoint(match_id: int):
    # Re-run coaching tips
    await generate_coach_tips(match_id)
    async with get_connection() as db:
        return await get_coach_tips(db, match_id, None)

@app.get("/api/matches/{match_id}/heatmap_data")
async def get_heatmap_data_endpoint(
    match_id: int,
    player: str | None = Query(None),
    db: aiosqlite.Connection = Depends(get_db)
):
    return await get_heatmap_data(db, match_id, player)

@app.get("/api/matches/{match_id}/rounds")
async def get_rounds_endpoint(match_id: int, db: aiosqlite.Connection = Depends(get_db)):
    return await list_rounds(db, match_id)

@app.get("/api/rounds/{round_id}/kills")
async def get_round_kills_endpoint(round_id: int, db: aiosqlite.Connection = Depends(get_db)):
    return await get_round_kills(db, round_id)

@app.get("/api/rounds/{round_id}/grenades")
async def get_round_grenades_endpoint(round_id: int, db: aiosqlite.Connection = Depends(get_db)):
    return await get_round_grenades(db, round_id)

@app.get("/api/rounds/{round_id}/movement")
async def get_round_movement_endpoint(round_id: int, db: aiosqlite.Connection = Depends(get_db)):
    return await get_round_movement(db, round_id)

def autodetect_cs2_demos_path() -> str | None:
    """Search for the standard CS2 replays directory in Steam installations."""
    if os.name == "nt":
        import winreg
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam")
            steam_path, _ = winreg.QueryValueEx(key, "InstallPath")
            winreg.CloseKey(key)
            if steam_path:
                candidate = os.path.join(steam_path, "steamapps", "common", "Counter-Strike Global Offensive", "game", "csgo", "replays")
                if os.path.exists(candidate) and os.path.isdir(candidate):
                    return candidate
        except Exception:
            pass

    # Common default locations
    default_paths = [
        r"C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive\game\csgo\replays",
        r"C:\Program Files\Steam\steamapps\common\Counter-Strike Global Offensive\game\csgo\replays",
    ]
    for p in default_paths:
        if os.path.exists(p) and os.path.isdir(p):
            return p
    return None

@app.get("/api/settings/watch_folder")
async def get_watch_folder(db: aiosqlite.Connection = Depends(get_db)):
    path = await get_setting(db, "watch_folder")
    suggested = autodetect_cs2_demos_path()
    return {"watch_folder": path, "suggested_folder": suggested}

@app.post("/api/settings/watch_folder")
async def set_watch_folder(req: WatchSettingsRequest, db: aiosqlite.Connection = Depends(get_db)):
    if req.watch_folder:
        if not os.path.exists(req.watch_folder) or not os.path.isdir(req.watch_folder):
            raise HTTPException(status_code=400, detail="Путь не существует или не является директорией")

    await set_setting(db, "watch_folder", req.watch_folder)
    await restart_watch_folder(req.watch_folder)
    return {"status": "success", "watch_folder": req.watch_folder}


@app.get("/api/players")
async def get_players_endpoint(db: aiosqlite.Connection = Depends(get_db)):
    async with db.execute("SELECT DISTINCT player FROM player_match_stats WHERE player IS NOT NULL AND player != '' ORDER BY player ASC") as cursor:
        rows = await cursor.fetchall()
        return [r[0] for r in rows]


@app.get("/api/players/{player_name}/map-stats")
async def get_player_map_stats_endpoint(player_name: str):
    from backend.cross_match import get_player_map_stats
    return get_player_map_stats(player_name)


@app.get("/api/players/{player_name}/trend")
async def get_player_trend_endpoint(player_name: str, limit: int = Query(20, ge=1, le=100)):
    from backend.cross_match import get_player_trend_stats
    return get_player_trend_stats(player_name, limit)
