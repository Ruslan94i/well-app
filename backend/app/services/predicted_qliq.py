from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import polars as pl

from app.core.config import settings


logger = logging.getLogger(__name__)

INVALID_WELL_IDS = {"Da_515", "Da_51Da_515", "Da_515Da_515"}
DUPLICATED_WELL_ID_PATTERN = re.compile(r"^([A-Za-z]+_\d+)\1$")

VFM_GAIN = 0.30
VFM_TAU = 0.50
VFM_SMOOTH_DAYS = 5
VFM_MIN_SHAPE_QLIQ = 10.0
VFM_STOP_FREQ_HZ = 5.0
VFM_STOP_POWER_KW = 1.0
VFM_MODEL_VERSION = "vfm_core_episode_shape_v1"
EXTERNAL_VFM_DAILY_PATH = settings.reference_data_path / "vfm_daily.csv"

WELL_ALIASES = ("Скважина", "РЎРєРІР°Р¶РёРЅР°", "well_id", "well")
DATE_ALIASES = ("Дата", "Р”Р°С‚Р°", "date", "telemetry_date", "telemetry_time")
QLIQ_ALIASES = (
    "Дебит жидкости",
    "Р”РµР±РёС‚ Р¶РёРґРєРѕСЃС‚Рё",
    "telemetry_qliq",
    "telemetry_qliq_vfm",
    "qliq",
)
FREQUENCY_ALIASES = (
    "Частота вращения двиг.",
    "Р§Р°СЃС‚РѕС‚Р° РІСЂР°С‰РµРЅРёСЏ РґРІРёРі.",
    "telemetry_esp_frequency",
)
ACTIVE_POWER_ALIASES = (
    "Активная мощность",
    "РђРєС‚РёРІРЅР°СЏ РјРѕС‰РЅРѕСЃС‚СЊ",
    "telemetry_active_power",
)


def _is_valid_well_id(value: str | None) -> bool:
    if value is None:
        return False
    cleaned = value.replace("\ufeff", "").replace("\xa0", " ").strip()
    return bool(cleaned) and cleaned not in INVALID_WELL_IDS and DUPLICATED_WELL_ID_PATTERN.match(cleaned) is None


def _today_utc_key() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _vfm_parameters() -> dict[str, float | int]:
    return {
        "gain": VFM_GAIN,
        "tau": VFM_TAU,
        "smooth_days": VFM_SMOOTH_DAYS,
        "min_shape_qliq": VFM_MIN_SHAPE_QLIQ,
        "stop_freq_hz": VFM_STOP_FREQ_HZ,
        "stop_active_power": VFM_STOP_POWER_KW,
    }


