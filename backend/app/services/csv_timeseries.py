from __future__ import annotations

import csv
import logging
import re
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
import polars as pl

from app.core.config import settings
from app.services.ozna import load_ozna_sessions
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
FULL_TIMESERIES_COLUMN_MAPPING = {
    "well_id": "well_id",
    "date": "telemetry_time",
    "qliq": "telemetry_qliq",
    "predicted_qliq": "telemetry_predicted_qliq",
    "buffer_pressure": "telemetry_buffer_pressure",
    "casing_pressure": "telemetry_casing_pressure",
    "load": "telemetry_load",
    "water_cut": "telemetry_water_cut",
    "intake_pressure": "telemetry_intake_pressure",
    "esp_frequency": "telemetry_esp_frequency",
    "active_power": "telemetry_active_power",
    "bdpv_volume_rate": "telemetry_bdpv_volume_rate",
    "bdpv_water_flow": "telemetry_bdpv_water_flow",
    "collector_pressure": "telemetry_collector_pressure",
    "full_power": "telemetry_full_power",
    "qoil": "telemetry_qoil",
    "qgas": "telemetry_qgas",
    "gas_factor": "telemetry_gas_factor",
    "gas_liquid_factor": "telemetry_gas_liquid_factor",
    "qliq_wfm": "telemetry_qliq_wfm",
    "qliq_vfm": "telemetry_qliq_vfm",
}
PVT_REQUIRED_COLUMNS = {
    "field": "Field short",
    "pressure": "Давление, бар",
    "oil_density": "Плотность нефти при давлении, кг/м3",
    "rs": "Газосодержание, м3/м3",
    "bg": "Объемный коэффициент газа, безр",
    "gas_density": "Плотность газа при давлении, кг/м3",
    "bo": "Объемный коэффициент нефти, безр",
}
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
    "water_cut_hal_density",
    "water_cut_hal_daily",
    "water_cut_algo",
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
    "free_gas_pct",
    "qliq_wfm",
    "ozna_qliq",
    "ozna_qliq_p10",
    "ozna_qliq_p90",
    "ozna_qliq_cv_pct",
    "ozna_qoil",
    "ozna_qoil_p10",
    "ozna_qoil_p90",
    "ozna_qoil_cv_pct",
    "ozna_qgas",
    "ozna_qgas_p10",
    "ozna_qgas_p90",
    "ozna_qgas_cv_pct",
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
    "water_cut_hal_density",
    "water_cut_hal_daily",
    "water_cut_algo",
    "water_cut_mode",
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
    "free_gas_pct",
    "qliq_wfm",
    "qliq_vfm",
    "ozna_session_id",
    "ozna_duration_min",
    "ozna_n_points",
    "ozna_quality_flags",
    "ozna_source_files",
    "ozna_qliq",
    "ozna_qliq_p10",
    "ozna_qliq_p90",
    "ozna_qliq_cv_pct",
    "ozna_qoil",
    "ozna_qoil_p10",
    "ozna_qoil_p90",
    "ozna_qoil_cv_pct",
    "ozna_qgas",
    "ozna_qgas_p10",
    "ozna_qgas_p90",
    "ozna_qgas_cv_pct",
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
    "water_cut_hal_density": pl.Float64,
    "water_cut_hal_daily": pl.Float64,
    "water_cut_algo": pl.Float64,
    "water_cut_mode": pl.Utf8,
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
    "free_gas_pct": pl.Float64,
    "qliq_wfm": pl.Float64,
    "qliq_vfm": pl.Float64,
    "ozna_session_id": pl.Utf8,
    "ozna_duration_min": pl.Float64,
    "ozna_n_points": pl.Int64,
    "ozna_quality_flags": pl.Utf8,
    "ozna_source_files": pl.Utf8,
    "ozna_qliq": pl.Float64,
    "ozna_qliq_p10": pl.Float64,
    "ozna_qliq_p90": pl.Float64,
    "ozna_qliq_cv_pct": pl.Float64,
    "ozna_qoil": pl.Float64,
    "ozna_qoil_p10": pl.Float64,
    "ozna_qoil_p90": pl.Float64,
    "ozna_qoil_cv_pct": pl.Float64,
    "ozna_qgas": pl.Float64,
    "ozna_qgas_p10": pl.Float64,
    "ozna_qgas_p90": pl.Float64,
    "ozna_qgas_cv_pct": pl.Float64,
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

    iso_value = cleaned.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(iso_value)
        if parsed.tzinfo is not None:
            return parsed.replace(tzinfo=None)
        return parsed
    except ValueError:
        pass

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


