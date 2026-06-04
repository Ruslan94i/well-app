from __future__ import annotations

import csv
import logging
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path

import polars as pl

from app.core.config import settings


logger = logging.getLogger(__name__)

CSV_FILE_PATH = settings.csv_data_path
MINUTE_TELEMETRY_FOLDER_PATH = settings.minute_telemetry_data_path
MINUTE_TELEMETRY_WELL_IDS = {"Ic_367"}
NULL_TOKENS = {"", "—", "#ЗНАЧ!", "#ДЕЛ/0!"}
COLUMN_MAPPING = {
    "well_id": "Скважина",
    "date": "Дата",
    "qliq": "Дебит жидкости",
    "buffer_pressure": "Давление буферное",
    "casing_pressure": "Давление затрубное",
    "load": "Загрузка",
    "water_cut": "Обводненность",
    "intake_pressure": "Р на приеме насоса",
    "esp_frequency": "Частота вращения двиг.",
    "active_power": "Активная мощность",
    "bdpv_volume_rate": "БДПВ Объем в пересчете на сутки",
    "bdpv_water_flow": "БДПВ Расход воды",
    "collector_pressure": "Давление в коллекторе",
    "full_power": "Полная мощность",
    "qgas": "Расход газа на сутки",
    "qoil": "Расход нефти",
    "gas_factor": "Газовый фактор",
    "gas_liquid_factor": "Газожидкостной фактор",
    "qliq_wfm": "Уплотненный дебит (виртуальный расходомер)",
}
NUMERIC_COLUMNS = [
    "qliq",
    "buffer_pressure",
    "casing_pressure",
    "load",
    "water_cut",
    "intake_pressure",
    "esp_frequency",
    "active_power",
    "bdpv_volume_rate",
    "bdpv_water_flow",
    "collector_pressure",
    "full_power",
    "qgas",
    "qoil",
    "gas_factor",
    "gas_liquid_factor",
    "qliq_wfm",
]
RESPONSE_COLUMNS = [
    "date",
    "qliq",
    "buffer_pressure",
    "casing_pressure",
    "load",
    "water_cut",
    "intake_pressure",
    "esp_frequency",
    "active_power",
    "bdpv_volume_rate",
    "bdpv_water_flow",
    "collector_pressure",
    "full_power",
    "qoil",
    "qgas",
    "gas_factor",
    "gas_liquid_factor",
    "qliq_wfm",
    "qliq_vfm",
]
FRAME_SCHEMA = {
    "well_id": pl.Utf8,
    "date": pl.Date,
    "qliq": pl.Float64,
    "buffer_pressure": pl.Float64,
    "casing_pressure": pl.Float64,
    "load": pl.Float64,
    "water_cut": pl.Float64,
    "intake_pressure": pl.Float64,
    "esp_frequency": pl.Float64,
    "active_power": pl.Float64,
    "bdpv_volume_rate": pl.Float64,
    "bdpv_water_flow": pl.Float64,
    "collector_pressure": pl.Float64,
    "full_power": pl.Float64,
    "qoil": pl.Float64,
    "qgas": pl.Float64,
    "gas_factor": pl.Float64,
    "gas_liquid_factor": pl.Float64,
    "qliq_wfm": pl.Float64,
    "qliq_vfm": pl.Float64,
}
MINUTE_FRAME_SCHEMA = {
    **FRAME_SCHEMA,
    "date": pl.Datetime,
}


def _clean_cell(value: str | None) -> str:
    if value is None:
        return ""

    return value.replace("\ufeff", "").replace("\xa0", " ").strip()


def _get_row_value(raw_row: list[str], column_indexes: dict[str, int], column_name: str) -> str | None:
    column_index = column_indexes.get(column_name)
    if column_index is None:
        return None

    if column_index >= len(raw_row):
        return None

    return raw_row[column_index]


def _parse_date(value: str | None) -> date | None:
    cleaned = _clean_cell(value)
    if cleaned in NULL_TOKENS:
        return None

    try:
        return datetime.strptime(cleaned, "%d.%m.%Y").date()
    except ValueError:
        return None


def _parse_datetime(value: str | None) -> datetime | None:
    cleaned = _clean_cell(value)
    if cleaned in NULL_TOKENS:
        return None

    for date_format in ("%d.%m.%Y %H:%M:%S", "%d.%m.%Y %H:%M", "%d.%m.%Y"):
        try:
            return datetime.strptime(cleaned, date_format)
        except ValueError:
            continue

    return None


