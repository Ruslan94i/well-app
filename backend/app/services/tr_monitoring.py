from __future__ import annotations

import csv
import logging
import math
from datetime import date, datetime
from functools import lru_cache

from app.core.config import settings


logger = logging.getLogger(__name__)

TR_MONITORING_FILE_PATH = settings.tr_monitoring_data_path
TR_MIN_DATE = date(2024, 11, 1)
NUMERIC_COLUMNS = [
    "reservoir_pressure",
    "dynamic_level",
    "intake_pressure",
    "bottomhole_pressure",
    "oil_rate",
    "liquid_rate",
    "water_cut",
    "pump_pressure",
    "gas_factor",
    "productivity",
]


def _clean_cell(value: str | None) -> str:
    return (value or "").replace("\ufeff", "").replace("\xa0", " ").strip()


def _parse_date(value: str | None) -> date | None:
    cleaned = _clean_cell(value)
    if not cleaned:
        return None

    try:
        return datetime.strptime(cleaned, "%Y-%m-%d").date()
    except ValueError:
        return None


def _parse_float(value: str | None) -> float | None:
    cleaned = _clean_cell(value)
    if not cleaned:
        return None

    normalized = cleaned.replace(" ", "").replace(",", ".")
    try:
        parsed = float(normalized)
    except ValueError:
        return None

    return parsed if math.isfinite(parsed) else None


def _load_tr_monitoring_rows() -> list[dict[str, object]]:
    if not TR_MONITORING_FILE_PATH.exists():
        logger.warning("TR monitoring file not found at %s", TR_MONITORING_FILE_PATH)
        return []

    file_stat = TR_MONITORING_FILE_PATH.stat()
    return _load_tr_monitoring_rows_cached(file_stat.st_mtime_ns, file_stat.st_size)


@lru_cache(maxsize=2)
def _load_tr_monitoring_rows_cached(file_mtime_ns: int, file_size: int) -> list[dict[str, object]]:
    del file_mtime_ns, file_size
    logger.info("Loading TR monitoring CSV from %s", TR_MONITORING_FILE_PATH)

    rows: list[dict[str, object]] = []
    with TR_MONITORING_FILE_PATH.open("r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        for raw_row in reader:
            well_id = _clean_cell(raw_row.get("well_id"))
            point_date = _parse_date(raw_row.get("date"))
            if not well_id or point_date is None or point_date < TR_MIN_DATE:
                continue

            row: dict[str, object] = {
                "well_id": well_id,
                "normalized_well_id": well_id.casefold(),
                "date": point_date,
            }
            for column in NUMERIC_COLUMNS:
                row[column] = _parse_float(raw_row.get(column))
            rows.append(row)

    rows.sort(key=lambda item: (str(item["normalized_well_id"]), item["date"]))
    logger.info("Loaded %s TR monitoring rows from %s", len(rows), TR_MONITORING_FILE_PATH)
    return rows


def get_well_tr_monitoring(
    well_id: str,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[dict[str, object]]:
    normalized_well_id = well_id.strip().casefold()
    effective_from = max(date_from or TR_MIN_DATE, TR_MIN_DATE)
    well_rows = [
        row
        for row in _load_tr_monitoring_rows()
        if row["normalized_well_id"] == normalized_well_id and row["date"] >= effective_from
    ]

    if date_to is not None:
        next_after_to: dict[str, object] | None = None
        visible_rows: list[dict[str, object]] = []
        for row in well_rows:
            row_date = row["date"]
            if not isinstance(row_date, date):
                continue
            if row_date <= date_to:
                visible_rows.append(row)
            elif next_after_to is None:
                next_after_to = row
                break
        well_rows = visible_rows + ([next_after_to] if next_after_to else [])

    return [
        {
            key: value
            for key, value in row.items()
            if key not in {"well_id", "normalized_well_id"}
        }
        for row in well_rows
    ]