def _is_finite_number(value: object) -> bool:
    return isinstance(value, (int, float, np.integer, np.floating)) and np.isfinite(float(value))


def _well_pvt_key(well_id: object) -> str:
    prefix = str(well_id or "").split("_", 1)[0].strip()
    return "AZ" if prefix == "Az" else prefix


@lru_cache(maxsize=4)
def _load_pvt_curves_cached(pvt_path: str, mtime_ns: int, size: int) -> dict[str, dict[str, np.ndarray]]:
    path = Path(pvt_path)
    if not path.exists():
        logger.warning("PVT workbook is unavailable at %s; free_gas_pct will be empty", path)
        return {}

    try:
        pvt = pd.read_excel(path, sheet_name=0, engine="openpyxl")
    except Exception as exc:
        logger.warning("Failed to load PVT workbook %s; free_gas_pct will be empty: %s", path, exc)
        return {}

    missing = [column for column in PVT_REQUIRED_COLUMNS.values() if column not in pvt.columns]
    if missing:
        logger.warning("PVT workbook %s is missing columns %s; free_gas_pct will be empty", path, missing)
        return {}

    pvt = pvt.rename(
        columns={
            PVT_REQUIRED_COLUMNS["field"]: "field",
            PVT_REQUIRED_COLUMNS["pressure"]: "pressure_bar",
            PVT_REQUIRED_COLUMNS["oil_density"]: "rho_o_p",
            PVT_REQUIRED_COLUMNS["rs"]: "Rs",
            PVT_REQUIRED_COLUMNS["bg"]: "Bg",
            PVT_REQUIRED_COLUMNS["gas_density"]: "rho_g_p",
            PVT_REQUIRED_COLUMNS["bo"]: "Bo",
        }
    )
    pvt["pvt_key"] = pvt["field"].map(lambda value: "AZ" if str(value).strip() == "Az" else str(value).strip())
    for column in ("pressure_bar", "rho_o_p", "Rs", "Bg", "rho_g_p", "Bo"):
        pvt[column] = pd.to_numeric(pvt[column], errors="coerce")

    curves: dict[str, dict[str, np.ndarray]] = {}
    for key, group in pvt[pvt["pvt_key"].ne("")].groupby("pvt_key", sort=True):
        curve = (
            group.groupby("pressure_bar", as_index=False)
            .agg(
                Rs=("Rs", "median"),
                Bg=("Bg", "median"),
                Bo=("Bo", "median"),
                rho_o_p=("rho_o_p", "median"),
                rho_g_p=("rho_g_p", "median"),
            )
            .replace([np.inf, -np.inf], np.nan)
            .dropna()
            .sort_values("pressure_bar")
        )
        if len(curve) < 2:
            continue
        curves[str(key)] = {
            column: curve[column].to_numpy(dtype=float)
            for column in ("pressure_bar", "Rs", "Bg", "Bo", "rho_o_p", "rho_g_p")
        }

    if not curves:
        logger.warning("PVT workbook %s has no usable curves; free_gas_pct will be empty", path)
        return {}

    logger.info("Loaded %s PVT curves from %s for free gas calculation", len(curves), path)
    return curves


def _load_pvt_curves() -> dict[str, dict[str, np.ndarray]]:
    path = settings.episodes_compute_pvt_data_path
    if not path.exists():
        return _load_pvt_curves_cached(str(path), 0, 0)
    stat = path.stat()
    return _load_pvt_curves_cached(str(path), stat.st_mtime_ns, stat.st_size)


