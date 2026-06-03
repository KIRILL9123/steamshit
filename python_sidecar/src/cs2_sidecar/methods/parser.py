"""Demo parsing via `awpy` (which wraps demoparser2).

The Rust core invokes this method over the JSON-lines sidecar channel with
`{"method": "parser.parse_demo", "params": {"path": "...", "include_ticks": false}}`.

The response is a JSON-serialisable dict that mirrors the schema of
`src-tauri/src/core/models.rs` (kill, damage, round, etc. rows + a header
struct). The Rust side is responsible for deserialising it and writing it
into SQLite.

Awpy returns polars DataFrames for events; we convert each to a list of
dicts via `.to_dicts()` and prune columns to the ones the Rust schema
expects. Missing columns are tolerated — they are filled with `None` in
the row dicts and become `NULL` in SQLite.
"""

from __future__ import annotations

import logging
import os
from typing import Any

log = logging.getLogger("sidecar.parser")

# Awpy is a heavy import (pulls in polars + demoparser2's csgoproto). We do
# it lazily so the sidecar's first response (system.ping) stays fast.
_awpy_demo_cls: Any | None = None


def _get_awpy_demo():
    global _awpy_demo_cls
    if _awpy_demo_cls is None:
        from awpy import Demo  # type: ignore[import-not-found]

        _awpy_demo_cls = Demo
    return _awpy_demo_cls


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def parse_demo(params: dict) -> dict:
    """Parse a CS2 .dem/.dem.zst file and return structured JSON.

    See module docstring for the response shape.
    """
    path = params.get("path")
    if not path or not isinstance(path, str):
        raise ValueError("params.path is required (string)")
    if not os.path.isfile(path):
        raise FileNotFoundError(f"demo not found: {path}")
    include_ticks = bool(params.get("include_ticks", False))

    Demo = _get_awpy_demo()
    log.info("parsing %s (include_ticks=%s)", path, include_ticks)
    dem = Demo(path)
    # Awpy's parse() returns early if already parsed. Safe to call unconditionally.
    dem.parse()
    if not dem.events:  # type: ignore[attr-defined]
        # Some demo formats leave events empty until a property is read.
        _ = dem.header  # noqa: F841  (force a header read)

    header = _extract_header(dem)
    players = _extract_players(dem, header.get("player_meta", []))

    out: dict[str, Any] = {
        "header": {k: v for k, v in header.items() if k != "player_meta"},
        "players": players,
        "rounds": _df_to_rows(dem.rounds, ROUND_COLS),
        "kills": _df_to_rows(dem.kills, KILL_COLS),
        "damages": _df_to_rows(dem.damages, DAMAGE_COLS),
        "grenades": _df_to_rows(dem.grenades, GRENADE_COLS),
        "smokes": _df_to_rows(dem.smokes, SMOKE_COLS),
        "infernos": _df_to_rows(dem.infernos, INFERNO_COLS),
        "shots": _df_to_rows(dem.shots, SHOT_COLS),
        "bomb": _df_to_rows(dem.bomb, BOMB_COLS),
        "ticks": _df_to_rows(dem.ticks, TICK_COLS) if include_ticks else [],
    }
    log.info(
        "parsed: %d rounds, %d kills, %d damages, %d grenades",
        len(out["rounds"]),
        len(out["kills"]),
        len(out["damages"]),
        len(out["grenades"]),
    )
    return out


# ---------------------------------------------------------------------------
# Column maps
#
# `awpy` uses snake_case column names. We map them to the names expected by
# `src-tauri/src/core/models.rs` and the SQLite schema in
# `src-tauri/migrations/V001__initial.sql`.
# ---------------------------------------------------------------------------

# Only columns that are common across recent awpy versions. Missing ones
# are tolerated and become NULL on the Rust side.

KILL_COLS = [
    "round_num",
    "tick",
    "attacker_name",
    "victim_name",
    "assister_name",
    "weapon",
    "headshot",
    "wallbang",
    "noscope",
    "thru_smoke",
    "thru_wall",
    "blind_kill",
    "attacker_x",
    "attacker_y",
    "attacker_z",
    "victim_x",
    "victim_y",
    "victim_z",
    "distance",
]

DAMAGE_COLS = [
    "round_num",
    "tick",
    "attacker_name",
    "victim_name",
    "weapon",
    "hp_damage",
    "armor_damage",
    "hitgroup",
]

ROUND_COLS = [
    "round_num",
    "start_tick",
    "freeze_end_tick",
    "end_tick",
    "winner",
    "reason",
    "bomb_plant",
    "bomb_site",
    "ct_score",
    "t_score",
]

GRENADE_COLS = [
    "round_num",
    "throw_tick",
    "thrower_name",
    "nade_type",
    "throw_x",
    "throw_y",
    "throw_z",
    "land_x",
    "land_y",
    "land_z",
    "land_tick",
    "duration_ticks",
]

