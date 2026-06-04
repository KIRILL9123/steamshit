"""Demo parsing via `awpy` 2.x (which wraps demoparser2).

The Rust core invokes this method over the JSON-lines sidecar channel with
`{"method": "parser.parse_demo", "params": {"path": "...", "include_ticks": false}}`.

The response is a JSON-serialisable dict that mirrors the schema of
`src-tauri/src/core/models.rs` (kill, damage, round, etc. rows + a header
struct). The Rust side is responsible for deserialising it and writing it
into SQLite.

awpy 2.x exposes its data as polars DataFrames with column names that
differ from our SQL schema. Each `*_COLS` list below is the **source ->
output** mapping used by `_df_to_rows`:

    [
        ("awpy_column", "key_in_output_json"),
        ...
    ]

If the source column is missing in the loaded demo (older awpy / CS:GO
demo with different schema), the projection silently drops it and the
output dict's value becomes `None` on the Rust side.
"""

from __future__ import annotations

import logging
import math
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

    log.info("parsing %s (include_ticks=%s)", path, include_ticks)
    dem = _get_awpy_demo()(path)
    dem.parse()

    header = _extract_header(dem, path)
    rounds = _project_rounds(getattr(dem, "rounds", None))
    kills = _df_to_rows(getattr(dem, "kills", None), KILL_COLS)
    damages = _df_to_rows(getattr(dem, "damages", None), DAMAGE_COLS)
    # All thrown utility goes through `grenades` (aggregated from per-tick
    # trail). The dedicated `smokes` / `infernos` DataFrames describe the
    # DETONATION region (centre + start/end tick); the Rust import re-routes
    # those into the same `grenades` table which would create duplicates,
    # so we expose them as empty arrays for now. Week 5+ will add a
    # dedicated `utility_zones` table for detonation-level analytics.
    grenades = _aggregate_grenades(getattr(dem, "grenades", None))
    smokes: list[dict] = []
    infernos: list[dict] = []
    shots = _df_to_rows(getattr(dem, "shots", None), SHOT_COLS)
    bomb = _df_to_rows(getattr(dem, "bomb", None), BOMB_COLS)
    ticks = _df_to_rows(getattr(dem, "ticks", None), TICK_COLS) if include_ticks else []
    players = _extract_players(
        getattr(dem, "ticks", None),
        kills_rows=kills,
        damages_rows=damages,
    )

    # Header.duration_ticks: awpy 2 doesn't expose playbackTicks reliably.
    # Approximate as max(end_tick) across rounds; falls back to ticks max.
    if header.get("duration_ticks") is None:
        if rounds:
            max_end = max((r.get("end_tick") or 0) for r in rounds)
            if max_end > 0:
                header["duration_ticks"] = int(max_end)
        if header.get("duration_ticks") is None:
            t_df = getattr(dem, "ticks", None)
            if t_df is not None and "tick" in getattr(t_df, "columns", []):
                try:
                    header["duration_ticks"] = int(t_df["tick"].max())
                except Exception:
                    pass

    out: dict[str, Any] = {
        "header": header,
        "players": players,
        "rounds": rounds,
        "kills": kills,
        "damages": damages,
        "grenades": grenades,
        "smokes": smokes,
        "infernos": infernos,
        "shots": shots,
        "bomb": bomb,
        "ticks": ticks,
    }
    log.info(
        "parsed: %d players, %d rounds, %d kills, %d damages, %d grenades, %d smokes, %d shots",
        len(players),
        len(rounds),
        len(kills),
        len(damages),
        len(grenades),
        len(smokes),
        len(shots),
    )
    return out


# ---------------------------------------------------------------------------
# Column maps: (awpy column, output json key)
#
# The Rust side (`src-tauri/src/core/import_helpers.rs`) reads each row by
# the keys listed in the second tuple element. Keep those in sync with the
# `get(v, "...")` calls there.
# ---------------------------------------------------------------------------

