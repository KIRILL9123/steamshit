"""CS2 Demo Analyzer — Python sidecar entry point."""

from __future__ import annotations

import sys
import traceback

from cs2_sidecar.server import run


def main() -> None:
    try:
        run()
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception:
        sys.stderr.write("sidecar crashed:\n")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
