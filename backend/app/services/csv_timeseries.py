from __future__ import annotations

import csv
import logging
import re
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path

import polars as pl

from app.core.config import settings
from app.services.predicted_qliq import ensure_predicted_qliq_cache
from app.services.water_cut_algorithm import add_water_cut_algorithm


logger = logging.getLogger(__name__)

CSV_FILE_PATH = settings.csv_data_path
TELEMETRY_FILE_PATH = settings.telemetry_aggregated_data_path
MEASUREMENTS_FILE_PATH = settings.measurements_data_path
POWER_DAILY_FILE_PATH = settings.power_daily_data_path
WATER_CUT_HAL_FILE_PATH = settings.water_cut_hal_data_path
PREDICTED_QLIQ_FILE_PATH = settings.predicted_qliq_data_path
NULL_TOKENS = {"", "—", "#ЗНАЧ!", "#ДЕЛ/0!"}
INVALID_WELL_IDS = {"Da_51Da_515", "Da_515Da_515"}
DUPLICATED_WELL_ID_PATTERN = re.compile(r"^([A-Za-z]+_\d+)\1$")
PREDICTED_QLIQ_WELL_COLUMNS = ("well_id", "well")
PREDICTED_QLIQ_DATE_COLUMNS = ("date", "telemetry_date", "telemetry_time")
PREDICTED_QLIQ_VALUE_COLUMNS = (
    "telemetry_predicted_qliq",
    "predicted_qliq",
    "predicted_q_liquid",
    "predicted_liquid_rate",
    "qliq_pred",
    "q_liq_pred",
    "pred_qliq",
)
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
    "predicted_qliq",
    "buffer_pressure",
    "casing_pressure",
    "load",
    "water_cut",
    "water_cut_hal",
    "water_cut_algorithm",
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
    "predicted_qliq",
    "buffer_pressure",
    "casing_pressure",
    "load",
    "water_cut",
    "water_cut_hal",
    "water_cut_algorithm",
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
    "predicted_qliq": pl.Float64,
    "buffer_pressure": pl.Float64,
    "casing_pressure": pl.Float64,
    "load": pl.Float64,
    "water_cut": pl.Float64,
    "water_cut_hal": pl.Float64,
    "water_cut_algorithm": pl.Float64,
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


def _is_valid_well_id(value: str | None) -> bool:
    cleaned = _clean_cell(value)
    return bool(cleaned) and cleaned not in INVALID_WELL_IDS and DUPLICATED_WELL_ID_PATTERN.match(cleaned) is None


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


def _normalize_csv_header(value: str | None) -> str:
    return re.sub(r"[^a-z0-9_]+", "_", _clean_cell(value).lower()).strip("_")


def _detect_csv_delimiter(path: Path) -> str:
    try:
        sample = path.read_text(encoding="utf-8-sig", errors="ignore")[:4096]
    except OSError:
        return ";"

    if not sample:
        return ";"

    try:
        return csv.Sniffer().sniff(sample, delimiters=";,").delimiter
    except csv.Error:
        return ";" if sample.count(";") >= sample.count(",") else ","


def _pick_csv_column(headers: list[str], aliases: tuple[str, ...]) -> str | None:
    by_normalized_name = {_normalize_csv_header(header): header for header in headers}
    for alias in aliases:
        column = by_normalized_name.get(_normalize_csv_header(alias))
        if column is not None:
            return column
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
        source_names = (
            [COLUMN_MAPPING[normalized_name]]
            if normalized_name in COLUMN_MAPPING
            else [normalized_name, f"telemetry_{normalized_name}"]
        )
        raw_value = None
        for source_name in source_names:
            raw_value = _get_row_value(raw_row, column_indexes, source_name)
            if raw_value is not None:
                break
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
    if not isinstance(row["predicted_qliq"], float) and isinstance(row["qliq_vfm"], float):
        row["predicted_qliq"] = row["qliq_vfm"]
    return row


def _use_aggregated_sources() -> bool:
    return settings.telemetry_data_path != settings.reference_data_path


def _load_timeseries_frame() -> pl.DataFrame:
    if _use_aggregated_sources() and TELEMETRY_FILE_PATH.exists() and MEASUREMENTS_FILE_PATH.exists() and POWER_DAILY_FILE_PATH.exists():
        try:
            ensure_predicted_qliq_cache()
        except Exception as exc:
            logger.warning("Predicted Q liquid cache refresh failed; using existing cache if available: %s", exc)

        telemetry_stat = TELEMETRY_FILE_PATH.stat()
        measurements_stat = MEASUREMENTS_FILE_PATH.stat()
        power_daily_stat = POWER_DAILY_FILE_PATH.stat()
        water_cut_hal_stat = WATER_CUT_HAL_FILE_PATH.stat() if WATER_CUT_HAL_FILE_PATH.exists() else None
        predicted_qliq_stat = PREDICTED_QLIQ_FILE_PATH.stat() if PREDICTED_QLIQ_FILE_PATH.exists() else None
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
            str(WATER_CUT_HAL_FILE_PATH) if water_cut_hal_stat else "",
            water_cut_hal_stat.st_mtime_ns if water_cut_hal_stat else 0,
            water_cut_hal_stat.st_size if water_cut_hal_stat else 0,
            str(PREDICTED_QLIQ_FILE_PATH) if predicted_qliq_stat else "",
            predicted_qliq_stat.st_mtime_ns if predicted_qliq_stat else 0,
            predicted_qliq_stat.st_size if predicted_qliq_stat else 0,
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
            if not _is_valid_well_id(well_id) or point_datetime is None:
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


