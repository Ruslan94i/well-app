from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
import json
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.services.auto_episodes import get_candidate_auto_episode_intervals
from app.services.json_markup import load_markup_state


SAFE_PARAM_RANGES: dict[str, tuple[float, float, float]] = {
    "stop_freq_hz": (0.5, 15.0, 5.0),
    "long_stop_h": (2.0, 48.0, 12.0),
    "gdi_min_stop_h": (12.0, 96.0, 48.0),
    "gdi_total_rise_bar": (2.0, 20.0, 5.0),
    "uvch_rise_hz": (0.3, 3.0, 0.9),
    "uvch_hold_d": (2.0, 14.0, 5.0),
    "rptch_round_frac": (0.3, 0.9, 0.60),
    "per_start_n": (4.0, 20.0, 8.0),
    "nur_min_drop_bar": (1.0, 6.0, 2.0),
    "snizh_win_drop": (1.0, 10.0, 3.0),
    "rost_rise_bar": (2.0, 15.0, 5.0),
    "kprod_pulse_drop": (0.03, 0.15, 0.06),
    "kprod_pulse_drop_cyclic": (0.02, 0.12, 0.045),
    "cf_min_opz": (2.0, 6.0, 3.0),
    "degr_load_pct": (0.01, 0.10, 0.03),
    "deopt_pzab_pct": (0.01, 0.10, 0.03),
    "wct_trend_pp": (1.0, 10.0, 3.0),
    "wct_local_win": (3.0, 14.0, 5.0),
    "vgf_glf_thr": (40.0, 120.0, 70.0),
    "gf_trend_frac": (0.2, 0.8, 0.4),
    "water_supply_up_frac": (0.1, 0.5, 0.20),
}

PARAMS: dict[str, float] = {
    key: default_value for key, (_, _, default_value) in SAFE_PARAM_RANGES.items()
}
PARAMS.update(
    {
        # Internal detector constants are intentionally not exposed to users.
        "stop_min_dur_min": 30.0,
        "uvch_slow_min_d": 7.0,
        "uvch_stop_clear_d": 3.0,
        "rptch_round_min_d": 5.0,
        "per_window_d": 14.0,
        "nur_peak_search_d": 5.0,
        "nur_rise_confirm_d": 2.0,
        "nur_monotone_ratio": 0.50,
        "snizh_max_dfreq": 2.0,
        "snizh_rise_veto_bar": 2.0,
        "kprod_freq_stable_hz": 3.0,
        "kprod_trprod_min_decl": 0.05,
        "cf_win_d": 60.0,
        "cf_min_kprod": 2.0,
        "degr_run_d": 5.0,
        "degr_freq_rise_hz": 2.0,
        "deopt_qstable": 5.0,
        "wct_smooth_d": 3.0,
        "vgf_min_d": 14.0,
        "gf_trend_min_d": 21.0,
        "sppv_bdpv_min": 0.5,
        # Legacy internal defaults kept so old algorithm branches still have values.
        "nur_gate_stop_h": 12.0,
        "nur_max_d": 30.0,
        "nur_max_gap_to_post": 30.0,
        "uvch_stop_suppress_d": 2.0,
        "rptch_interday_std": 1.0,
        "rptch_osc_hz": 1.5,
        "rptch_density": 0.20,
        "snizh_seg_win_d": 45.0,
        "snizh_seg_drop_bar": 4.0,
        "snizh_win_d": 14.0,
        "per_keep_n": 3.0,
    }
)

WELL_PARAMS_PATH = settings.well_params_data_path