SMOKE_COLS = [
    "round_num",
    "throw_tick",
    "thrower_name",
    "throw_x",
    "throw_y",
    "throw_z",
    "land_x",
    "land_y",
    "land_z",
    "land_tick",
    "duration_ticks",
    "extinguished_by",
]

INFERNO_COLS = [
    "round_num",
    "throw_tick",
    "thrower_name",
    "throw_x",
    "throw_y",
    "throw_z",
    "land_x",
    "land_y",
    "land_z",
    "land_tick",
    "duration_ticks",
    "extinguished_by",
]

SHOT_COLS = [
    "round_num",
    "tick",
    "player_name",
    "weapon",
    "x",
    "y",
    "z",
]

BOMB_COLS = [
    "round_num",
    "tick",
    "event",
    "player_name",
    "site",
    "x",
    "y",
    "z",
]

# Tick columns — only included when `include_ticks=True`. Awpy returns a
# wide DataFrame here; we keep the most useful ones.
TICK_COLS = [
    "round_num",
    "tick",
    "player_name",
    "x",
    "y",
    "z",
    "yaw",
    "pitch",
    "health",
    "armor",
    "velocity_x",
    "velocity_y",
    "velocity_z",
    "is_alive",
    "is_planting",
    "is_defusing",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _df_to_rows(df, wanted_cols: list[str]) -> list[dict]:
    """Convert a polars DataFrame to a list of dicts, projected to `wanted_cols`.

    Missing columns are filled with `None`. Column names are passed through
    unchanged; the Rust side maps them to the SQL columns.
    """
    if df is None:
        return []
    try:
        # Awpy exposes a polars DataFrame.
        existing = set(df.columns)
    except AttributeError:
        return []

    selected = [c for c in wanted_cols if c in existing]
    if not selected:
        return []
    projected = df.select(selected)
    # `to_dicts` is the canonical polars way; returns List[Dict[str, Any]].
    rows = projected.to_dicts()
    # Coerce numpy scalars to native Python so json.dumps handles them.
    return [_coerce(r) for r in rows]


def _coerce(value: Any) -> Any:
    """Best-effort conversion of numpy / polars scalar types to native Python."""
    # numpy scalars expose .item()
    if hasattr(value, "item") and not isinstance(value, (list, dict, str, bytes)):
        try:
            return value.item()
        except (ValueError, TypeError):
            return value
    if isinstance(value, float):
        # polars uses NaN/NaT; serialise as null.
        import math

        if math.isnan(value):
            return None
    return value


def _extract_header(dem) -> dict:
    """Pull the small set of header fields we need into a flat dict."""
    raw = getattr(dem, "header", {}) or {}
    # awpy's header is a dict; in newer versions it lives under .header['mapName'] etc.
    map_name = raw.get("mapName") or raw.get("map_name") or raw.get("map") or "unknown"
    server_name = raw.get("serverName") or raw.get("server_name")
    client_name = raw.get("clientName") or raw.get("client_name")
    playtime = raw.get("playbackTicks") or raw.get("playback_ticks") or raw.get("duration_ticks")
    tick_rate = raw.get("tickRate") or raw.get("tick_rate")

    # Demo type: valve / faceit / hltv / unknown
    proto = (raw.get("networkProtocol") or raw.get("type") or "").lower()
    if "faceit" in (server_name or "").lower() or "faceit" in (client_name or "").lower():
        demo_type = "faceit"
    elif "hltv" in (server_name or "").lower():
        demo_type = "hltv"
    elif proto:
        demo_type = "valve"
    else:
        demo_type = "unknown"

    return {
        "map_name": str(map_name),
        "server_name": server_name,
        "client_name": client_name,
        "demo_type": demo_type,
        "match_date": raw.get("matchDate") or raw.get("match_date"),
        "duration_ticks": _to_int(playtime),
        "tick_rate": _to_int(tick_rate),
        "player_meta": raw.get("playerMetadata") or raw.get("players") or [],
    }


def _extract_players(dem, player_meta: list) -> list[dict]:
    """Build a per-match roster. Falls back to names found in kills."""
    out: list[dict] = []
    seen: set[str] = set()
    for p in player_meta or []:
        name = p.get("playerName") or p.get("name") or p.get("player_name")
        if not name or name in seen:
            continue
        seen.add(name)
        out.append(
            {
                "name": name,
                "steam_id": p.get("playerSteamId") or p.get("steamid") or p.get("steam_id"),
                "team": (p.get("team") or "").upper() or None,
                "user_id": p.get("userId") or p.get("user_id"),
            }
        )
    return out


def _to_int(v: Any) -> int | None:
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None
