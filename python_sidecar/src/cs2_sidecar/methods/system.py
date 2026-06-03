"""System methods: ping, version."""

from __future__ import annotations

import platform
import sys
from datetime import UTC, datetime

from cs2_sidecar import __version__


def ping(_params: dict) -> dict:
    return {"result": "pong", "ts": datetime.now(UTC).isoformat()}


def version(_params: dict) -> dict:
    return {
        "sidecar": __version__,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
    }
