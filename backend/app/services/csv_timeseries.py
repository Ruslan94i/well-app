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
TELEMETRY_FILE_PATH = settings.telemetry_aggregated_data_path
MEASUREMENTS_FILE_PATH = settings.measurements_data_path
POWER_DAILY_FILE_PATH = settings.power_daily_data_path
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
TELEMETRY_COLUMNS = [
    "buffer_pressure",
    "casing_pressure",
    "load",
    "intake_pressure",
    "esp_frequency",
    "collector_pressure",
]
MEASUREMENT_COLUMNS = [
    "qliq",
    "water_cut",
    "bdpv_volume_rate",
    "bdpv_water_flow",
    "qgas",
    "qoil",
]
POWER_DAILY_COLUMNS = [
    "active_power",
    "full_power",
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
    "date": pl.Datetime,
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

    for date_format in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%d.%m.%Y %H:%M:%S",
        "%d.%m.%Y %H:%M",
        "%d.%m.%Y",
    ):
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


def _build_empty_timeseries_row(well_id: str, point_datetime: datetime) -> dict[str, object]:
    row: dict[str, object] = {"well_id": well_id, "date": point_datetime}
    for normalized_name in NUMERIC_COLUMNS:
        row[normalized_name] = None
    row["qliq_vfm"] = None
    return row


def _fill_numeric_values(
    row: dict[str, object],
    raw_row: list[str],
    column_indexes: dict[str, int],
    normalized_columns: list[str],
) -> None:
    for normalized_name in normalized_columns:
        source_name = COLUMN_MAPPING[normalized_name]
        raw_value = _get_row_value(raw_row, column_indexes, source_name)
        row[normalized_name] = _parse_float(raw_value)


def _finalize_timeseries_row(row: dict[str, object]) -> dict[str, object]:
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
    if TELEMETRY_FILE_PATH.exists() and MEASUREMENTS_FILE_PATH.exists() and POWER_DAILY_FILE_PATH.exists():
        telemetry_stat = TELEMETRY_FILE_PATH.stat()
        measurements_stat = MEASUREMENTS_FILE_PATH.stat()
        power_daily_stat = POWER_DAILY_FILE_PATH.stat()
        return _load_aggregated_timeseries_frame_cached(
            str(TELEMETRY_FILE_PATH),
            telemetry_stat.st_mtime_ns,
            telemetry_stat.st_size,
            str(MEASUREMENTS_FILE_PATH),
            measurements_stat.st_mtime_ns,
            measurements_stat.st_size,
            str(POWER_DAILY_FILE_PATH),
            power_daily_stat.st_mtime_ns,
            power_daily_stat.st_size,
        )

    if not CSV_FILE_PATH.exists():
        logger.error("CSV data file not found at %s", CSV_FILE_PATH)
        raise FileNotFoundError(f"CSV data file not found: {CSV_FILE_PATH}")

    csv_stat = CSV_FILE_PATH.stat()
    return _load_timeseries_frame_cached(csv_stat.st_mtime_ns, csv_stat.st_size)


def _load_aggregated_source_rows(
    csv_path: str,
    source_columns: list[str],
    source_label: str,
) -> list[dict[str, object]]:
    path = Path(csv_path)
    rows: list[dict[str, object]] = []
    skipped_rows = 0
    with path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.reader(csv_file, delimiter=";")
        header = next(reader, None)
        if header is None:
            logger.warning("Aggregated %s CSV %s is empty", source_label, path)
            return rows

        column_indexes = {name: index for index, name in enumerate(header)}
        required_columns = [COLUMN_MAPPING["well_id"], COLUMN_MAPPING["date"]]
        missing_columns = [source_name for source_name in required_columns if source_name not in column_indexes]
        if missing_columns:
            missing = ", ".join(missing_columns)
            logger.error("Aggregated %s CSV %s is missing required columns: %s", source_label, path, missing)
            raise ValueError(f"Missing required aggregated {source_label} columns: {missing}")

        for raw_row in reader:
            if not raw_row:
                continue

            well_id = _clean_cell(_get_row_value(raw_row, column_indexes, COLUMN_MAPPING["well_id"]))
            point_datetime = _parse_datetime(_get_row_value(raw_row, column_indexes, COLUMN_MAPPING["date"]))
            if not well_id or point_datetime is None:
                skipped_rows += 1
                continue

            row = _build_empty_timeseries_row(well_id, point_datetime)
            _fill_numeric_values(row, raw_row, column_indexes, source_columns)
            rows.append(_finalize_timeseries_row(row))

    logger.info(
        "Loaded %s rows from aggregated %s CSV %s%s",
        len(rows),
        source_label,
        path,
        f"; skipped {skipped_rows} rows" if skipped_rows else "",
    )
    return rows


