"""JSON-lines RPC server.

The sidecar communicates with the Rust core (Tauri) over stdio using a
newline-delimited JSON protocol. One request per line in, one response
per line out. See `docs/TZ.md` §7.2 for the envelope shape.

Week 1: scaffolding only — methods are dispatched to stubs that echo a
placeholder result. Real awpy-backed implementations land in weeks 8–12.
"""

from __future__ import annotations

import json
import logging
import sys
import time
import traceback
import uuid
from collections.abc import Callable
from typing import Any

from cs2_sidecar import __version__
from cs2_sidecar.methods import (
    anticheat,
    coach,
    navmesh,
    parser,
    system,
    trends,
    visibility,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
log = logging.getLogger("sidecar")


# ---------------------------------------------------------------------------
# Dispatch table
# ---------------------------------------------------------------------------

#: Maps fully-qualified method name -> (handler, is_async_handler).
#: Handlers accept `(params: dict) -> dict` and may raise exceptions.
METHODS: dict[str, Callable[[dict], dict]] = {
    "system.ping":                   lambda p: system.ping(p),
    "system.version":                lambda p: system.version(p),
    "parser.parse_demo":             lambda p: parser.parse_demo(p),
    "visibility.compute":            lambda p: visibility.compute(p),
    "navmesh.find_path":             lambda p: navmesh.find_path(p),
    "anticheat.run_heuristic":       lambda p: anticheat.run_heuristic(p),
    "coach.generate_tips":           lambda p: coach.generate_tips(p),
    "trends.compute":                lambda p: trends.compute(p),
}


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------


def _read_request(line: str) -> dict:
    """Parse a single request envelope. Raises `ValueError` on bad input."""
    try:
        msg = json.loads(line)
    except json.JSONDecodeError as e:
        raise ValueError(f"invalid JSON: {e}") from e

    if not isinstance(msg, dict):
        raise ValueError("request must be a JSON object")
    if "id" not in msg or "method" not in msg:
        raise ValueError('request needs "id" and "method" fields')
    return msg


def _make_response(req_id: str, result: Any = None, error: dict | None = None) -> dict:
    return {
        "id": req_id,
        "ok": error is None,
        **({"result": result} if error is None else {"error": error}),
    }


def _handle(req: dict) -> dict:
    method = req.get("method", "")
    params = req.get("params") or {}
    req_id = req.get("id") or str(uuid.uuid4())

    handler = METHODS.get(method)
    if handler is None:
        return _make_response(
            req_id,
            error={"kind": "unknown_method", "message": f"unknown method: {method}"},
        )

    t0 = time.perf_counter()
    try:
        result = handler(params) if params else handler({})
    except NotImplementedError as e:
        return _make_response(
            req_id,
            error={"kind": "not_implemented", "message": str(e) or "not implemented yet"},
        )
    except Exception as e:
        log.exception("method %s raised", method)
        return _make_response(
            req_id,
            error={
                "kind": e.__class__.__name__,
                "message": str(e) or e.__class__.__name__,
                "trace": traceback.format_exc(limit=6),
            },
        )
    else:
        log.info("%s done in %.1f ms", method, (time.perf_counter() - t0) * 1000)
        return _make_response(req_id, result=result)


def run() -> None:
    """Blocking read loop. One JSON object per stdin line, one response per stdout line."""
    log.info("cs2-sidecar %s ready (pid=%d)", __version__, __getpid())

    stdin = sys.stdin
    stdout = sys.stdout
    for raw in stdin:
        line = raw.strip()
        if not line:
            continue
        try:
            req = _read_request(line)
        except ValueError as e:
            stdout.write(
                json.dumps(
                    {
                        "id": "unknown",
                        "ok": False,
                        "error": {"kind": "bad_request", "message": str(e)},
                    }
                )
                + "\n"
            )
            stdout.flush()
            continue

        resp = _handle(req)
        stdout.write(json.dumps(resp) + "\n")
        stdout.flush()


def __getpid() -> int:
    try:
        import os

        return os.getpid()
    except Exception:
        return -1