CLASSIFICATION_VALUE_LABELS: dict[str, str] = {
    "work": "Работа",
    "работа": "Работа",
    "stop": "Остановка",
    "остановка": "Остановка",
    "gdi": "ГДИ",
    "гди": "ГДИ",
    "uvch": "УВЧ",
    "увч": "УВЧ",
    "umch": "УМЧ",
    "умч": "УМЧ",
    "rptch": "РПТЧ",
    "рптч": "РПТЧ",
    "periodic_operation": "Периодическая работа",
    "периодическая работа": "Периодическая работа",
    "nur": "НУР",
    "nur_yes": "НУР",
    "да": "НУР",
    "pres_growth": "Рост Рпл",
    "рост рпл": "Рост Рпл",
    "pres_decline": "Снижение Рпл",
    "снижение рпл": "Снижение Рпл",
    "wct_growth": "Рост обводненности",
    "рост обводненности": "Рост обводненности",
    "wct_decline": "Снижение обводненности",
    "снижение обводненности": "Снижение обводненности",
    "kprod_growth": "Рост Кпрод",
    "рост кпрод": "Рост Кпрод",
    "kprod_decline": "Снижение Кпрод",
    "снижение кпрод": "Снижение Кпрод",
    "slozhn_fond": "Осложненный фонд",
    "осложненный фонд": "Осложненный фонд",
    "sppv": "СППВ",
    "сппв": "СППВ",
    "увеличение подачи воды": "Увеличение подачи воды",
    "vgf": "ВГФ",
    "вгф": "ВГФ",
    "рост гф": "Рост ГФ",
    "снижение гф": "Снижение ГФ",
    "deoptimization": "Деоптимизация",
    "деоптимизация": "Деоптимизация",
    "degr_yes": "Деградация ЭЦН",
    "деградация эцн": "Деградация ЭЦН",
}


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}

    try:
        raw_value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    return raw_value if isinstance(raw_value, dict) else {}


def clamp_param_value(param_key: str, value: float) -> float:
    min_value, max_value, _ = SAFE_PARAM_RANGES[param_key]
    return min(max(float(value), min_value), max_value)


def load_overrides() -> dict[str, dict[str, float]]:
    raw_overrides = _read_json(WELL_PARAMS_PATH)
    overrides: dict[str, dict[str, float]] = {}

    for target_id, raw_params in raw_overrides.items():
        if not isinstance(target_id, str) or not isinstance(raw_params, dict):
            continue

        params: dict[str, float] = {}
        for key, raw_value in raw_params.items():
            if key not in SAFE_PARAM_RANGES or not isinstance(raw_value, (int, float)):
                continue
            params[key] = clamp_param_value(key, raw_value)

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
    if param_key not in SAFE_PARAM_RANGES:
        raise KeyError(param_key)

    overrides = load_overrides()
    target_overrides = dict(overrides.get(target_id, {}))
    target_overrides[param_key] = clamp_param_value(param_key, value)
    overrides[target_id] = target_overrides
    save_overrides(overrides)
    return overrides


def replace_target_overrides(target_id: str, params: dict[str, float]) -> dict[str, dict[str, float]]:
    normalized = {
        key: clamp_param_value(key, value)
        for key, value in params.items()
        if key in SAFE_PARAM_RANGES and isinstance(value, (int, float))
    }
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


def normalize_safe_params(params: dict[str, float]) -> dict[str, float]:
    return {
        key: clamp_param_value(key, value)
        for key, value in params.items()
        if key in SAFE_PARAM_RANGES and isinstance(value, (int, float))
    }


def _normalize_label(value: object) -> str | None:
    label = str(value or "").strip()
    if not label:
        return None

    normalized = label.casefold().replace("ё", "е").strip()
    if "=" in normalized:
        normalized = normalized.split("=", 1)[1].strip()

    return CLASSIFICATION_VALUE_LABELS.get(normalized, label)


def _parse_date(value: object) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None

    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _iter_interval_days(start_value: object, end_value: object) -> list[str]:
    start = _parse_date(start_value)
    end = _parse_date(end_value)
    if start is None or end is None:
        return []
    if end < start:
        start, end = end, start

    max_days = 5000
    days: list[str] = []
    current = start
    while current <= end and len(days) < max_days:
        days.append(current.isoformat())
        current += timedelta(days=1)
    return days


def _selected_wells(scope: dict[str, Any], all_wells: set[str]) -> set[str]:
    scope_type = scope.get("type")
    if scope_type == "well":
        well = str(scope.get("well") or "").strip()
        return {well} if well else set()
    if scope_type == "field":
        field = str(scope.get("field") or "").strip()
        return {well for well in all_wells if get_field_code(well) == field} if field else set()
    if scope_type == "set":
        wells = scope.get("wells")
        return {str(well).strip() for well in wells if str(well).strip()} if isinstance(wells, list) else set()
    return set(all_wells)