def _interpolate_pvt(curve: dict[str, np.ndarray], pressure_bar: object) -> dict[str, float] | None:
    if not _is_finite_number(pressure_bar):
        return None
    pressure = float(pressure_bar)
    pressure_grid = curve["pressure_bar"]
    if pressure < float(pressure_grid[0]) or pressure > float(pressure_grid[-1]):
        return None
    return {
        column: float(np.interp(pressure, pressure_grid, curve[column]))
        for column in ("Rs", "Bg", "Bo", "rho_o_p", "rho_g_p")
    }


def _select_water_cut_pct(row: dict[str, object]) -> float | None:
    for column in ("water_cut_algo", "water_cut"):
        value = row.get(column)
        if _is_finite_number(value):
            water_cut = float(value)
            if 0.0 <= water_cut <= 100.0:
                return water_cut
    return None


def _calculate_free_gas_pct(
    row: dict[str, object],
    gas_liquid_factor: float,
    curves: dict[str, dict[str, np.ndarray]],
) -> float | None:
    if gas_liquid_factor < 0:
        return None

    curve = curves.get(_well_pvt_key(row.get("well_id")))
    if curve is None:
        return None

    pvt = _interpolate_pvt(curve, row.get("intake_pressure"))
    water_cut = _select_water_cut_pct(row)
    if pvt is None or water_cut is None:
        return None

    oil_fraction = 1.0 - water_cut / 100.0
    rho_g_std = pvt["rho_g_p"] * pvt["Bg"]
    rho_o_std = pvt["rho_o_p"] * pvt["Bo"] - pvt["Rs"] * rho_g_std
    r_total = gas_liquid_factor * rho_o_std / 1000.0
    tolerance = max(10.0, 0.10 * r_total)
    r_free = max(r_total - pvt["Rs"] - tolerance, 0.0)
    gas = r_free * oil_fraction * pvt["Bg"]
    liquid = oil_fraction * pvt["Bo"] + (1.0 - oil_fraction) * 1.0
    denominator = gas + liquid
    if denominator <= 0:
        return None

    gvf = gas / denominator
    if not (650.0 <= rho_o_std <= 1000.0):
        return None
    if not (0.3 <= rho_g_std <= 2.0):
        return None
    if not (0.0 <= gvf <= 1.0):
        return None

    return round(100.0 * gvf, 2)


def _add_free_gas_pct(frame: pl.DataFrame) -> pl.DataFrame:
    if frame.is_empty():
        return frame

    curves = _load_pvt_curves()
    if not curves:
        return frame.with_columns(pl.lit(None).cast(pl.Float64).alias("free_gas_pct"))

    rows = frame.select(
        [
            pl.int_range(pl.len(), dtype=pl.UInt32).alias("_row_index"),
            "well_id",
            "date",
            "intake_pressure",
            "gas_liquid_factor",
            "water_cut",
            "water_cut_algo",
        ]
    ).iter_rows(named=True)
    sorted_rows = sorted(
        rows,
        key=lambda row: (str(row.get("well_id") or ""), row.get("date") or datetime.min, row["_row_index"]),
    )
    values: list[float | None] = [None] * frame.height

    current_well: str | None = None
    current_group: list[dict[str, object]] = []
    for row in sorted_rows:
        well_id = str(row.get("well_id") or "")
        if current_well is None:
            current_well = well_id
        if well_id != current_well:
            _fill_free_gas_values_for_well(current_group, values, curves)
            current_group = []
            current_well = well_id
        current_group.append(row)
    if current_group:
        _fill_free_gas_values_for_well(current_group, values, curves)

    return frame.with_columns(pl.Series("free_gas_pct", values, dtype=pl.Float64))


def _with_derived_gas_factor(frame: pl.DataFrame) -> pl.DataFrame:
    if frame.is_empty() or "qgas" not in frame.columns or "qoil" not in frame.columns:
        return frame

    gas_factor_expr = (
        pl.when((pl.col("qgas") >= 0) & (pl.col("qoil") > 0))
        .then(pl.col("qgas") / pl.col("qoil"))
        .otherwise(pl.col("gas_factor"))
        .round(6)
        .alias("gas_factor")
    )
    gas_liquid_factor_expr = (
        pl.when((pl.col("qgas") >= 0) & (pl.col("qliq") > 0))
        .then(pl.col("qgas") / pl.col("qliq"))
        .otherwise(pl.col("gas_liquid_factor"))
        .round(6)
        .alias("gas_liquid_factor")
    )
    return frame.with_columns(gas_factor_expr, gas_liquid_factor_expr)