@lru_cache(maxsize=2)
def _load_aggregated_timeseries_frame_cached(
    telemetry_path: str,
    telemetry_mtime_ns: int,
    telemetry_size: int,
    measurements_path: str,
    measurements_mtime_ns: int,
    measurements_size: int,
    power_daily_path: str,
    power_daily_mtime_ns: int,
    power_daily_size: int,
) -> pl.DataFrame:
    logger.info("Loading aggregated telemetry from %s, %s and %s", telemetry_path, measurements_path, power_daily_path)
    logger.debug(
        "Aggregated cache keys telemetry=(%s,%s) measurements=(%s,%s) power_daily=(%s,%s)",
        telemetry_mtime_ns,
        telemetry_size,
        measurements_mtime_ns,
        measurements_size,
        power_daily_mtime_ns,
        power_daily_size,
    )
    rows = [
        *_load_aggregated_source_rows(telemetry_path, TELEMETRY_COLUMNS, "telemetry"),
        *_load_aggregated_source_rows(measurements_path, MEASUREMENT_COLUMNS, "measurements"),
        *_load_aggregated_source_rows(power_daily_path, POWER_DAILY_COLUMNS, "power_daily"),
    ]
    if not rows:
        logger.warning("Aggregated telemetry sources produced no valid rows")
        return pl.DataFrame(schema=FRAME_SCHEMA)

    aggregations = [pl.col(column).mean().alias(column) for column in NUMERIC_COLUMNS]
    frame = (
        pl.DataFrame(rows, schema=FRAME_SCHEMA, strict=False)
        .group_by(["well_id", "date"])
        .agg(aggregations)
        .with_columns(pl.col("qliq_wfm").alias("qliq_vfm"))
        .sort(["well_id", "date"])
    )
    logger.info(
        "Loaded %s aggregated rows for %s unique wells",
        frame.height,
        frame.select("well_id").n_unique(),
    )
    return frame


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

            row = _build_empty_timeseries_row(well_id, datetime.combine(point_date, datetime.min.time()))
            _fill_numeric_values(row, raw_row, column_indexes, NUMERIC_COLUMNS)
            rows.append(_finalize_timeseries_row(row))

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


def _source_signature(path: Path) -> tuple[str, int, int] | None:
    if not path.exists():
        return None

    file_stat = path.stat()
    return (str(path), file_stat.st_mtime_ns, file_stat.st_size)


@lru_cache(maxsize=2)
def _load_available_well_ids_cached(source_signatures: tuple[tuple[str, int, int], ...]) -> tuple[str, ...]:
    well_ids: set[str] = set()
    source_well_column = COLUMN_MAPPING["well_id"]
    for path_value, _mtime_ns, _size in source_signatures:
        path = Path(path_value)
        try:
            frame = pl.read_csv(
                path,
                separator=";",
                encoding="utf8-lossy",
                columns=[source_well_column],
                schema_overrides={source_well_column: pl.Utf8},
            )
        except Exception:
            logger.exception("Failed to read well ids from %s", path)
            continue

        well_ids.update(
            value
            for value in frame.get_column(source_well_column).drop_nulls().cast(pl.Utf8).str.strip_chars().to_list()
            if value
        )

    return tuple(sorted(well_ids))


def get_available_well_ids() -> list[str]:
    source_signatures = tuple(
        signature
        for signature in (
            _source_signature(TELEMETRY_FILE_PATH),
            _source_signature(MEASUREMENTS_FILE_PATH),
            _source_signature(POWER_DAILY_FILE_PATH),
        )
        if signature is not None
    )
    if source_signatures:
        well_ids = list(_load_available_well_ids_cached(source_signatures))
        if well_ids:
            logger.info("Returning %s unique well ids from aggregated source headers", len(well_ids))
            return well_ids

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


def clear_timeseries_cache() -> None:
    """Drop cached CSV frames after aggregated telemetry files are regenerated."""
    _load_timeseries_frame_cached.cache_clear()
    _load_aggregated_timeseries_frame_cached.cache_clear()
    _load_available_well_ids_cached.cache_clear()


def get_timeseries_frame() -> pl.DataFrame:
    """Return the cached normalized telemetry frame for read-only aggregate services."""
    return _load_timeseries_frame()


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
        .with_columns(pl.col("date").dt.strftime("%Y-%m-%dT%H:%M:%S"))
        .to_dicts()
    )
