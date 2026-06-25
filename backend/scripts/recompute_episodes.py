from __future__ import annotations

import argparse
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.episodes_scheduler import run_episode_recompute_once  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Recompute ready-to-read auto episode table.")
    parser.add_argument("--wells", default=None, help="Optional comma-separated well ids.")
    args = parser.parse_args()
    return 0 if run_episode_recompute_once(args.wells) else 1


if __name__ == "__main__":
    raise SystemExit(main())