KILL_COLS: list[tuple[str, str]] = [
    ("round_num", "round_num"),
    ("tick", "tick"),
    ("attacker_name", "attacker_name"),
    ("victim_name", "victim_name"),
    ("assister_name", "assister_name"),
    ("weapon", "weapon"),
    ("headshot", "headshot"),
    # Awpy 2 names: penetrated (wall pen count), thrusmoke, attackerblind, noscope
    ("penetrated", "wallbang"),
    ("noscope", "noscope"),
    ("thrusmoke", "thru_smoke"),
    # awpy 2 has no separate thru_wall flag; we reuse penetrated > 0
    ("penetrated", "thru_wall"),
    ("attackerblind", "blind_kill"),
    ("attacker_X", "attacker_x"),
    ("attacker_Y", "attacker_y"),
    ("attacker_Z", "attacker_z"),
    ("victim_X", "victim_x"),
    ("victim_Y", "victim_y"),
    ("victim_Z", "victim_z"),
    ("distance", "distance"),
]

DAMAGE_COLS: list[tuple[str, str]] = [
    ("round_num", "round_num"),
    ("tick", "tick"),
    ("attacker_name", "attacker_name"),
    ("victim_name", "victim_name"),
    ("weapon", "weapon"),
    ("dmg_health", "hp_damage"),
    ("dmg_armor", "armor_damage"),
    ("hitgroup", "hitgroup"),
]

# Smokes/infernos in awpy 2 carry a start/end tick + thrower position +
# detonation centre. We treat the thrower spot as "throw" and the centre
# as "land" for our schema.
SMOKE_COLS: list[tuple[str, str]] = [
    ("round_num", "round_num"),
    ("start_tick", "throw_tick"),
    ("thrower_name", "thrower_name"),
    ("thrower_X", "throw_x"),
    ("thrower_Y", "throw_y"),
    ("thrower_Z", "throw_z"),
    ("X", "land_x"),
    ("Y", "land_y"),
    ("Z", "land_z"),
    ("end_tick", "land_tick"),
]

INFERNO_COLS: list[tuple[str, str]] = list(SMOKE_COLS)  # identical schema

SHOT_COLS: list[tuple[str, str]] = [
    ("round_num", "round_num"),
    ("tick", "tick"),
    ("player_name", "player_name"),
    ("weapon", "weapon"),
    ("player_X", "x"),
    ("player_Y", "y"),
    ("player_Z", "z"),
]

BOMB_COLS: list[tuple[str, str]] = [
    ("round_num", "round_num"),
    ("tick", "tick"),
    ("event", "event"),
    ("name", "player_name"),
    ("bombsite", "site"),
    ("X", "x"),
    ("Y", "y"),
    ("Z", "z"),
]