def _read_meta(meta_path: Path) -> dict[str, Any]:
    try:
        return json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _write_meta(meta_path: Path, payload: dict[str, Any]) -> None:
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = meta_path.with_suffix(meta_path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(meta_path)


def _replace_file(tmp_path: Path, output_path: Path) -> None:
    try:
        tmp_path.replace(output_path)
    except PermissionError:
        output_path.unlink(missing_ok=True)
        tmp_path.replace(output_path)


def _external_vfm_mtime_ns() -> int | None:
    try:
        return EXTERNAL_VFM_DAILY_PATH.stat().st_mtime_ns if EXTERNAL_VFM_DAILY_PATH.exists() else None
    except OSError:
        return None


def _portable_path(path: Path) -> str:
    project_root = Path(__file__).resolve().parents[3]
    try:
        return str(path.resolve().relative_to(project_root)).replace("\\", "/")
    except (OSError, ValueError):
        return str(path)


def _normalize_numeric(column_name: str) -> pl.Expr:
    return (
        pl.col(column_name)
        .cast(pl.Utf8, strict=False)
        .str.replace_all(",", ".")
        .cast(pl.Float64, strict=False)
    )


def _parse_day(column_name: str) -> pl.Expr:
    return pl.col(column_name).cast(pl.Utf8, strict=False).str.to_datetime(strict=False).dt.date()


def _valid_well_expr(column_name: str = "well_id") -> pl.Expr:
    return (
        pl.col(column_name).is_not_null()
        & (pl.col(column_name).str.len_chars() > 0)
        & (~pl.col(column_name).is_in(list(INVALID_WELL_IDS)))
    )


def _load_telemetry_days(path: Path) -> pl.DataFrame:
    frame = (
        pl.read_csv(path, separator=";", columns=["Скважина", "Дата"], infer_schema_length=0)
        .rename({"Скважина": "well_id", "Дата": "date_text"})
        .with_columns(
            pl.col("well_id").cast(pl.Utf8, strict=False).str.strip_chars(),
            _parse_day("date_text").alias("date"),
        )
        .filter(_valid_well_expr() & pl.col("date").is_not_null())
        .filter(pl.col("well_id").map_elements(_is_valid_well_id, return_dtype=pl.Boolean))
        .select("well_id", "date")
        .unique()
        .sort(["well_id", "date"])
    )
    return frame


def _load_measurement_daily(path: Path) -> pl.DataFrame:
    frame = (
        pl.read_csv(path, separator=";", columns=["Скважина", "Дата", "Дебит жидкости"], infer_schema_length=0)
        .rename({"Скважина": "well_id", "Дата": "date_text", "Дебит жидкости": "qliq_text"})
        .with_columns(
            pl.col("well_id").cast(pl.Utf8, strict=False).str.strip_chars(),
            _parse_day("date_text").alias("date"),
            _normalize_numeric("qliq_text").alias("measured_qliq"),
        )
        .filter(_valid_well_expr() & pl.col("date").is_not_null() & (pl.col("measured_qliq") > 0))
        .filter(pl.col("well_id").map_elements(_is_valid_well_id, return_dtype=pl.Boolean))
        .group_by(["well_id", "date"])
        .agg(pl.col("measured_qliq").mean())
        .sort(["well_id", "date"])
    )
    return frame


def _detect_delimiter(path: Path) -> str:
    try:
        sample = path.read_text(encoding="utf-8-sig", errors="ignore")[:4096]
    except OSError:
        return ","
    if not sample:
        return ","
    return ";" if sample.count(";") > sample.count(",") else ","


def _read_pandas_csv(path: Path) -> pd.DataFrame:
    delimiter = _detect_delimiter(path)
    return pd.read_csv(path, sep=delimiter, low_memory=False, encoding="utf-8-sig")


def _column_lookup(frame: pd.DataFrame) -> dict[str, str]:
    return {str(column).strip().lstrip("\ufeff").lower(): column for column in frame.columns}


def _find_column(frame: pd.DataFrame, aliases: tuple[str, ...]) -> str | None:
    lookup = _column_lookup(frame)
    for alias in aliases:
        column = lookup.get(alias.strip().lower())
        if column is not None:
            return column
    return None


def _numeric_series(frame: pd.DataFrame, column: str | None) -> pd.Series:
    if column is None:
        return pd.Series(np.nan, index=frame.index, dtype="float64")
    values = frame[column].astype("string").str.replace(",", ".", regex=False)
    return pd.to_numeric(values, errors="coerce")


def _date_series(frame: pd.DataFrame, column: str) -> pd.Series:
    return pd.to_datetime(frame[column], errors="coerce").dt.floor("D")


def _well_series(frame: pd.DataFrame, column: str) -> pd.Series:
    return frame[column].astype("string").str.replace("\ufeff", "", regex=False).str.strip()


def _valid_well_mask(series: pd.Series) -> pd.Series:
    return series.map(lambda value: _is_valid_well_id(None if pd.isna(value) else str(value))).astype(bool)


def _load_telemetry_daily_vfm(path: Path) -> pd.DataFrame:
    raw = _read_pandas_csv(path)
    well_column = _find_column(raw, WELL_ALIASES)
    date_column = _find_column(raw, DATE_ALIASES)
    if well_column is None or date_column is None:
        raise ValueError(f"Telemetry CSV has no well/date columns: {path}")

    frame = pd.DataFrame(
        {
            "well_id": _well_series(raw, well_column),
            "date": _date_series(raw, date_column),
            "telemetry_qliq": _numeric_series(raw, _find_column(raw, QLIQ_ALIASES)),
            "telemetry_esp_frequency": _numeric_series(raw, _find_column(raw, FREQUENCY_ALIASES)),
            "telemetry_active_power": _numeric_series(raw, _find_column(raw, ACTIVE_POWER_ALIASES)),
        }
    )
    frame = frame[_valid_well_mask(frame["well_id"]) & frame["date"].notna()]
    return (
        frame.groupby(["well_id", "date"], as_index=False)
        .median(numeric_only=True)
        .sort_values(["well_id", "date"])
        .reset_index(drop=True)
    )


def _load_measurement_daily_vfm(path: Path) -> pd.DataFrame:
    raw = _read_pandas_csv(path)
    well_column = _find_column(raw, WELL_ALIASES)
    date_column = _find_column(raw, DATE_ALIASES)
    qliq_column = _find_column(raw, QLIQ_ALIASES)
    if well_column is None or date_column is None or qliq_column is None:
        raise ValueError(f"Measurements CSV has no required columns: {path}")

    frame = pd.DataFrame(
        {
            "well_id": _well_series(raw, well_column),
            "date": _date_series(raw, date_column),
            "measured_qliq": _numeric_series(raw, qliq_column),
        }
    )
    frame = frame[
        _valid_well_mask(frame["well_id"])
        & frame["date"].notna()
        & frame["measured_qliq"].notna()
        & (frame["measured_qliq"] > 0)
    ]
    return (
        frame.groupby(["well_id", "date"], as_index=False)["measured_qliq"]
        .mean()
        .sort_values(["well_id", "date"])
        .reset_index(drop=True)
    )


def _load_tr_daily(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame(columns=["well_id", "tr_source_date", "tr_liquid_rate"])

    raw = _read_pandas_csv(path)
    lookup = _column_lookup(raw)
    well_column = lookup.get("well_id") or lookup.get("well")
    date_column = lookup.get("tr_source_date") or lookup.get("date")
    qliq_column = lookup.get("tr_liquid_rate") or lookup.get("liquid_rate")
    if well_column is None or date_column is None or qliq_column is None:
        logger.warning("TR monitoring CSV has no usable anchor columns: %s", path)
        return pd.DataFrame(columns=["well_id", "tr_source_date", "tr_liquid_rate"])

    frame = pd.DataFrame(
        {
            "well_id": _well_series(raw, well_column),
            "tr_source_date": _date_series(raw, date_column),
            "tr_liquid_rate": _numeric_series(raw, qliq_column),
        }
    )
    frame = frame[
        _valid_well_mask(frame["well_id"])
        & frame["tr_source_date"].notna()
        & frame["tr_liquid_rate"].notna()
        & (frame["tr_liquid_rate"] > 0)
    ]
    return (
        frame.sort_values(["well_id", "tr_source_date"])
        .groupby(["well_id", "tr_source_date"], as_index=False)["tr_liquid_rate"]
        .last()
        .sort_values(["well_id", "tr_source_date"])
        .reset_index(drop=True)
    )


def _rolling_median_by_well(frame: pd.DataFrame, column: str) -> pd.Series:
    return (
        frame.groupby("well_id", group_keys=False)[column]
        .rolling(VFM_SMOOTH_DAYS, min_periods=1)
        .median()
        .reset_index(level=0, drop=True)
    )


def _attach_tr_anchors(daily: pd.DataFrame, tr_daily: pd.DataFrame) -> pd.DataFrame:
    parts: list[pd.DataFrame] = []
    empty_tr_columns = ["tr_source_date", "tr_liquid_rate", "anchor_shape_qliq_s"]

    for well_id, well_daily in daily.groupby("well_id", sort=False):
        well_frame = well_daily.sort_values("date").copy()
        well_tr = tr_daily[tr_daily["well_id"] == well_id].sort_values("tr_source_date")
        if well_tr.empty:
            for column in empty_tr_columns:
                well_frame[column] = np.nan
            parts.append(well_frame)
            continue

        anchored = pd.merge_asof(
            well_frame,
            well_tr[["tr_source_date", "tr_liquid_rate"]],
            left_on="date",
            right_on="tr_source_date",
            direction="backward",
        )

        shape_dates = well_frame["date"].to_numpy(dtype="datetime64[ns]")
        shape_values = well_frame["shape_qliq_s"].to_numpy(dtype="float64")
        tr_dates = pd.to_datetime(anchored["tr_source_date"], errors="coerce").to_numpy(dtype="datetime64[ns]")
        positions = np.searchsorted(shape_dates, tr_dates, side="right") - 1
        valid_positions = positions >= 0
        anchor_shape = np.full(len(anchored), np.nan)
        anchor_shape[valid_positions] = shape_values[positions[valid_positions]]
        anchored["anchor_shape_qliq_s"] = anchor_shape
        parts.append(anchored)

    if not parts:
        return daily.assign(tr_source_date=np.nan, tr_liquid_rate=np.nan, anchor_shape_qliq_s=np.nan)
    return pd.concat(parts, ignore_index=True).sort_values(["well_id", "date"]).reset_index(drop=True)


def _compute_anchored_delta(daily: pd.DataFrame) -> pd.DataFrame:
    has_tr_anchor = daily["tr_liquid_rate"].notna() & (daily["tr_liquid_rate"] > 0)
    fallback_anchor = daily["shape_qliq_s"].where(daily["shape_qliq_s"].notna(), daily["measured_qliq"])
    anchor = daily["tr_liquid_rate"].where(has_tr_anchor, fallback_anchor)
    anchor_shape = daily["anchor_shape_qliq_s"].where(
        daily["anchor_shape_qliq_s"].notna(), daily["shape_qliq_s"]
    )

    can_use_shape = (
        daily["shape_qliq_s"].notna()
        & anchor_shape.notna()
        & (daily["shape_qliq_s"] > VFM_MIN_SHAPE_QLIQ)
        & (anchor_shape > VFM_MIN_SHAPE_QLIQ)
    )
    ratio = pd.Series(1.0, index=daily.index, dtype="float64")
    ratio.loc[can_use_shape] = (daily.loc[can_use_shape, "shape_qliq_s"] / anchor_shape.loc[can_use_shape]).clip(0.5, 2.0)

    predicted = anchor * (1.0 + VFM_GAIN * (ratio - 1.0))
    predicted = predicted.clip(lower=anchor * (1.0 - VFM_TAU), upper=anchor * (1.0 + VFM_TAU))

    stop_flag = (
        daily["telemetry_esp_frequency_s"].notna()
        & daily["telemetry_active_power_s"].notna()
        & (daily["telemetry_esp_frequency_s"] < VFM_STOP_FREQ_HZ)
        & (daily["telemetry_active_power_s"] < VFM_STOP_POWER_KW)
    )
    predicted.loc[stop_flag] = 0.0

    result = daily.copy()
    result["predicted_qliq"] = predicted.round(2)
    result["anchor_qliq"] = anchor.round(2)
    result["shape_ratio"] = ratio.round(4)
    result["anchor_source"] = np.where(has_tr_anchor, "tr", "telemetry_qliq")
    result["stop_flag"] = stop_flag
    return result


def _load_existing_predictions(path: Path) -> pl.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pl.DataFrame(schema={"well_id": pl.Utf8, "date": pl.Date, "seed_predicted_qliq": pl.Float64})

    delimiter = _detect_delimiter(path)
    try:
        raw = pl.read_csv(path, separator=delimiter, infer_schema_length=0)
    except Exception as exc:
        logger.warning("Cannot read existing predicted Q liquid cache %s: %s", path, exc)
        return pl.DataFrame(schema={"well_id": pl.Utf8, "date": pl.Date, "seed_predicted_qliq": pl.Float64})

    normalized = {column.strip().lstrip("\ufeff").lower(): column for column in raw.columns}
    well_column = normalized.get("well_id") or normalized.get("well")
    date_column = normalized.get("date") or normalized.get("telemetry_date") or normalized.get("telemetry_time")
    value_column = (
        normalized.get("predicted_qliq")
        or normalized.get("predicted_q_liquid")
        or normalized.get("predicted_liquid_rate")
        or normalized.get("qliq_pred")
    )
    if well_column is None or date_column is None or value_column is None:
        logger.info("Existing predicted Q liquid cache %s has no reusable seed columns", path)
        return pl.DataFrame(schema={"well_id": pl.Utf8, "date": pl.Date, "seed_predicted_qliq": pl.Float64})

    return (
        raw.rename({well_column: "well_id", date_column: "date_text", value_column: "predicted_text"})
        .with_columns(
            pl.col("well_id").cast(pl.Utf8, strict=False).str.strip_chars(),
            _parse_day("date_text").alias("date"),
            _normalize_numeric("predicted_text").alias("seed_predicted_qliq"),
        )
        .filter(_valid_well_expr() & pl.col("date").is_not_null() & pl.col("seed_predicted_qliq").is_not_null())
        .filter(pl.col("well_id").map_elements(_is_valid_well_id, return_dtype=pl.Boolean))
        .group_by(["well_id", "date"])
        .agg(pl.col("seed_predicted_qliq").mean())
        .sort(["well_id", "date"])
    )


def _build_predicted_qliq_from_external_vfm(path: Path, output_path: Path, meta_path: Path) -> dict[str, Any]:
    raw = _read_pandas_csv(path)
    normalized = {str(column).strip().lstrip("\ufeff"): column for column in raw.columns}
    required = {"well_id", "date", "vQliq"}
    missing = [column for column in required if column not in normalized]
    if missing:
        raise ValueError(f"External VFM daily CSV has no required columns {missing}: {path}")

    output = pd.DataFrame(
        {
            "well_id": _well_series(raw, normalized["well_id"]),
            "date": pd.to_datetime(raw[normalized["date"]], errors="coerce").dt.floor("D"),
            "predicted_qliq": _numeric_series(raw, normalized["vQliq"]),
            "anchor_qliq": _numeric_series(raw, normalized.get("tr_anchor")),
            "shape_ratio": 1.0,
            "anchor_source": "vfm_core",
            "stop_flag": _numeric_series(raw, normalized.get("stop")).fillna(0).astype(bool),
            "tr_source_date": pd.to_datetime(raw[normalized.get("tr_source_date")], errors="coerce").dt.floor("D")
            if normalized.get("tr_source_date") is not None
            else pd.NaT,
        }
    )
    output = output[
        _valid_well_mask(output["well_id"])
        & output["date"].notna()
        & output["predicted_qliq"].notna()
    ]
    output = (
        output.sort_values(["well_id", "date"])
        .drop_duplicates(["well_id", "date"], keep="last")
        .reset_index(drop=True)
    )
    output["predicted_qliq"] = output["predicted_qliq"].round(2)
    output["anchor_qliq"] = output["anchor_qliq"].round(2)
    output["date"] = pd.to_datetime(output["date"]).dt.strftime("%Y-%m-%d")
    output["tr_source_date"] = pd.to_datetime(output["tr_source_date"], errors="coerce").dt.strftime("%Y-%m-%d")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    output.to_csv(tmp_path, index=False)
    _replace_file(tmp_path, output_path)

    metadata = {
        "computed_at_utc": datetime.now(timezone.utc).isoformat(),
        "computed_for_utc_date": _today_utc_key(),
        "source": "external vfm_core daily output",
        "model": "vfm_core",
        "model_version": VFM_MODEL_VERSION,
        "external_vfm_daily_path": _portable_path(path),
        "external_vfm_daily_mtime_ns": path.stat().st_mtime_ns,
        "rows": int(len(output)),
        "wells": int(output["well_id"].nunique()),
        "anchor_source_counts": output["anchor_source"].value_counts().to_dict(),
        "stop_days": int(output["stop_flag"].sum()),
    }
    _write_meta(meta_path, metadata)
    logger.info(
        "Predicted Q liquid cache loaded from external VFM %s: %s rows, %s wells",
        path,
        metadata["rows"],
        metadata["wells"],
    )
    return metadata


def build_predicted_qliq_cache() -> dict[str, Any]:
    telemetry_path = settings.telemetry_aggregated_data_path
    measurements_path = settings.measurements_data_path
    tr_path = settings.tr_monitoring_data_path
    output_path = settings.predicted_qliq_data_path
    meta_path = settings.predicted_qliq_meta_path

    if EXTERNAL_VFM_DAILY_PATH.exists():
        return _build_predicted_qliq_from_external_vfm(EXTERNAL_VFM_DAILY_PATH, output_path, meta_path)

    if not telemetry_path.exists():
        raise FileNotFoundError(f"Telemetry CSV not found: {telemetry_path}")
    if not measurements_path.exists():
        raise FileNotFoundError(f"Measurements CSV not found: {measurements_path}")

    logger.info("Building anchored-delta VFM daily predicted Q liquid cache for all wells")
    telemetry_daily = _load_telemetry_daily_vfm(telemetry_path)
    measurement_daily = _load_measurement_daily_vfm(measurements_path)
    tr_daily = _load_tr_daily(tr_path)

    daily = (
        telemetry_daily.merge(measurement_daily, on=["well_id", "date"], how="left")
        .sort_values(["well_id", "date"])
        .reset_index(drop=True)
    )
    daily["shape_qliq"] = daily["telemetry_qliq"].combine_first(daily["measured_qliq"])
    daily["shape_qliq"] = daily.groupby("well_id")["shape_qliq"].ffill()
    daily["shape_qliq"] = daily.groupby("well_id")["shape_qliq"].bfill()
    daily["shape_qliq_s"] = _rolling_median_by_well(daily, "shape_qliq")
    daily["telemetry_esp_frequency_s"] = _rolling_median_by_well(daily, "telemetry_esp_frequency")
    daily["telemetry_active_power_s"] = _rolling_median_by_well(daily, "telemetry_active_power")

    daily = _attach_tr_anchors(daily, tr_daily)
    predicted = _compute_anchored_delta(daily)
    output = (
        predicted[predicted["predicted_qliq"].notna()]
        .loc[
            :,
            [
                "well_id",
                "date",
                "predicted_qliq",
                "anchor_qliq",
                "shape_ratio",
                "anchor_source",
                "stop_flag",
                "tr_source_date",
            ],
        ]
        .sort_values(["well_id", "date"])
        .reset_index(drop=True)
    )
    output["date"] = pd.to_datetime(output["date"]).dt.strftime("%Y-%m-%d")
    output["tr_source_date"] = pd.to_datetime(output["tr_source_date"], errors="coerce").dt.strftime("%Y-%m-%d")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    output.to_csv(tmp_path, index=False)
    _replace_file(tmp_path, output_path)

    metadata = {
        "computed_at_utc": datetime.now(timezone.utc).isoformat(),
        "computed_for_utc_date": _today_utc_key(),
        "source": "anchored-delta VFM: TR anchor with smoothed Qliq shape and stop guard",
        "model": "anchored_delta_vfm",
        "model_version": VFM_MODEL_VERSION,
        "parameters": _vfm_parameters(),
        "rows": int(len(output)),
        "wells": int(output["well_id"].nunique()),
        "telemetry_day_rows": int(len(telemetry_daily)),
        "telemetry_wells": int(telemetry_daily["well_id"].nunique()),
        "measurement_wells": int(measurement_daily["well_id"].nunique()),
        "tr_anchor_wells": int(tr_daily["well_id"].nunique()) if not tr_daily.empty else 0,
        "tr_anchor_rows": int(len(tr_daily)),
        "anchor_source_counts": output["anchor_source"].value_counts().to_dict(),
        "stop_days": int(output["stop_flag"].sum()),
    }
    _write_meta(meta_path, metadata)
    logger.info(
        "Predicted Q liquid cache written to %s: %s rows, %s wells",
        output_path,
        metadata["rows"],
        metadata["wells"],
    )
    return metadata


def ensure_predicted_qliq_cache(*, force: bool = False) -> dict[str, Any]:
    output_path = settings.predicted_qliq_data_path
    meta_path = settings.predicted_qliq_meta_path
    meta = _read_meta(meta_path)
    external_mtime_ns = _external_vfm_mtime_ns()
    if (
        not force
        and output_path.exists()
        and meta.get("computed_for_utc_date") == _today_utc_key()
        and meta.get("model_version") == VFM_MODEL_VERSION
        and (
            (external_mtime_ns is not None and meta.get("external_vfm_daily_mtime_ns") == external_mtime_ns)
            or (external_mtime_ns is None and meta.get("parameters") == _vfm_parameters())
        )
        and meta.get("rows", 0) > 0
    ):
        return meta

    return build_predicted_qliq_cache()
