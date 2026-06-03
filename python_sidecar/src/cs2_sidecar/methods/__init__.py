"""Sidecar methods.

`parser` (week 4) parses .dem files via awpy and returns JSON for the
Rust core. The others are stubs that land in weeks 8–12.
"""

from . import anticheat, coach, navmesh, parser, system, trends, visibility

__all__ = [
    "anticheat",
    "coach",
    "navmesh",
    "parser",
    "system",
    "trends",
    "visibility",
]
