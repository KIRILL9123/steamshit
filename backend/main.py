import os
import asyncio
import logging
from typing import Optional
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import aiosqlite
from watchfiles import awatch, Change

from backend.database import (
    get_db, init_db, list_matches, get_match, delete_match,
    list_round_progression, get_utility_throws, get_heatmap_data,
    list_rounds, get_round_kills, get_round_grenades,
    get_anticheat_flags, get_coach_tips, find_match_by_hash,
    insert_parsed_demo, get_connection, get_setting, set_setting
)
from backend.parser import parse_demo, get_file_hash
from backend.analytics import run_anticheat_analysis, generate_coach_tips

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("backend.main")

app = FastAPI(title="Fragscope CS2 Demo Analyzer API")

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

watch_task: Optional[asyncio.Task] = None
current_watch_path: Optional[str] = None

async def watch_folder_loop(path: str):
    global current_watch_path
    current_watch_path = path
    log.info(f"Starting directory watcher for: {path}")
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
                            await run_anticheat_analysis(match_id)
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

async def restart_watch_folder(path: Optional[str]):
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
    watch_folder: Optional[str]

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
        await run_anticheat_analysis(match_id)
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
    await run_anticheat_analysis(match_id)
    async with get_connection() as db:
        return await get_anticheat_flags(db, match_id)

@app.get("/api/matches/{match_id}/coach_tips")
async def get_coach_tips_endpoint(
    match_id: int, 
    player: Optional[str] = Query(None), 
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
    player: Optional[str] = Query(None), 
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

@app.get("/api/settings/watch_folder")
async def get_watch_folder(db: aiosqlite.Connection = Depends(get_db)):
    path = await get_setting(db, "watch_folder")
    return {"watch_folder": path}

@app.post("/api/settings/watch_folder")
async def set_watch_folder(req: WatchSettingsRequest, db: aiosqlite.Connection = Depends(get_db)):
    if req.watch_folder:
        if not os.path.exists(req.watch_folder) or not os.path.isdir(req.watch_folder):
            raise HTTPException(status_code=400, detail="Путь не существует или не является директорией")

    await set_setting(db, "watch_folder", req.watch_folder)
    await restart_watch_folder(req.watch_folder)
    return {"status": "success", "watch_folder": req.watch_folder}
