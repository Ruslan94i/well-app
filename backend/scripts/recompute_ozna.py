from __future__ import annotations

import argparse
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import settings  # noqa: E402
from app.services.ozna import recompute_ozna, result_to_json  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Recompute OZNA raw measurements and session summaries.")
    parser.add_argument("--source", type=Path, default=settings.ozna_source_data_path, help="OZNA source CSV")
    parser.add_argument("--raw-out", type=Path, default=settings.ozna_raw_data_path, help="Raw normalized output CSV")
    parser.add_argument("--sessions-out", type=Path, default=settings.ozna_sessions_data_path, help="Session summary output CSV")
    parser.add_argument("--density", type=Path, default=settings.ozna_pvt_density_data_path, help="PVT density by field prefix CSV")
    args = parser.parse_args()

    result = recompute_ozna(
        source_path=args.source,
        raw_path=args.raw_out,
        sessions_path=args.sessions_out,
        density_path=args.density,
    )
    print(result_to_json(result))


if __name__ == "__main__":
    main()
