from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.core.config import settings


PARAMS: dict[str, float] = {
    "nur_gate_stop_h": 12.0,
    "nur_min_drop_bar": 2.0,
    "nur_max_d": 30.0,
    "nur_max_gap_to_post": 30.0,
    "uvch_stop_suppress_d": 2.0,
    "uvch_rise_hz": 0.3,
    "rptch_interday_std": 1.0,
    "rptch_osc_hz": 1.5,
    "rptch_density": 0.20,
    "snizh_seg_win_d": 45.0,
    "snizh_seg_drop_bar": 4.0,
    "snizh_win_d": 14.0,
    "snizh_win_drop": 3.0,
    "stop_freq_hz": 5.0,
    "stop_min_dur_min": 30.0,
    "long_stop_h": 12.0,
    "per_window_d": 14.0,
    "per_start_n": 8.0,
    "per_keep_n": 3.0,
}

WELL_PARAMS_PATH = settings.well_params_data_path


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}

    try:
        raw_value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    return raw_value if isinstance(raw_value, dict) else {}


def load_overrides() -> dict[str, dict[str, float]]:
    raw_overrides = _read_json(WELL_PARAMS_PATH)
    overrides: dict[str, dict[str, float]] = {}

    for target_id, raw_params in raw_overrides.items():
        if not isinstance(target_id, str) or not isinstance(raw_params, dict):
            continue

        params: dict[str, float] = {}
        for key, raw_value in raw_params.items():
            if key not in PARAMS or not isinstance(raw_value, (int, float)):
                continue
            params[key] = float(raw_value)

        if params:
            overrides[target_id] = params

    return overrides


def save_overrides(overrides: dict[str, dict[str, float]]) -> None:
    WELL_PARAMS_PATH.parent.mkdir(parents=True, exist_ok=True)
    WELL_PARAMS_PATH.write_text(
        json.dumps(overrides, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def get_field_code(well_id: str) -> str:
    return well_id.split("_", 1)[0].strip()


def get_params(well_id: str) -> dict[str, float]:
    params = PARAMS.copy()
    overrides = load_overrides()
    field_code = get_field_code(well_id)

    for target_id in ("all", field_code, well_id):
        params.update(overrides.get(target_id, {}))

    return params


def set_param_override(target_id: str, param_key: str, value: float) -> dict[str, dict[str, float]]:
    if param_key not in PARAMS:
        raise KeyError(param_key)

    overrides = load_overrides()
    target_overrides = dict(overrides.get(target_id, {}))
    target_overrides[param_key] = float(value)
    overrides[target_id] = target_overrides
    save_overrides(overrides)
    return overrides


def replace_target_overrides(target_id: str, params: dict[str, float]) -> dict[str, dict[str, float]]:
    normalized = {key: float(value) for key, value in params.items() if key in PARAMS}
    overrides = load_overrides()

    if normalized:
        overrides[target_id] = normalized
    else:
        overrides.pop(target_id, None)

    save_overrides(overrides)
    return overrides


def reset_well_params(target_id: str) -> dict[str, dict[str, float]]:
    overrides = load_overrides()
    overrides.pop(target_id, None)
    save_overrides(overrides)
    return overrides