# Ticks — default awpy projection. Yaw/pitch/armor/velocity/is_alive require
# explicit `player_props=[...]` at parse-time; week 5+ will request them.
TICK_COLS: list[tuple[str, str]] = [
    ("round_num", "round_num"),
    ("tick", "tick"),
    ("name", "player_name"),
    ("X", "x"),
    ("Y", "y"),
    ("Z", "z"),
    ("health", "health"),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _df_to_rows(df, col_map: list[tuple[str, str]]) -> list[dict]:
    """Project a polars DataFrame to a list of dicts using `col_map`.

    `col_map` is a list of `(source_column, output_key)` tuples. Columns
    missing from `df` are silently dropped (output dict keys are absent).
    Numpy/polars scalars are coerced to native Python.
    """
    if df is None:
        return []
    try:
        existing = set(df.columns)
    except AttributeError:
        return []

    selected_src = []
    seen = set()
    for src, _out in col_map:
        if src in existing and src not in seen:
            selected_src.append(src)
            seen.add(src)
    if not selected_src:
        return []

    projected = df.select(selected_src)
    raw_rows = projected.to_dicts()

    out_rows: list[dict] = []
    for r in raw_rows:
        out: dict[str, Any] = {}
        for src, out_key in col_map:
            if src not in r:
                continue
            out[out_key] = _coerce(r[src])
        out_rows.append(out)
    return out_rows


def _coerce(value: Any) -> Any:
    """Best-effort conversion of numpy / polars scalar types to native Python."""
    if value is None:
        return None
    if hasattr(value, "item") and not isinstance(value, (list, dict, str, bytes)):
        try:
            value = value.item()
        except (ValueError, TypeError):
            return value
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
    return value


def _project_rounds(df) -> list[dict]:
    """Map awpy's rounds DataFrame to our schema, computing running scores."""
    if df is None:
        return []
    try:
        cols = set(df.columns)
    except AttributeError:
        return []

    base_map: list[tuple[str, str]] = [
        ("round_num", "round_num"),
        ("start", "start_tick"),
        ("freeze_end", "freeze_end_tick"),
        ("end", "end_tick"),
        ("official_end", "official_end_tick"),
        ("winner", "winner"),
        ("reason", "reason"),
        ("bomb_plant", "bomb_plant"),
        ("bomb_site", "bomb_site"),
    ]
    rows = _df_to_rows(df, base_map)
    # Sort by round_num so the running score is correct.
    rows.sort(key=lambda r: r.get("round_num") or 0)
    ct = 0
    t = 0
    for r in rows:
        winner = (r.get("winner") or "").upper()
        if winner == "CT":
            ct += 1
        elif winner in ("T", "TERRORIST"):
            t += 1
        r["ct_score"] = ct
        r["t_score"] = t
    _ = cols  # silence "unused" — kept for future schema-version checks
    return rows


def _aggregate_grenades(df) -> list[dict]:
    """Awpy's `grenades` DataFrame is **per-tick trail positions** of every
    in-flight projectile (millions of rows). Collapse to one row per throw
    keyed by `entity_id`, taking the first/last tick as throw/land.
    """
    if df is None:
        return []
    needed = {"entity_id", "round_num", "tick", "X", "Y", "Z", "thrower", "grenade_type"}
    try:
        cols = set(df.columns)
    except AttributeError:
        return []
    if not needed.issubset(cols):
        return []

    # Use polars groupby for speed (the trail is often 1M+ rows).
    try:
        import polars as pl
    except ImportError:
        return []

    try:
        grouped = (
            df.sort(["entity_id", "tick"])
            .group_by("entity_id", maintain_order=True)
            .agg(
                [
                    pl.col("round_num").first().alias("round_num"),
                    pl.col("tick").first().alias("throw_tick"),
                    pl.col("tick").last().alias("land_tick"),
                    pl.col("X").first().alias("throw_x"),
                    pl.col("Y").first().alias("throw_y"),
                    pl.col("Z").first().alias("throw_z"),
                    pl.col("X").last().alias("land_x"),
                    pl.col("Y").last().alias("land_y"),
                    pl.col("Z").last().alias("land_z"),
                    pl.col("thrower").first().alias("thrower_name"),
                    pl.col("grenade_type").first().alias("nade_type"),
                ]
            )
        )
    except Exception as e:
        log.warning("grenade aggregation failed: %s", e)
        return []

    rows = grouped.to_dicts()
    out: list[dict] = []
    for r in rows:
        throw = r.get("throw_tick") or 0
        land = r.get("land_tick") or 0
        r["duration_ticks"] = max(0, int(land - throw))
        r["nade_type"] = _normalise_nade_type(r.get("nade_type"))
        # Drop entity_id from output (not in our SQL schema).
        r.pop("entity_id", None)
        out.append({k: _coerce(v) for k, v in r.items()})
    return out


def _normalise_nade_type(t: Any) -> str:
    if not t:
        return "smoke"
    s = str(t).lower()
    if "smoke" in s:
        return "smoke"
    if "flash" in s:
        return "flash"
    if "molot" in s:
        return "molotov"
    if "inc" in s:
        return "incendiary"
    if "decoy" in s:
        return "decoy"
    if "he" in s or "explos" in s:
        return "he"
    return s


def _extract_header(dem, demo_path: str) -> dict:
    """Pull the small set of header fields we need into a flat dict."""
    raw = getattr(dem, "header", {}) or {}

    map_name = (
        raw.get("map_name")
        or raw.get("mapName")
        or raw.get("map")
        or getattr(dem, "map_name", None)
        or "unknown"
    )
    server_name = raw.get("server_name") or raw.get("serverName")
    client_name = raw.get("client_name") or raw.get("clientName")

    # Demo type heuristic: server/client name keywords.
    sn = (server_name or "").lower()
    cn = (client_name or "").lower()
    if "faceit" in sn or "faceit" in cn:
        demo_type = "faceit"
    elif "hltv" in sn or "hltv" in cn:
        demo_type = "hltv"
    elif "valve" in sn or "valve" in cn or raw.get("demo_version_name"):
        demo_type = "valve"
    else:
        demo_type = "unknown"

    # Match date — awpy doesn't expose it; fall back to file mtime (UTC).
    match_date: str | None = None
    try:
        import datetime as _dt

        st = os.stat(demo_path)
        match_date = _dt.datetime.fromtimestamp(st.st_mtime, tz=_dt.UTC).isoformat()
    except OSError:
        match_date = None

    return {
        "map_name": str(map_name),
        "server_name": server_name,
        "client_name": client_name,
        "demo_type": demo_type,
        "match_date": match_date,
        "duration_ticks": _to_int(
            raw.get("playback_ticks") or raw.get("playbackTicks") or raw.get("duration_ticks")
        ),
        "tick_rate": _to_int(raw.get("tick_rate") or raw.get("tickRate")) or 64,
    }


def _extract_players(ticks_df, kills_rows: list[dict], damages_rows: list[dict]) -> list[dict]:
    """Build the per-match roster.

    Awpy 2 doesn't expose `dem.players` or `header.playerMetadata`. We
    derive the roster from (in order of preference):
        1. unique `(name, steamid, side)` in the ticks DataFrame
        2. unique attacker/victim names in kills + damages (no steam id /
           side info, used as a last resort)

    For each player we record the **first non-spectator side** seen, which
    matches CT/T allocation at round 1 (before any half-time swap).
    """
    seen: dict[str, dict] = {}

    if ticks_df is not None:
        try:
            cols = set(ticks_df.columns)
        except AttributeError:
            cols = set()
        if {"name", "steamid", "side", "round_num"}.issubset(cols):
            try:
                # Project once; iterate as dict rows (small set after distinct).
                small = ticks_df.select(["name", "steamid", "side", "round_num"]).unique()
                for r in small.to_dicts():
                    name = r.get("name")
                    if not name:
                        continue
                    side = (r.get("side") or "").upper()
                    rn = r.get("round_num") or 0
                    entry = seen.get(name)
                    if entry is None:
                        seen[name] = {
                            "name": name,
                            "steam_id": str(r.get("steamid"))
                            if r.get("steamid") is not None
                            else None,
                            "team": side if side in ("CT", "T") else None,
                            "user_id": None,
                            "_first_round": rn,
                        }
                    else:
                        # Keep the earliest non-empty side.
                        if not entry.get("team") and side in ("CT", "T"):
                            entry["team"] = side
                        if rn < entry.get("_first_round", 0):
                            entry["_first_round"] = rn
                            if side in ("CT", "T"):
                                entry["team"] = side
            except Exception as e:
                log.warning("roster from ticks failed: %s", e)

    # Fallback: derive names from kills + damages (no team info).
    if not seen:
        names = set()
        for r in kills_rows:
            n = r.get("attacker_name") or r.get("victim_name")
            if n:
                names.add(n)
        for r in damages_rows:
            n = r.get("attacker_name") or r.get("victim_name")
            if n:
                names.add(n)
        for n in names:
            seen[n] = {"name": n, "steam_id": None, "team": None, "user_id": None}

    # Strip helper fields, sort for deterministic output.
    out = []
    for v in seen.values():
        v.pop("_first_round", None)
        if v.get("team") is None:
            v["team"] = None  # Rust side falls back to "Spectator"
        out.append(v)
    out.sort(key=lambda p: (p.get("team") or "Z", p["name"]))
    return out


def _to_int(v: Any) -> int | None:
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None
