#!/usr/bin/env python
"""Download + normalise CS2 radar PNGs into the data directory.

Source data:
  * 2mlml/cs2-radar-images (GitHub) — official radar PNGs (low-res 1024×1024)
  * awpy data downloads — per-map nav meshes + visibility triangles

Outputs:
  * $DATA_DIR/maps/<map_name>.png
  * $DATA_DIR/maps/<map_name>/{nav.json, tri.bsp} (raw, parsed lazily by Rust)

Usage:
  python tools/extract_maps.py            # all active duty maps
  python tools/extract_maps.py mirage      # single map
  python tools/extract_maps.py --force     # re-download even if present

This script is idempotent: existing files are skipped unless --force.
Week 1: skeleton with the file-fetch logic stubbed. The real network
calls are added in week 6 alongside the heatmap/calibration work.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = (
    Path(os.environ["APPDATA"]) / "CS2Analyzer" / "maps"
    if os.name == "nt"
    else Path.home() / ".local" / "share" / "CS2Analyzer" / "maps"
)

ACTIVE_DUTY_MAPS = [
    "mirage",
    "inferno",
    "nuke",
    "ancient",
    "anubis",
    "dust2",
    "vertigo",
]

log = logging.getLogger("extract_maps")


# ---------------------------------------------------------------------------
# Fetchers
# ---------------------------------------------------------------------------


def fetch_radar(map_name: str, dest: Path, force: bool) -> bool:
    """Download the radar PNG for a single map.

    Week 1 stub. Returns True if the file ended up at `dest`.
    """
    if dest.exists() and not force:
        log.info("[%s] radar already present at %s", map_name, dest)
        return True
    log.warning("[%s] radar download not yet implemented (week 6)", map_name)
    return False


def fetch_navmesh(map_name: str, dest_dir: Path, force: bool) -> bool:
    """Download the navmesh for a single map via awpy.get_nav(...).

    Week 1 stub.
    """
    nav_path = dest_dir / "nav.json"
    if nav_path.exists() and not force:
        log.info("[%s] nav already present at %s", map_name, nav_path)
        return True
    log.warning("[%s] navmesh download not yet implemented (week 6)", map_name)
    return False


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument(
        "maps",
        nargs="*",
        help="Specific map names (default: all active duty maps)",
    )
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--force", action="store_true", help="Re-download even if cached")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    targets = args.maps or ACTIVE_DUTY_MAPS
    log.info("extracting %d map(s) into %s", len(targets), args.data_dir)
    args.data_dir.mkdir(parents=True, exist_ok=True)

    summary = {"ok": [], "skipped": [], "failed": []}
    for m in targets:
        radar_dest = args.data_dir / f"{m}.png"
        nav_dir = args.data_dir / m
        nav_dir.mkdir(parents=True, exist_ok=True)

        try:
            r = fetch_radar(m, radar_dest, args.force)
            n = fetch_navmesh(m, nav_dir, args.force)
            (summary["ok"] if (r and n) else summary["skipped"]).append(m)
        except Exception as e:  # noqa: BLE001
            log.exception("[%s] failed: %s", m, e)
            summary["failed"].append({"map": m, "error": str(e)})

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if not summary["failed"] else 1


if __name__ == "__main__":
    sys.exit(main())
