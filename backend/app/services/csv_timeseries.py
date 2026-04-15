from __future__ import annotations

import csv
import logging
from datetime import date, datetime
from functools import lru_cache

import polars as pl

from app.core.config import settings


logger = logging.getLogger(__name__)

CSV_FILE_PATH = settings.csv_data_path
NULL_TOKENS = {"", "—", "#ЗНАЧ!", "#ДЕЛ/0!"}
COLUMN_MAPPING = {
    "well_id": "Скважина",
    "date": "Дата",
    "qliq": "Дебит жидкости (среднеуплотненный)",
    "qoil": "Дебит нефти",
    "water_cut": "Обводненность, %",
    "intake_pressure": "Давление на приеме насоса",
    "esp_frequency": "Частота вращения двигателя",
    "load": "Загрузка",
    "gas_factor": "Газовый фактор",
    "gas_liquid_factor": "Газожидкостной фактор",
    "qliq_wfm": "Уплотненный дебит (виртуальный расходомер)",
}
NUMERIC_COLUMNS = [
    "qliq",
    "qoil",
    "water_cut",
    "intake_pressure",
    "esp_frequency",
    "load",
    "gas_factor",
    "gas_liquid_factor",
    "qliq_wfm",
]
RESPONSE_COLUMNS = [
    "date",
    "qliq",
    "qoil",
    "qgas",
    "gas_factor",
    "gas_liquid_factor",
    "qliq_wfm",
    "qliq_vfm",
    "water_cut",
    "intake_pressure",
    "esp_frequency",
    "load",
]
FRAME_SCHEMA = {
    "well_id": pl.Utf8,
    "date": pl.Date,
    "qliq": pl.Float64,
    "qoil": pl.Float64,
    "qgas": pl.Float64,
    "gas_factor": pl.Float64,
    "gas_liquid_factor": pl.Float64,
    "qliq_wfm": pl.Float64,
    "qliq_vfm": pl.Float64,
    "water_cut": pl.Float64,
    "intake_pressure": pl.Float64,
    "esp_frequency": pl.Float64,
    "load": pl.Float64,
}


def _clean_cell(value: str | None) -> str:
    if value is None:
        return ""

    return value.replace("\ufeff", "").replace("\xa0", " ").strip()


def _get_row_value(raw_row: list[str], column_indexes: dict[str, int], column_name: str) -> str | None:
    column_index = column_indexes[column_name]
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


def _parse_float(value: str | None) -> float | None:
    cleaned = _clean_cell(value)
    if cleaned in NULL_TOKENS:
        return None

    normalized = cleaned.replace(" ", "").replace(",", ".")
    try:
        return float(normalized)
    except ValueError:
        return None


@lru_cache(maxsize=1)
def _load_timeseries_frame() -> pl.DataFrame:
    logger.info("Loading well timeseries CSV from %s", CSV_FILE_PATH)

    if not CSV_FILE_PATH.exists():
        logger.error("CSV data file not found at %s", CSV_FILE_PATH)
        raise FileNotFoundError(f"CSV data file not found: {CSV_FILE_PATH}")

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

            row: dict[str, object] = {
                "well_id": well_id,
                "date": point_date,
            }

            for normalized_name in NUMERIC_COLUMNS:
                source_name = COLUMN_MAPPING[normalized_name]
                raw_value = _get_row_value(raw_row, column_indexes, source_name)
                row[normalized_name] = _parse_float(raw_value)

            qoil = row["qoil"]
            gas_factor = row["gas_factor"]
            qgas = None
            if isinstance(qoil, float) and isinstance(gas_factor, float):
                qgas = round(qoil * gas_factor, 2)

            row["qgas"] = qgas
            row["qliq_vfm"] = row["qliq_wfm"]
            rows.append(row)

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
    frame = _load_timeseries_frame().filter(pl.col("well_id") == pl.lit(normalized_well_id))

    if date_from is not None:
        frame = frame.filter(pl.col("date") >= pl.lit(date_from))

    if date_to is not None:
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
        .with_columns(pl.col("date").dt.strftime("%Y-%m-%d"))
        .to_dicts()
    )
