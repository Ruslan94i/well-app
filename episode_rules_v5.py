from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.model_params import PARAMS, get_params, reset_well_params, set_param_override  # noqa: E402


def _parse_value(raw_value: str) -> float:
    return float(raw_value.replace(",", "."))


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("Usage:")
        print("  python episode_rules_v5.py set-param <well_id> <param_key> <value>")
        print("  python episode_rules_v5.py reset <well_id>")
        return 1

    command = argv[1]
    if command == "set-param":
        if len(argv) != 5:
            print("Usage: python episode_rules_v5.py set-param <well_id> <param_key> <value>")
            return 1

        well_id, param_key, raw_value = argv[2], argv[3], argv[4]
        if param_key not in PARAMS:
            print(f"Unknown parameter: {param_key}")
            return 1

        set_param_override(well_id, param_key, _parse_value(raw_value))
        print(f"Saved override: {well_id}.{param_key}={raw_value}")
        return 0

    if command == "reset":
        if len(argv) != 3:
            print("Usage: python episode_rules_v5.py reset <well_id>")
            return 1

        reset_well_params(argv[2])
        print(f"Reset overrides for {argv[2]}")
        return 0

    if command == "show":
        if len(argv) != 3:
            print("Usage: python episode_rules_v5.py show <well_id>")
            return 1

        print(get_params(argv[2]))
        return 0

    print(f"Unknown command: {command}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