def _load_water_cut_hal_rows(csv_path: str) -> list[dict[str, object]]:
    path = Path(csv_path)
    if not path.exists():
        return []

    rows: list[dict[str, object]] = []
    skipped_rows = 0
    with path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file, delimiter=";")
        for raw_row in reader:
            well_id = _clean_cell(raw_row.get("well_id"))
            point_datetime = _parse_datetime(raw_row.get("date"))
            water_cut = _parse_float(raw_row.get("water_cut_hal"))
            if not _is_valid_well_id(well_id) or point_datetime is None or water_cut is None:
                skipped_rows += 1
                continue

            row = _build_empty_timeseries_row(well_id, point_datetime)
            row["water_cut_hal"] = water_cut
            rows.append(_finalize_timeseries_row(row))

    logger.info(
        "Loaded %s rows from water cut HAL CSV %s%s",
        len(rows),
        path,
        f"; skipped {skipped_rows} rows" if skipped_rows else "",
    )
    return rows


def _load_predicted_qliq_rows(csv_path: str) -> list[dict[str, object]]:
    path = Path(csv_path)
    if not path.exists():
        return []

    rows: list[dict[str, object]] = []
    skipped_rows = 0
    with path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file, delimiter=_detect_csv_delimiter(path))
        headers = reader.fieldnames or []
        well_column = _pick_csv_column(headers, PREDICTED_QLIQ_WELL_COLUMNS)
        date_column = _pick_csv_column(headers, PREDICTED_QLIQ_DATE_COLUMNS)
        value_column = _pick_csv_column(headers, PREDICTED_QLIQ_VALUE_COLUMNS)
        if well_column is None or date_column is None or value_column is None:
            logger.warning("Predicted Q liquid CSV %s is missing expected columns", path)
            return rows

        for raw_row in reader:
            well_id = _clean_cell(raw_row.get(well_column))
            point_datetime = _parse_datetime(raw_row.get(date_column))
            predicted_qliq = _parse_float(raw_row.get(value_column))
            if not _is_valid_well_id(well_id) or point_datetime is None or predicted_qliq is None:
                skipped_rows += 1
                continue

            row = _build_empty_timeseries_row(well_id, point_datetime)
            row["predicted_qliq"] = predicted_qliq
            rows.append(_finalize_timeseries_row(row))

    logger.info(
        "Loaded %s rows from predicted Q liquid CSV %s%s",
        len(rows),
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
    water_cut_hal_path: str,
    water_cut_hal_mtime_ns: int,
    water_cut_hal_size: int,
    predicted_qliq_path: str,
    predicted_qliq_mtime_ns: int,
    predicted_qliq_size: int,
) -> pl.DataFrame:
    logger.info("Loading aggregated telemetry from %s, %s and %s", telemetry_path, measurements_path, power_daily_path)
    logger.debug(
        (
            "Aggregated cache keys telemetry=(%s,%s) measurements=(%s,%s) power_daily=(%s,%s) "
            "water_cut_hal=(%s,%s) predicted_qliq=(%s,%s)"
        ),
        telemetry_mtime_ns,
        telemetry_size,
        measurements_mtime_ns,
        measurements_size,
        power_daily_mtime_ns,
        power_daily_size,
        water_cut_hal_mtime_ns,
        water_cut_hal_size,
        predicted_qliq_mtime_ns,
        predicted_qliq_size,
    )
    rows = [
        *_load_aggregated_source_rows(telemetry_path, TELEMETRY_COLUMNS, "telemetry"),
        *_load_aggregated_source_rows(measurements_path, MEASUREMENT_COLUMNS, "measurements"),
        *_load_aggregated_source_rows(power_daily_path, POWER_DAILY_COLUMNS, "power_daily"),
        *(_load_water_cut_hal_rows(water_cut_hal_path) if water_cut_hal_path else []),
        *(_load_predicted_qliq_rows(predicted_qliq_path) if predicted_qliq_path else []),
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
    frame = add_water_cut_algorithm(frame)
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
            if not _is_valid_well_id(well_id) or point_date is None:
                skipped_rows += 1
                continue

            row = _build_empty_timeseries_row(well_id, datetime.combine(point_date, datetime.min.time()))
            _fill_numeric_values(row, raw_row, column_indexes, NUMERIC_COLUMNS)
            rows.append(_finalize_timeseries_row(row))

    if not rows:
        logger.warning("CSV file %s produced no valid well rows", CSV_FILE_PATH)
        return pl.DataFrame(schema=FRAME_SCHEMA)

    base_well_ids = {str(row["well_id"]) for row in rows if row.get("well_id")}

    # The primary CSV (well_metrics_v9.csv) has no HAL water-cut column, so merge
    # the standalone HAL points here as well — otherwise HAL water-cut points are
    # missing whenever the app runs without the aggregated telemetry sources.
    if WATER_CUT_HAL_FILE_PATH.exists():
        hal_rows = [
            row
            for row in _load_water_cut_hal_rows(str(WATER_CUT_HAL_FILE_PATH))
            if str(row.get("well_id") or "") in base_well_ids
        ]
        if hal_rows:
            rows.extend(hal_rows)
    if PREDICTED_QLIQ_FILE_PATH.exists():
        predicted_rows = [
            row
            for row in _load_predicted_qliq_rows(str(PREDICTED_QLIQ_FILE_PATH))
            if str(row.get("well_id") or "") in base_well_ids
        ]
        if predicted_rows:
            rows.extend(predicted_rows)

    frame = add_water_cut_algorithm(pl.DataFrame(rows, schema=FRAME_SCHEMA, strict=False).sort(["well_id", "date"]))
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
            if _is_valid_well_id(value)
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
    ) if _use_aggregated_sources() else ()
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
        .filter(pl.col("well_id").map_elements(_is_valid_well_id, return_dtype=pl.Boolean))
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
