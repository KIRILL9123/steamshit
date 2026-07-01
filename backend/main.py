import os
import logging
from typing import Optional
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import aiosqlite

from backend.database import (
    get_db, init_db, list_matches, get_match, delete_match,
    list_round_progression, get_utility_throws, get_heatmap_data,
    list_rounds, get_round_kills, get_round_grenades,
    get_anticheat_flags, get_coach_tips, find_match_by_hash,
    insert_parsed_demo, get_connection
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

@app.on_event("startup")
async def startup():
    """Initialise the DB on startup."""
    await init_db()

# Pydantic models
class ImportRequest(BaseModel):
    path: str

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

    async with await get_connection() as db:
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
    async with await get_connection() as db:
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
    async with await get_connection() as db:
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