def _parse_float(value: str | None) -> float | None:
    cleaned = _clean_cell(value)
    if cleaned in NULL_TOKENS:
        return None

    normalized = cleaned.replace(" ", "").replace(",", ".")
    try:
        return float(normalized)
    except ValueError:
        return None


def _build_timeseries_row(
    raw_row: list[str],
    column_indexes: dict[str, int],
    well_id: str,
    point_date: date | datetime,
) -> dict[str, object]:
    row: dict[str, object] = {
        "well_id": well_id,
        "date": point_date,
    }

    for normalized_name in NUMERIC_COLUMNS:
        source_name = COLUMN_MAPPING[normalized_name]
        raw_value = _get_row_value(raw_row, column_indexes, source_name)
        row[normalized_name] = _parse_float(raw_value)

    qliq = row["qliq"]
    qoil = row["qoil"]
    qgas = row["qgas"]

    if not isinstance(qgas, float) and isinstance(qoil, float) and isinstance(row["gas_factor"], float):
        row["qgas"] = round(qoil * row["gas_factor"], 2)
        qgas = row["qgas"]

    if not isinstance(row["gas_factor"], float) and isinstance(qgas, float) and isinstance(qoil, float) and qoil:
        row["gas_factor"] = round(qgas / qoil, 6)

    if (
        not isinstance(row["gas_liquid_factor"], float)
        and isinstance(qgas, float)
        and isinstance(qliq, float)
        and qliq
    ):
        row["gas_liquid_factor"] = round(qgas / qliq, 6)

    row["qliq_vfm"] = row["qliq_wfm"]
    return row


def _load_timeseries_frame() -> pl.DataFrame:
    if not CSV_FILE_PATH.exists():
        logger.error("CSV data file not found at %s", CSV_FILE_PATH)
        raise FileNotFoundError(f"CSV data file not found: {CSV_FILE_PATH}")

    csv_stat = CSV_FILE_PATH.stat()
    return _load_timeseries_frame_cached(csv_stat.st_mtime_ns, csv_stat.st_size)


