from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.predicted_qliq import ensure_predicted_qliq_cache  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Recompute daily predicted Q liquid cache.")
    parser.add_argument("--force", action="store_true", help="Recompute even if cache was already built today.")
    args = parser.parse_args()
    metadata = ensure_predicted_qliq_cache(force=args.force)
    print(json.dumps(metadata, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
