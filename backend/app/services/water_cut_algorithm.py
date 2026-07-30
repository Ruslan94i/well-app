from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

import polars as pl

from app.core.config import settings
from app.services.adaptive_water_cut import build_water_cut_line


logger = logging.getLogger(__name__)

# Canonical "well is running" gate reused from this pipeline's pre-existing
# determination (do not invent a second independent running/stop definition).
RUNNING_FREQ_MIN_HZ = 10.0
RUNNING_POWER_MIN_KW = 2.0

# Field names always exposed by add_water_cut_algorithm, even when there is no
# HAL data at all for a well/frame (as all-null columns, never omitted).
_FLOAT_FIELD_NAMES = ("water_cut_hal_daily", "water_cut_algo")
_STRING_FIELD_NAMES = ("water_cut_mode",)


def _empty_daily_fields() -> tuple[dict[str, dict], dict[str, dict]]:
    return {name: {} for name in _FLOAT_FIELD_NAMES}, {name: {} for name in _STRING_FIELD_NAMES}


def _path_cache_key(path: Path) -> tuple[str, int, int]:
    if not path.exists():
        return str(path), 0, 0
    stat = path.stat()
    return str(path), stat.st_mtime_ns, stat.st_size


@lru_cache(maxsize=4)
def _load_hal_raw_frame(path: str, path_mtime_ns: int, path_size: int) -> Any:
    """Raw (well_id, timestamp, value) ХАЛ measurements — intentionally NOT
    pre-aggregated to daily here, because the running-time gate must be applied
    per measurement before daily aggregation, not after."""
    import pandas as pd  # type: ignore

    if path_size <= 0:
        return pd.DataFrame(columns=["well_id", "timestamp", "hal_value"])

    source = Path(path)
    if not source.exists():
        return pd.DataFrame(columns=["well_id", "timestamp", "hal_value"])

    hal = pd.read_csv(source, sep=";")
    if len(hal.columns) == 1:
        hal = pd.read_csv(source)

    value_column = "water_cut_hal" if "water_cut_hal" in hal.columns else "hal" if "hal" in hal.columns else None
    if "well_id" not in hal.columns or "date" not in hal.columns or value_column is None:
        logger.warning("HAL water cut file %s has no required columns", source)
        return pd.DataFrame(columns=["well_id", "timestamp", "hal_value"])

    hal = hal[["well_id", "date", value_column]].copy()
    hal["well_id"] = hal["well_id"].astype(str)
    hal["timestamp"] = pd.to_datetime(hal["date"], errors="coerce")
    hal["hal_value"] = pd.to_numeric(hal[value_column], errors="coerce")
    hal = hal.dropna(subset=["well_id", "timestamp", "hal_value"])
    hal = hal[hal["hal_value"].between(0.0, 100.0)]
    return hal[["well_id", "timestamp", "hal_value"]].sort_values(["well_id", "timestamp"]).reset_index(drop=True)


def _build_daily_running_flag(pdf: Any) -> Any:
    """Per (well_id, calendar day): True if the well was running that day, based on
    a 7-day centered rolling median of esp_frequency/active_power (mirrors the
    running gate this pipeline already used before this rewrite)."""
    import pandas as pd  # type: ignore

    has_signal = "esp_frequency" in pdf.columns and "active_power" in pdf.columns
    if not has_signal:
        return None

    daily = (
        pdf.groupby(["well_id", "_day"], sort=True)
        .agg(esp_frequency=("esp_frequency", "median"), active_power=("active_power", "median"))
        .reset_index()
    )

    parts = []
    for well_id, well_daily in daily.groupby("well_id", sort=False):
        well_daily = well_daily.sort_values("_day").copy()
        freq_med = well_daily["esp_frequency"].rolling(7, min_periods=1, center=True).median()
        power_med = well_daily["active_power"].rolling(7, min_periods=1, center=True).median()
        well_daily["running"] = freq_med.ge(RUNNING_FREQ_MIN_HZ) & power_med.ge(RUNNING_POWER_MIN_KW)
        parts.append(well_daily[["well_id", "_day", "running"]])

    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=["well_id", "_day", "running"])