def _manual_day_labels(selected: set[str]) -> dict[str, set[tuple[str, str]]]:
    state = load_markup_state()
    labels: dict[str, set[tuple[str, str]]] = defaultdict(set)

    for annotation in state.annotations:
        well_id = annotation.wellId
        if well_id not in selected:
            continue

        days = _iter_interval_days(annotation.startDate, annotation.endDate)
        if not days:
            continue

        for raw_value in annotation.classification.values():
            label = _normalize_label(raw_value)
            if not label:
                continue
            for day in days:
                labels[label].add((well_id, day))

    return labels


def _auto_day_labels(selected: set[str]) -> dict[str, set[tuple[str, str]]]:
    labels: dict[str, set[tuple[str, str]]] = defaultdict(set)

    for interval in get_candidate_auto_episode_intervals():
        well_id = str(interval.get("wellId") or "").strip()
        if well_id not in selected:
            continue

        label = _normalize_label(interval.get("label"))
        days = _iter_interval_days(interval.get("startDate"), interval.get("endDate"))
        if not label or not days:
            continue

        for day in days:
            labels[label].add((well_id, day))

    return labels


def _score_labels(
    manual_labels: dict[str, set[tuple[str, str]]],
    auto_labels: dict[str, set[tuple[str, str]]],
) -> tuple[float, dict[str, float], dict[str, int]]:
    by_category: dict[str, float] = {}
    union_sizes: dict[str, int] = {}
    total_intersection = 0
    total_union = 0

    for label in sorted(set(manual_labels) | set(auto_labels)):
        manual_points = manual_labels.get(label, set())
        auto_points = auto_labels.get(label, set())
        union = manual_points | auto_points
        if not union:
            continue

        intersection_size = len(manual_points & auto_points)
        union_size = len(union)
        by_category[label] = round(100 * intersection_size / union_size, 1)
        union_sizes[label] = union_size
        total_intersection += intersection_size
        total_union += union_size

    overall = round(100 * total_intersection / total_union, 1) if total_union else 0.0
    return overall, by_category, union_sizes


def recompute_model_quality(scope: dict[str, Any], overrides: dict[str, float]) -> dict[str, object]:
    """Compare persisted auto episodes with manual markup without running detectors."""
    safe_overrides = normalize_safe_params(overrides)
    all_wells = {
        annotation.wellId
        for annotation in load_markup_state().annotations
        if annotation.wellId
    }
    all_wells.update(
        str(interval.get("wellId") or "").strip()
        for interval in get_candidate_auto_episode_intervals()
        if str(interval.get("wellId") or "").strip()
    )

    selected = _selected_wells(scope, all_wells) or set(all_wells)
    manual_labels = _manual_day_labels(selected)
    auto_labels = _auto_day_labels(selected)
    overall, by_category, union_sizes = _score_labels(manual_labels, auto_labels)

    fields = sorted({get_field_code(well) for well in selected if well})
    rows = []
    for field in fields:
        field_wells = {well for well in selected if get_field_code(well) == field}
        field_manual = {
            label: {point for point in points if point[0] in field_wells}
            for label, points in manual_labels.items()
        }
        field_auto = {
            label: {point for point in points if point[0] in field_wells}
            for label, points in auto_labels.items()
        }
        field_overall, _, field_unions = _score_labels(field_manual, field_auto)
        rows.append(
            {
                "field": field,
                "wells": len(field_wells),
                "rows": f"{sum(field_unions.values()):,}".replace(",", " "),
                "pct": field_overall,
                "note": "сохранённые интервалы; детектор запускается офлайн",
            }
        )

    if not rows:
        rows.append(
            {
                "field": str(scope.get("field") or scope.get("well") or "Все"),
                "wells": 0,
                "rows": "0",
                "pct": 0.0,
                "note": "нет ручной или авторазметки для сравнения",
            }
        )

    # The heavy classifier is intentionally not run here. New safe thresholds are
    # saved/exported, and the scheduled offline job will produce the true "after".
    after = overall
    if safe_overrides:
        after = overall

    return {
        "overall_before": overall,
        "overall_after": after,
        "by_category_before": by_category,
        "by_category_after": by_category.copy(),
        "rows": rows,
    }
