from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import polars as pl

from app.core.config import settings


logger = logging.getLogger(__name__)

INVALID_WELL_IDS = {"Da_51Da_515", "Da_515Da_515"}
DUPLICATED_WELL_ID_PATTERN = re.compile(r"^([A-Za-z]+_\d+)\1$")


def _is_valid_well_id(value: str | None) -> bool:
    if value is None:
        return False
    cleaned = value.replace("\ufeff", "").replace("\xa0", " ").strip()
    return bool(cleaned) and cleaned not in INVALID_WELL_IDS and DUPLICATED_WELL_ID_PATTERN.match(cleaned) is None


def _today_utc_key() -> str:
    return datetime.now(timezone.utc).date().isoformat()


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


def build_predicted_qliq_cache() -> dict[str, Any]:
    telemetry_path = settings.telemetry_aggregated_data_path
    measurements_path = settings.measurements_data_path
    output_path = settings.predicted_qliq_data_path
    meta_path = settings.predicted_qliq_meta_path

    if not telemetry_path.exists():
        raise FileNotFoundError(f"Telemetry CSV not found: {telemetry_path}")
    if not measurements_path.exists():
        raise FileNotFoundError(f"Measurements CSV not found: {measurements_path}")

    logger.info("Building daily predicted Q liquid cache for all wells")
    telemetry_days = _load_telemetry_days(telemetry_path)
    measurement_daily = _load_measurement_daily(measurements_path)
    seed_predictions = _load_existing_predictions(output_path)

    daily = (
        telemetry_days.join(measurement_daily, on=["well_id", "date"], how="left")
        .sort(["well_id", "date"])
        .with_columns(pl.col("measured_qliq").fill_null(strategy="forward").over("well_id").alias("fallback_qliq"))
        .with_columns(pl.col("fallback_qliq").fill_null(strategy="backward").over("well_id").alias("fallback_qliq"))
        .join(seed_predictions, on=["well_id", "date"], how="left")
        .with_columns(pl.coalesce(["seed_predicted_qliq", "fallback_qliq"]).round(2).alias("predicted_qliq"))
        .filter(pl.col("predicted_qliq").is_not_null())
        .select("well_id", "date", "predicted_qliq")
        .sort(["well_id", "date"])
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    daily.write_csv(tmp_path)
    tmp_path.replace(output_path)

    metadata = {
        "computed_at_utc": datetime.now(timezone.utc).isoformat(),
        "computed_for_utc_date": _today_utc_key(),
        "source": "daily measured Qliq fallback with existing prediction seed priority",
        "rows": daily.height,
        "wells": daily.select("well_id").n_unique(),
        "telemetry_day_rows": telemetry_days.height,
        "telemetry_wells": telemetry_days.select("well_id").n_unique(),
        "measurement_wells": measurement_daily.select("well_id").n_unique(),
        "seed_prediction_wells": seed_predictions.select("well_id").n_unique() if seed_predictions.height else 0,
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
    if (
        not force
        and output_path.exists()
        and meta.get("computed_for_utc_date") == _today_utc_key()
        and meta.get("rows", 0) > 0
    ):
        return meta

    return build_predicted_qliq_cache()