def _with_adaptive_water_cut_algorithm(frame: pl.DataFrame) -> pl.DataFrame:
    """'Обв. алгоритм' sourced exclusively from ХАЛ lab измерений
    (water_cut_hal_data_path), single stateful filter (see adaptive_water_cut.py —
    algorithm as supplied, not modified: no rolling windows, no separate
    fast/slow blend, no hold-aware carry-over). No fallback to telemetry_water_cut
    (АГЗУ), Qж/Qн back-calculation, TR, СППВ, zero-filling, or interpolation of
    missing days."""
    import pandas as pd  # type: ignore

    if frame.is_empty():
        return _apply_daily_fields(frame, *_empty_daily_fields())

    hal_raw = _load_hal_raw_frame(*_path_cache_key(settings.water_cut_hal_data_path))
    if hal_raw.empty:
        return _apply_daily_fields(frame, *_empty_daily_fields())

    selected = [c for c in ("well_id", "date", "esp_frequency", "active_power") if c in frame.columns]
    pdf = pd.DataFrame(frame.select(selected).to_dicts())
    if pdf.empty or "well_id" not in pdf.columns or "date" not in pdf.columns:
        return _apply_daily_fields(frame, *_empty_daily_fields())

    pdf["well_id"] = pdf["well_id"].astype(str)
    pdf["date"] = pd.to_datetime(pdf["date"], errors="coerce")
    pdf = pdf.dropna(subset=["well_id", "date"]).copy()
    pdf["_day"] = pdf["date"].dt.floor("D")

    running_daily = _build_daily_running_flag(pdf)

    hal_daily_predictions: dict[tuple[str, Any], float] = {}
    algo_predictions: dict[tuple[str, Any], float] = {}
    mode_predictions: dict[tuple[str, Any], str] = {}

    for well_id, well_hal in hal_raw.groupby("well_id", sort=False):
        well_hal = well_hal.sort_values("timestamp").copy()
        well_hal["_day"] = well_hal["timestamp"].dt.floor("D")

        well_running = None
        if running_daily is not None:
            well_running = running_daily[running_daily["well_id"] == well_id].set_index("_day")["running"]
            running_by_point = well_hal["_day"].map(well_running).fillna(False)
            well_hal = well_hal[running_by_point.to_numpy()]

        if well_hal.empty:
            continue

        daily_median = well_hal.groupby("_day")["hal_value"].median()
        if daily_median.empty:
            continue

        result = build_water_cut_line(hal_daily=daily_median, running_daily=well_running)
        if result.empty:
            continue

        for day, row in result.iterrows():
            key = (well_id, day.to_pydatetime())
            hal_value = row.get("water_cut_hal_daily")
            if pd.notna(hal_value):
                hal_daily_predictions[key] = float(hal_value)
            algo_value = row.get("water_cut_algo")
            if pd.notna(algo_value):
                algo_predictions[key] = float(algo_value)
            mode_value = row.get("water_cut_mode")
            if isinstance(mode_value, str) and mode_value:
                mode_predictions[key] = mode_value

    return _apply_daily_fields(
        frame,
        {"water_cut_hal_daily": hal_daily_predictions, "water_cut_algo": algo_predictions},
        {"water_cut_mode": mode_predictions},
    )


def _apply_daily_fields(
    frame: pl.DataFrame,
    float_fields: dict[str, dict[tuple[str, Any], float]],
    string_fields: dict[str, dict[tuple[str, Any], str]],
) -> pl.DataFrame:
    """Attach one or more daily (well_id, day) -> value maps to `frame`, placing
    each value on the FIRST record of that calendar day only (never replicated
    across every raw telemetry row of the day, never fabricated for other rows)."""
    all_keys: set[tuple[str, Any]] = set()
    for values in float_fields.values():
        all_keys.update(values.keys())
    for values in string_fields.values():
        all_keys.update(values.keys())

    field_names = list(float_fields) + list(string_fields)

    if not all_keys:
        out = frame
        for name in float_fields:
            out = out.with_columns(pl.lit(None, dtype=pl.Float64).alias(name))
        for name in string_fields:
            out = out.with_columns(pl.lit(None, dtype=pl.Utf8).alias(name))
        return out

    keys = sorted(all_keys)
    columns: dict[str, list] = {
        "well_id": [k[0] for k in keys],
        "_water_cut_day": [k[1] for k in keys],
    }
    schema: dict[str, pl.DataType] = {"well_id": pl.Utf8, "_water_cut_day": pl.Datetime}
    for name, values in float_fields.items():
        columns[f"_src_{name}"] = [values.get(k) for k in keys]
        schema[f"_src_{name}"] = pl.Float64
    for name, values in string_fields.items():
        columns[f"_src_{name}"] = [values.get(k) for k in keys]
        schema[f"_src_{name}"] = pl.Utf8

    daily = pl.DataFrame(columns, schema=schema, strict=False)

    joined = (
        frame.with_row_index("_water_cut_row")
        .with_columns(pl.col("date").dt.truncate("1d").alias("_water_cut_day"))
        .join(daily, on=["well_id", "_water_cut_day"], how="left")
    )
    is_first_of_day = pl.col("_water_cut_row") == pl.col("_water_cut_row").min().over(["well_id", "_water_cut_day"])

    exprs = []
    drop_cols = ["_water_cut_row", "_water_cut_day"] + [f"_src_{name}" for name in field_names]
    for name in float_fields:
        exprs.append(pl.when(is_first_of_day).then(pl.col(f"_src_{name}")).otherwise(None).cast(pl.Float64).alias(name))
    for name in string_fields:
        exprs.append(pl.when(is_first_of_day).then(pl.col(f"_src_{name}")).otherwise(None).cast(pl.Utf8).alias(name))

    return joined.with_columns(exprs).drop(drop_cols)


def add_water_cut_algorithm(frame: pl.DataFrame) -> pl.DataFrame:
    if frame.is_empty():
        return _apply_daily_fields(frame, *_empty_daily_fields())

    return _with_adaptive_water_cut_algorithm(frame)