@lru_cache(maxsize=2)
def _load_timeseries_frame_cached(csv_mtime_ns: int, csv_size: int) -> pl.DataFrame:
    logger.info("Loading well timeseries CSV from %s", CSV_FILE_PATH)

    logger.debug("CSV cache key mtime_ns=%s size=%s", csv_mtime_ns, csv_size)

    with CSV_FILE_PATH.open("r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.reader(csv_file, delimiter=";")
        header = next(reader, None)
        if header is None:
            logger.warning("CSV file %s is empty", CSV_FILE_PATH)
            return pl.DataFrame(schema=FRAME_SCHEMA)

        column_indexes = {name: index for index, name in enumerate(header)}
        missing_columns = [
            source_name for source_name in COLUMN_MAPPING.values() if source_name not in column_indexes
        ]
        if missing_columns:
            missing = ", ".join(missing_columns)
            logger.error("CSV file %s is missing required columns: %s", CSV_FILE_PATH, missing)
            raise ValueError(f"Missing required CSV columns: {missing}")

        rows: list[dict[str, object]] = []
        skipped_rows = 0
        for raw_row in reader:
            if not raw_row:
                continue

            well_id = _clean_cell(_get_row_value(raw_row, column_indexes, COLUMN_MAPPING["well_id"]))
            point_date = _parse_date(_get_row_value(raw_row, column_indexes, COLUMN_MAPPING["date"]))
            if not well_id or point_date is None:
                skipped_rows += 1
                continue

            rows.append(_build_timeseries_row(raw_row, column_indexes, well_id, point_date))

    if not rows:
        logger.warning("CSV file %s produced no valid well rows", CSV_FILE_PATH)
        return pl.DataFrame(schema=FRAME_SCHEMA)

    frame = pl.DataFrame(rows, schema=FRAME_SCHEMA, strict=False).sort(["well_id", "date"])
    logger.info(
        "Loaded %s rows for %s unique wells from %s%s",
        frame.height,
        frame.select("well_id").n_unique(),
        CSV_FILE_PATH,
        f"; skipped {skipped_rows} rows" if skipped_rows else "",
    )
    return frame


def _get_minute_telemetry_path(well_id: str) -> Path:
    return MINUTE_TELEMETRY_FOLDER_PATH / f"{well_id}.csv"


def _load_minute_timeseries_frame(well_id: str) -> pl.DataFrame:
    csv_path = _get_minute_telemetry_path(well_id)
    if not csv_path.exists():
        logger.warning("Minute telemetry file not found for well_id=%s at %s", well_id, csv_path)
        return pl.DataFrame(schema=MINUTE_FRAME_SCHEMA)

    csv_stat = csv_path.stat()
    return _load_minute_timeseries_frame_cached(well_id, str(csv_path), csv_stat.st_mtime_ns, csv_stat.st_size)


@lru_cache(maxsize=4)
def _load_minute_timeseries_frame_cached(
    well_id: str,
    csv_path_value: str,
    csv_mtime_ns: int,
    csv_size: int,
) -> pl.DataFrame:
    del csv_mtime_ns, csv_size
    csv_path = Path(csv_path_value)
    logger.info("Loading minute telemetry CSV for well_id=%s from %s", well_id, csv_path)

    with csv_path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.reader(csv_file, delimiter=";")
        header = next(reader, None)
        if header is None:
            logger.warning("Minute telemetry CSV %s is empty", csv_path)
            return pl.DataFrame(schema=MINUTE_FRAME_SCHEMA)

        column_indexes = {name: index for index, name in enumerate(header)}
        required_columns = [COLUMN_MAPPING["well_id"], COLUMN_MAPPING["date"]]
        missing_columns = [source_name for source_name in required_columns if source_name not in column_indexes]
        if missing_columns:
            missing = ", ".join(missing_columns)
            logger.error("Minute telemetry CSV %s is missing required columns: %s", csv_path, missing)
            raise ValueError(f"Missing required minute telemetry columns: {missing}")

        rows: list[dict[str, object]] = []
        skipped_rows = 0
        for raw_row in reader:
            if not raw_row:
                continue

            row_well_id = _clean_cell(_get_row_value(raw_row, column_indexes, COLUMN_MAPPING["well_id"]))
            point_datetime = _parse_datetime(_get_row_value(raw_row, column_indexes, COLUMN_MAPPING["date"]))
            if row_well_id != well_id or point_datetime is None:
                skipped_rows += 1
                continue

            rows.append(_build_timeseries_row(raw_row, column_indexes, row_well_id, point_datetime))

    if not rows:
        logger.warning("Minute telemetry CSV %s produced no valid rows", csv_path)
        return pl.DataFrame(schema=MINUTE_FRAME_SCHEMA)

    frame = pl.DataFrame(rows, schema=MINUTE_FRAME_SCHEMA, strict=False).sort(["well_id", "date"])
    logger.info(
        "Loaded %s minute telemetry rows for well_id=%s from %s%s",
        frame.height,
        well_id,
        csv_path,
        f"; skipped {skipped_rows} rows" if skipped_rows else "",
    )
    return frame


def get_available_well_ids() -> list[str]:
    frame = _load_timeseries_frame()
    if frame.is_empty():
        logger.warning("No wells available because the CSV frame is empty")
        return []

    well_ids = (
        frame.select(pl.col("well_id").str.strip_chars().alias("well_id"))
        .filter(pl.col("well_id") != "")
        .unique()
        .sort("well_id")
        .get_column("well_id")
        .to_list()
    )
    logger.info("Returning %s unique well ids", len(well_ids))
    return well_ids


def get_well_timeseries(
    well_id: str,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[dict[str, object]]:
    normalized_well_id = well_id.strip()
    use_minute_telemetry = normalized_well_id in MINUTE_TELEMETRY_WELL_IDS
    frame = (
        _load_minute_timeseries_frame(normalized_well_id)
        if use_minute_telemetry
        else _load_timeseries_frame().filter(pl.col("well_id") == pl.lit(normalized_well_id))
    )

    if date_from is not None:
        if use_minute_telemetry:
            frame = frame.filter(pl.col("date").dt.date() >= pl.lit(date_from))
        else:
            frame = frame.filter(pl.col("date") >= pl.lit(date_from))

    if date_to is not None:
        if use_minute_telemetry:
            frame = frame.filter(pl.col("date").dt.date() <= pl.lit(date_to))
        else:
            frame = frame.filter(pl.col("date") <= pl.lit(date_to))

    if frame.is_empty():
        logger.info(
            "No timeseries rows found for well_id=%s date_from=%s date_to=%s",
            normalized_well_id,
            date_from,
            date_to,
        )
        return []

    logger.info(
        "Returning %s timeseries rows for well_id=%s date_from=%s date_to=%s",
        frame.height,
        normalized_well_id,
        date_from,
        date_to,
    )
    return (
        frame.select(RESPONSE_COLUMNS)
        .with_columns(pl.col("date").dt.strftime("%Y-%m-%dT%H:%M:%S" if use_minute_telemetry else "%Y-%m-%d"))
        .to_dicts()
    )