def _fill_free_gas_values_for_well(
    rows: list[dict[str, object]],
    values: list[float | None],
    curves: dict[str, dict[str, np.ndarray]],
) -> None:
    last_glf: float | None = None
    last_glf_date: datetime | None = None

    for row in rows:
        row_index = int(row["_row_index"])
        row_date = row.get("date")
        if isinstance(row_date, date) and not isinstance(row_date, datetime):
            row_date = datetime.combine(row_date, datetime.min.time())
        if not isinstance(row_date, datetime):
            continue

        current_glf = row.get("gas_liquid_factor")
        if _is_finite_number(current_glf) and float(current_glf) >= 0:
            last_glf = float(current_glf)
            last_glf_date = row_date

        if last_glf is None or last_glf_date is None:
            continue

        glf_age_days = (row_date - last_glf_date).total_seconds() / 86400.0
        if glf_age_days < 0 or glf_age_days > 5:
            continue

        values[row_index] = _calculate_free_gas_pct(row, last_glf, curves)


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
    row["ozna_session_id"] = None
    row["ozna_quality_flags"] = None
    row["ozna_source_files"] = None
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
    qoil = row["qoil"]
    qgas = row["qgas"]

    if not isinstance(qgas, float) and isinstance(qoil, float) and isinstance(row["gas_factor"], float):
        row["qgas"] = round(qoil * row["gas_factor"], 2)
        qgas = row["qgas"]

    if isinstance(qgas, float) and isinstance(qoil, float) and qoil:
        row["gas_factor"] = round(qgas / qoil, 6)

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

    full_timeseries_path = settings.episodes_compute_enriched_data_path
    if full_timeseries_path.exists():
        full_stat = full_timeseries_path.stat()
        water_cut_hal_stat = WATER_CUT_HAL_FILE_PATH.stat() if WATER_CUT_HAL_FILE_PATH.exists() else None
        predicted_qliq_stat = PREDICTED_QLIQ_FILE_PATH.stat() if PREDICTED_QLIQ_FILE_PATH.exists() else None
        return _load_full_timeseries_frame_cached(
            str(full_timeseries_path),
            full_stat.st_mtime_ns,
            full_stat.st_size,
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
        reader = csv.DictReader(csv_file, delimiter=_detect_csv_delimiter(path))
        headers = reader.fieldnames or []
        well_column = _pick_csv_column(headers, ("well_id", "name"))
        date_column = _pick_csv_column(headers, ("date", "sample_datetime"))
        value_column = _pick_csv_column(headers, ("water_cut_hal", "water_cut", "hal"))
        density_column = _pick_csv_column(headers, ("water_cut_hal_density", "water_density"))
        if well_column is None or date_column is None or value_column is None:
            logger.warning("Water cut HAL CSV %s is missing expected columns", path)
            return rows

        for raw_row in reader:
            well_id = _clean_cell(raw_row.get(well_column))
            point_datetime = _parse_datetime(raw_row.get(date_column))
            water_cut = _parse_float(raw_row.get(value_column))
            if not _is_valid_well_id(well_id) or point_datetime is None or water_cut is None:
                skipped_rows += 1
                continue

            row = _build_empty_timeseries_row(well_id, point_datetime)
            row["water_cut_hal"] = water_cut
            if density_column is not None:
                row["water_cut_hal_density"] = _parse_float(raw_row.get(density_column))
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


def _load_ozna_session_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    skipped_rows = 0
    for session in load_ozna_sessions():
        well_id = _clean_cell(session.get("well_code"))
        point_datetime = _parse_datetime(session.get("mid_at"))
        if not _is_valid_well_id(well_id) or point_datetime is None:
            skipped_rows += 1
            continue

        row = _build_empty_timeseries_row(well_id, point_datetime)
        row["ozna_session_id"] = _clean_cell(session.get("session_id"))
        row["ozna_duration_min"] = _parse_float(session.get("duration_min"))
        n_points = _parse_float(session.get("n_points"))
        row["ozna_n_points"] = int(n_points) if n_points is not None else None
        row["ozna_quality_flags"] = _clean_cell(session.get("quality_flags")) or None
        row["ozna_source_files"] = _clean_cell(session.get("source_files")) or None
        row["ozna_qliq"] = _parse_float(session.get("qliq_median"))
        row["ozna_qliq_p10"] = _parse_float(session.get("qliq_p10"))
        row["ozna_qliq_p90"] = _parse_float(session.get("qliq_p90"))
        row["ozna_qliq_cv_pct"] = _parse_float(session.get("qliq_cv_pct"))
        row["ozna_qoil"] = _parse_float(session.get("qoil_tpd_median"))
        row["ozna_qoil_p10"] = _parse_float(session.get("qoil_tpd_p10"))
        row["ozna_qoil_p90"] = _parse_float(session.get("qoil_tpd_p90"))
        row["ozna_qoil_cv_pct"] = _parse_float(session.get("qoil_tpd_cv_pct"))
        row["ozna_qgas"] = _parse_float(session.get("qgas_median"))
        row["ozna_qgas_p10"] = _parse_float(session.get("qgas_p10"))
        row["ozna_qgas_p90"] = _parse_float(session.get("qgas_p90"))
        row["ozna_qgas_cv_pct"] = _parse_float(session.get("qgas_cv_pct"))
        rows.append(_finalize_timeseries_row(row))

    logger.info(
        "Loaded %s OZNA session rows%s",
        len(rows),
        f"; skipped {skipped_rows} rows" if skipped_rows else "",
    )
    return rows


@lru_cache(maxsize=2)
def _load_full_timeseries_frame_cached(
    csv_path: str,
    csv_mtime_ns: int,
    csv_size: int,
    water_cut_hal_path: str,
    water_cut_hal_mtime_ns: int,
    water_cut_hal_size: int,
    predicted_qliq_path: str,
    predicted_qliq_mtime_ns: int,
    predicted_qliq_size: int,
) -> pl.DataFrame:
    path = Path(csv_path)
    logger.info("Loading full telemetry from %s", path)
    with path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        header = next(csv.reader(csv_file), [])

    source_columns = [
        source
        for target, source in FULL_TIMESERIES_COLUMN_MAPPING.items()
        if source in header and target in FRAME_SCHEMA
    ]
    if "well_id" not in source_columns or "telemetry_time" not in source_columns:
        logger.warning("Full telemetry CSV %s is missing well_id/telemetry_time", path)
        return pl.DataFrame(schema=FRAME_SCHEMA)

    source_to_target = {source: target for target, source in FULL_TIMESERIES_COLUMN_MAPPING.items()}
    raw = pl.read_csv(
        path,
        columns=source_columns,
        infer_schema_length=1000,
        null_values=list(NULL_TOKENS),
        encoding="utf8-lossy",
    )
    expressions: list[pl.Expr] = []
    for source in source_columns:
        target = source_to_target[source]
        if target == "well_id":
            expressions.append(pl.col(source).cast(pl.Utf8, strict=False).str.strip_chars().alias(target))
        elif target == "date":
            expressions.append(pl.col(source).cast(pl.Utf8, strict=False).str.strptime(pl.Datetime, strict=False).alias(target))
        else:
            expressions.append(pl.col(source).cast(pl.Float64, strict=False).alias(target))

    frame = raw.select(expressions)
    missing_columns = [column for column in FRAME_SCHEMA if column not in frame.columns]
    if missing_columns:
        frame = frame.with_columns([pl.lit(None, dtype=FRAME_SCHEMA[column]).alias(column) for column in missing_columns])

    frame = (
        frame.select(list(FRAME_SCHEMA))
        .filter(
            pl.col("well_id").map_elements(_is_valid_well_id, return_dtype=pl.Boolean)
            & pl.col("date").is_not_null()
        )
        .with_columns(
            pl.coalesce([pl.col("qliq_vfm"), pl.col("qliq_wfm")]).alias("qliq_vfm"),
            pl.coalesce([pl.col("predicted_qliq"), pl.col("qliq_vfm"), pl.col("qliq_wfm")]).alias("predicted_qliq"),
        )
    )

    extra_rows = [
        *(_load_water_cut_hal_rows(water_cut_hal_path) if water_cut_hal_path else []),
        *(_load_predicted_qliq_rows(predicted_qliq_path) if predicted_qliq_path else []),
        *_load_ozna_session_rows(),
    ]
    if extra_rows:
        frame = pl.concat([frame, pl.DataFrame(extra_rows, schema=FRAME_SCHEMA, strict=False)], how="vertical_relaxed")

    frame = _with_derived_gas_factor(frame)
    frame = add_water_cut_algorithm(frame)
    frame = _add_free_gas_pct(frame.sort(["well_id", "date"]))
    logger.info(
        "Loaded %s full telemetry rows for %s unique wells",
        frame.height,
        frame.select("well_id").n_unique(),
    )
    return frame


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
    missing_columns = [column for column in FRAME_SCHEMA if column not in frame.columns]
    if missing_columns:
        frame = frame.with_columns([pl.lit(None, dtype=FRAME_SCHEMA[column]).alias(column) for column in missing_columns])

    ozna_rows = _load_ozna_session_rows()
    if ozna_rows:
        frame = pl.concat([frame.select(list(FRAME_SCHEMA)), pl.DataFrame(ozna_rows, schema=FRAME_SCHEMA, strict=False)], how="vertical_relaxed")

    frame = _with_derived_gas_factor(frame)
    frame = add_water_cut_algorithm(frame)
    frame = _add_free_gas_pct(frame)
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
    rows.extend([row for row in _load_ozna_session_rows() if str(row.get("well_id") or "") in base_well_ids])

    frame = _with_derived_gas_factor(pl.DataFrame(rows, schema=FRAME_SCHEMA, strict=False).sort(["well_id", "date"]))
    frame = add_water_cut_algorithm(frame)
    frame = _add_free_gas_pct(frame)
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


# Matches the minimum telemetry-row threshold episode_rules_v12_8.py's compute()
# uses to skip a well ("a['telemetry_time'].notna().sum() < 20") — a well with fewer
# rows than this has no meaningful telemetry, even if it has a stray water_cut_hal/
# predicted_qliq row merged in for display purposes elsewhere.
MIN_TELEMETRY_ROWS_FOR_WELL = 20


@lru_cache(maxsize=2)
def _load_enriched_well_ids_cached(path: str, path_mtime_ns: int, path_size: int) -> tuple[str, ...]:
    if path_size <= 0:
        return ()

    source = Path(path)
    if not source.exists():
        return ()

    try:
        frame = pl.read_csv(source, columns=["well_id", "telemetry_time"], infer_schema_length=1000)
    except Exception:
        logger.exception("Failed to read well ids from enriched telemetry %s", source)
        return ()

    counts = (
        frame.filter(pl.col("telemetry_time").is_not_null())
        .group_by("well_id")
        .agg(pl.len().alias("telemetry_rows"))
        .filter(pl.col("telemetry_rows") >= MIN_TELEMETRY_ROWS_FOR_WELL)
    )
    well_ids = {
        value
        for value in counts.get_column("well_id").drop_nulls().cast(pl.Utf8).str.strip_chars().to_list()
        if _is_valid_well_id(value)
    }
    return tuple(sorted(well_ids))


def get_available_well_ids() -> list[str]:
    # Prefer the enriched telemetry CSV directly: it is the ONLY source that
    # distinguishes wells with real telemetry from wells that merely have a
    # water_cut_hal/predicted_qliq row merged into the display frame elsewhere.
    enriched_path = settings.episodes_compute_enriched_data_path
    if enriched_path.exists():
        stat = enriched_path.stat()
        well_ids = list(_load_enriched_well_ids_cached(str(enriched_path), stat.st_mtime_ns, stat.st_size))
        if well_ids:
            logger.info("Returning %s unique well ids with real telemetry from %s", len(well_ids), enriched_path)
            return well_ids

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
        frame.sort("date")
        .select(RESPONSE_COLUMNS)
        .with_columns(pl.col("date").dt.strftime("%Y-%m-%dT%H:%M:%S"))
        .to_dicts()
    )
