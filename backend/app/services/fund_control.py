from __future__ import annotations

import math
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from functools import lru_cache
from typing import Literal

import polars as pl

from app.core.config import settings
from app.schemas.fund_control import (
    FundControlFactorSummaryRow,
    FundControlResponse,
    FundControlWellFactorRow,
)
from app.services.auto_episodes import get_candidate_auto_episode_intervals
from app.services.csv_timeseries import get_timeseries_frame


FundControlPreset = Literal["week", "month", "quarter", "year", "custom"]
FACTOR_KEYS = [
    "stop_gdi",
    "frequency",
    "periodic",
    "complicated",
    "water_supply",
    "nur",
    "kprod",
    "reservoir_pressure",
    "gas_factor",
]
BUCKET_KEYS = ["calibration_tr", "background"]
GAS_FACTOR_CHANGE = 0.10
SMOOTH_WINDOW_DAYS = 5
PRECOMPUTED_WELL_FACTOR_PATH = settings.reference_data_path / "fund_control_well_factor.csv"
PRECOMPUTED_DAILY_PATH = settings.reference_data_path / "fund_control_daily.csv"
PRECOMPUTED_VFM_DAILY_PATH = settings.reference_data_path / "vfm_daily.csv"
INVALID_WELL_IDS = {"Da_515Da_515", "Da_51Da_515", "Da_515"}

FACTOR_META = {
    "stop_gdi": ("ГДИ / остановка", "Интерпретация ГДИ", None),
    "frequency": ("Частота / РПТЧ", "Пересмотр режима работы", "Пересмотр режима работы"),
    "periodic": ("Периодическая работа", "Пересмотр режима работы", "Пересмотр режима работы"),
    "complicated": ("Осложнённый фонд", "Пересмотр режима работы", "Пересмотр режима работы"),
    "water_supply": ("Подача воды / СППВ", "Пересмотр режима работы", "Пересмотр режима работы"),
    "nur": ("НУР", "Пересмотр режима работы", None),
    "kprod": ("Кпрод", "ОПЗ", None),
    "reservoir_pressure": ("Рпл", "Анализ ячейки заводнения", "Оценка оптимизации"),
    "gas_factor": ("Газовый фактор", "Анализ ячейки заводнения / корр. режима ЭЦН", None),
}


def _field_code(well_id: str) -> str:
    return well_id.split("_", 1)[0] if "_" in well_id else ""


def _split_filter(value: str | None) -> set[str]:
    if not value:
        return set()
    return {item.strip() for item in value.split(",") if item.strip()}


def _parse_datetime(value: object, *, end_of_day: bool = False) -> datetime | None:
    if value is None:
        return None
    raw_value = str(value).strip()
    if not raw_value:
        return None

    normalized = raw_value.replace(" ", "T")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        try:
            parsed_date = date.fromisoformat(raw_value[:10])
        except ValueError:
            return None
        return datetime.combine(parsed_date, time.max if end_of_day else time.min)

    if "T" not in normalized:
        return datetime.combine(parsed.date(), time.max if end_of_day else time.min)
    return parsed


def _round(value: float | None, digits: int = 1) -> float | None:
    if value is None or not math.isfinite(value):
        return None
    return round(float(value), digits)


def _to_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        return number if math.isfinite(number) else None
    text = str(value).strip().replace(",", ".")
    if not text or text.lower() in {"nan", "none", "null"}:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    return number if math.isfinite(number) else None


def _row_value(record: dict[str, object], key: str, default: float = 0.0) -> float:
    return _to_float(record.get(key)) or default


def _resolve_period(
    frame: pl.DataFrame,
    preset: FundControlPreset,
    date_from: date | None,
    date_to: date | None,
) -> tuple[datetime, datetime]:
    max_date = frame.select(pl.col("date").max()).item() if not frame.is_empty() else None
    end_at = datetime.combine(date_to, time.max) if date_to else max_date
    if isinstance(end_at, date) and not isinstance(end_at, datetime):
        end_at = datetime.combine(end_at, time.max)
    if not isinstance(end_at, datetime):
        end_at = datetime.now()

    if preset == "custom" and date_from and date_to:
        return datetime.combine(date_from, time.min), datetime.combine(date_to, time.max)

    days_by_preset = {"week": 7, "month": 31, "quarter": 92, "year": 365}
    start_at = end_at - timedelta(days=days_by_preset.get(preset, 7))
    return datetime.combine(start_at.date(), time.min), end_at


@lru_cache(maxsize=4)
def _load_precomputed_rows(path_key: str, mtime_ns: int) -> list[FundControlWellFactorRow]:
    path = PRECOMPUTED_WELL_FACTOR_PATH
    if not path.exists():
        return []

    frame = pl.read_csv(path, infer_schema_length=0)
    unknown_columns = [
        column
        for column in frame.columns
        if column
        not in {
            "well_id",
            "field_code",
            "vQliq_start",
            "vQliq_end",
            "total_dQ",
            "stop_rate",
            "stop_gdi",
            "freq",
            "periodic",
            "complicated",
            "water",
            "nur",
            "kprod",
            "rpl",
            "gf",
            "_check",
        }
    ]
    calibration_column = unknown_columns[0] if len(unknown_columns) > 0 else ""
    background_column = unknown_columns[1] if len(unknown_columns) > 1 else ""

    rows: list[FundControlWellFactorRow] = []
    for record in frame.to_dicts():
        well_id = str(record.get("well_id") or "").strip()
        if not well_id or well_id in INVALID_WELL_IDS:
            continue

        rows.append(
            FundControlWellFactorRow(
                well_id=well_id,
                field_code=str(record.get("field_code") or _field_code(well_id)),
                vqliq_start=_to_float(record.get("vQliq_start")),
                vqliq_end=_to_float(record.get("vQliq_end")),
                total_delta=_to_float(record.get("total_dQ")),
                stop_rate=_to_float(record.get("stop_rate")),
                stop_gdi=_row_value(record, "stop_gdi"),
                frequency=_row_value(record, "freq"),
                periodic=_row_value(record, "periodic"),
                complicated=_row_value(record, "complicated"),
                water_supply=_row_value(record, "water"),
                nur=_row_value(record, "nur"),
                kprod=_row_value(record, "kprod"),
                reservoir_pressure=_row_value(record, "rpl"),
                gas_factor=_row_value(record, "gf"),
                calibration_tr=_row_value(record, calibration_column),
                background=_row_value(record, background_column),
                balance_error=_row_value(record, "_check"),
            )
        )
    rows.sort(key=lambda item: (item.field_code, item.well_id))
    return rows


@lru_cache(maxsize=4)
def _load_precomputed_daily(path_key: str, mtime_ns: int) -> pl.DataFrame:
    path = PRECOMPUTED_DAILY_PATH
    if not path.exists():
        return pl.DataFrame()

    frame = pl.read_csv(
        path,
        try_parse_dates=True,
        schema_overrides={
            "well_id": pl.Utf8,
            "field_code": pl.Utf8,
            "day": pl.Date,
            "vqliq_smooth": pl.Float64,
            "esp_frequency_smooth": pl.Float64,
            "active_power_smooth": pl.Float64,
            "gas_factor_smooth": pl.Float64,
        },
    )
    return frame.filter(~pl.col("well_id").is_in(list(INVALID_WELL_IDS))).sort(["well_id", "day"])


@lru_cache(maxsize=4)
def _load_vfm_daily(path_key: str, mtime_ns: int) -> pl.DataFrame:
    path = PRECOMPUTED_VFM_DAILY_PATH
    if not path.exists():
        return pl.DataFrame()

    frame = pl.read_csv(path, infer_schema_length=0)
    required = {"well_id", "date", "vQliq"}
    if not required.issubset(set(frame.columns)):
        return pl.DataFrame()

    expressions = [
        pl.col("well_id").cast(pl.Utf8, strict=False).str.strip_chars(),
        pl.col("date").cast(pl.Utf8, strict=False).str.to_date(strict=False).alias("day"),
        pl.col("vQliq").cast(pl.Utf8, strict=False).str.replace_all(",", ".").cast(pl.Float64, strict=False).alias("vqliq_smooth"),
    ]
    if "field_code" in frame.columns:
        expressions.append(pl.col("field_code").cast(pl.Utf8, strict=False).str.strip_chars())
    else:
        expressions.append(pl.col("well_id").cast(pl.Utf8, strict=False).str.split("_").list.first().alias("field_code"))
    if "telemetry_esp_frequency" in frame.columns:
        expressions.append(
            pl.col("telemetry_esp_frequency")
            .cast(pl.Utf8, strict=False)
            .str.replace_all(",", ".")
            .cast(pl.Float64, strict=False)
            .alias("esp_frequency_smooth")
        )
    else:
        expressions.append(pl.lit(None, dtype=pl.Float64).alias("esp_frequency_smooth"))
    if "telemetry_active_power" in frame.columns:
        expressions.append(
            pl.col("telemetry_active_power")
            .cast(pl.Utf8, strict=False)
            .str.replace_all(",", ".")
            .cast(pl.Float64, strict=False)
            .alias("active_power_smooth")
        )
    else:
        expressions.append(pl.lit(None, dtype=pl.Float64).alias("active_power_smooth"))
    if "telemetry_gas_factor" in frame.columns:
        expressions.append(
            pl.col("telemetry_gas_factor")
            .cast(pl.Utf8, strict=False)
            .str.replace_all(",", ".")
            .cast(pl.Float64, strict=False)
            .alias("gas_factor_smooth")
        )
    else:
        expressions.append(pl.lit(None, dtype=pl.Float64).alias("gas_factor_smooth"))

    return (
        frame.with_columns(expressions)
        .filter(
            (~pl.col("well_id").is_in(list(INVALID_WELL_IDS)))
            & pl.col("day").is_not_null()
            & pl.col("vqliq_smooth").is_not_null()
        )
        .select(
            "well_id",
            "field_code",
            "day",
            "vqliq_smooth",
            "esp_frequency_smooth",
            "active_power_smooth",
            "gas_factor_smooth",
        )
        .unique(subset=["well_id", "day"], keep="last")
        .sort(["well_id", "day"])
    )


def _build_precomputed_fund_control(
    preset: FundControlPreset,
    date_from: date | None,
    date_to: date | None,
    field_code: str | None,
    well_id: str | None,
) -> FundControlResponse | None:
    if PRECOMPUTED_VFM_DAILY_PATH.exists() or PRECOMPUTED_DAILY_PATH.exists():
        if PRECOMPUTED_VFM_DAILY_PATH.exists():
            daily = _load_vfm_daily(str(PRECOMPUTED_VFM_DAILY_PATH), PRECOMPUTED_VFM_DAILY_PATH.stat().st_mtime_ns)
        else:
            daily = _load_precomputed_daily(str(PRECOMPUTED_DAILY_PATH), PRECOMPUTED_DAILY_PATH.stat().st_mtime_ns)
        if daily.is_empty():
            return None

        period_start, period_end = _resolve_period(daily.rename({"day": "date"}), preset, date_from, date_to)
        if period_end < period_start:
            period_start, period_end = period_end, period_start
        allowed_fields = _split_filter(field_code)
        allowed_wells = _split_filter(well_id)
        period_start_day = period_start.date()
        period_end_day = period_end.date()
        source_start_day = (period_start - timedelta(days=SMOOTH_WINDOW_DAYS + 1)).date()

        daily = daily.filter(
            (pl.col("day") >= pl.lit(source_start_day))
            & (pl.col("day") <= pl.lit(period_end_day))
            & (pl.col("vqliq_smooth").is_not_null())
        )
        if allowed_wells:
            daily = daily.filter(pl.col("well_id").is_in(list(allowed_wells)))
        if allowed_fields:
            daily = daily.filter(pl.col("field_code").is_in(list(allowed_fields)))

        factors_by_day = _build_factor_days(period_start, period_end, allowed_wells, allowed_fields)
        rows = [
            row
            for _, group in daily.partition_by("well_id", as_dict=True).items()
            if (row := _attribute_well(group.sort("day").to_dicts(), factors_by_day)) is not None
        ]
        rows.sort(key=lambda item: (item.field_code, item.well_id))
        max_error = max((abs(row.balance_error) for row in rows), default=0.0)
        return FundControlResponse(
            period_start=period_start.isoformat(timespec="seconds"),
            period_end=period_end.isoformat(timespec="seconds"),
            rows=rows,
            factors=_factor_summary(rows),
            max_abs_balance_error=round(max_error, 4),
            balance_check_passed=max_error <= 0.01,
        )

    if not PRECOMPUTED_WELL_FACTOR_PATH.exists():
        return None

    rows = _load_precomputed_rows(str(PRECOMPUTED_WELL_FACTOR_PATH), PRECOMPUTED_WELL_FACTOR_PATH.stat().st_mtime_ns)
    allowed_fields = _split_filter(field_code)
    allowed_wells = _split_filter(well_id)
    if allowed_wells:
        rows = [row for row in rows if row.well_id in allowed_wells]
    if allowed_fields:
        rows = [row for row in rows if row.field_code in allowed_fields]

    max_error = max((abs(row.balance_error) for row in rows), default=0.0)
    if preset == "custom" and date_from and date_to:
        period_start = datetime.combine(date_from, time.min)
        period_end = datetime.combine(date_to, time.max)
    else:
        mtime = datetime.fromtimestamp(PRECOMPUTED_WELL_FACTOR_PATH.stat().st_mtime)
        days_by_preset = {"week": 7, "month": 31, "quarter": 92, "year": 365}
        period_end = mtime
        period_start = datetime.combine((mtime - timedelta(days=days_by_preset.get(preset, 7))).date(), time.min)

    return FundControlResponse(
        period_start=period_start.isoformat(timespec="seconds"),
        period_end=period_end.isoformat(timespec="seconds"),
        rows=rows,
        factors=_factor_summary(rows),
        max_abs_balance_error=round(max_error, 4),
        balance_check_passed=max_error <= 0.01,
    )


def _factor_from_label(label: str) -> str | None:
    normalized = label.casefold().replace("ё", "е").strip()
    if not normalized:
        return None
    if "останов" in normalized or normalized == "гди" or "гди" in normalized:
        return "stop_gdi"
    if "рптч" in normalized or "увч" in normalized or "умч" in normalized or "част" in normalized:
        return "frequency"
    if "период" in normalized:
        return "periodic"
    if "ослож" in normalized:
        return "complicated"
    if "сппв" in normalized or "подач" in normalized:
        return "water_supply"
    if "нур" in normalized:
        return "nur"
    if "кпрод" in normalized:
        return "kprod"
    if "рпл" in normalized:
        return "reservoir_pressure"
    if "гф" in normalized or "газов" in normalized or "вгф" in normalized:
        return "gas_factor"
    return None


# Final clean runtime mapping. Older generated blocks above contain mojibake
# labels and are kept only to avoid a broad refactor in this hot path.
FACTOR_META = {
    "stop_gdi": ("ГДИ / остановка / пуск", "Интерпретация ГДИ или запуск после остановки", None),
    "frequency": ("Частота / РПТЧ", "Пересмотр режима работы", "Пересмотр режима работы"),
    "periodic": ("Периодическая работа", "Пересмотр режима работы", "Пересмотр режима работы"),
    "complicated": ("Осложненный фонд", "Пересмотр режима работы", "Пересмотр режима работы"),
    "water_supply": ("Подача воды / СППВ", "Пересмотр подачи воды", "Пересмотр подачи воды"),
    "nur": ("НУР", "Пересмотр режима работы", None),
    "kprod": ("Кпрод", "ОПЗ", None),
    "reservoir_pressure": ("Рпл", "Анализ ячейки заводнения", "Оценка оптимизации"),
    "gas_factor": ("Газовый фактор", "Анализ газового фактора", None),
}


def _factor_from_label(label: str) -> str | None:
    normalized = label.casefold().replace("ё", "е").strip()
    if not normalized:
        return None
    if "останов" in normalized or normalized == "гди" or "гди" in normalized:
        return "stop_gdi"
    if "рптч" in normalized or "увч" in normalized or "умч" in normalized or "част" in normalized:
        return "frequency"
    if "период" in normalized:
        return "periodic"
    if "ослож" in normalized:
        return "complicated"
    if "сппв" in normalized or "подач" in normalized:
        return "water_supply"
    if "нур" in normalized:
        return "nur"
    if "кпрод" in normalized:
        return "kprod"
    if "рпл" in normalized:
        return "reservoir_pressure"
    if "гф" in normalized or "газов" in normalized or "вгф" in normalized:
        return "gas_factor"
    return None


FACTOR_META = {
    "stop_gdi": ("ГДИ / остановка", "Интерпретация ГДИ", None),
    "frequency": ("Частота / РПТЧ", "Пересмотр режима работы", "Пересмотр режима работы"),
    "periodic": ("Периодическая работа", "Пересмотр режима работы", "Пересмотр режима работы"),
    "complicated": ("Осложнённый фонд", "Пересмотр режима работы", "Пересмотр режима работы"),
    "water_supply": ("Подача воды / СППВ", "Пересмотр режима работы", "Пересмотр режима работы"),
    "nur": ("НУР", "Пересмотр режима работы", None),
    "kprod": ("Кпрод", "ОПЗ", None),
    "reservoir_pressure": ("Рпл", "Анализ ячейки заводнения", "Оценка оптимизации"),
    "gas_factor": ("Газовый фактор", "Анализ ячейки заводнения / корр. режима ЭЦН", None),
}


def _factor_from_label(label: str) -> str | None:
    normalized = label.casefold().replace("ё", "е").strip()
    if not normalized:
        return None
    if "останов" in normalized or normalized == "гди" or "гди" in normalized:
        return "stop_gdi"
    if "рптч" in normalized or "увч" in normalized or "умч" in normalized or "част" in normalized:
        return "frequency"
    if "период" in normalized:
        return "periodic"
    if "ослож" in normalized:
        return "complicated"
    if "сппв" in normalized or "подач" in normalized:
        return "water_supply"
    if "нур" in normalized:
        return "nur"
    if "кпрод" in normalized:
        return "kprod"
    if "рпл" in normalized:
        return "reservoir_pressure"
    if "гф" in normalized or "газов" in normalized or "вгф" in normalized:
        return "gas_factor"
    return None


def _build_daily_frame(source: pl.DataFrame) -> pl.DataFrame:
    if source.is_empty():
        return source

    value_columns = [
        "predicted_qliq",
        "qliq_vfm",
        "qliq_wfm",
        "qliq",
        "esp_frequency",
        "active_power",
        "gas_factor",
    ]
    aggregations = [pl.col(column).median().alias(column) for column in value_columns if column in source.columns]
    daily = (
        source.with_columns(pl.col("date").dt.date().alias("day"))
        .group_by(["well_id", "day"])
        .agg(aggregations)
        .sort(["well_id", "day"])
    )

    if "predicted_qliq" not in daily.columns:
        daily = daily.with_columns(pl.lit(None, dtype=pl.Float64).alias("predicted_qliq"))
    if "qliq_vfm" not in daily.columns:
        daily = daily.with_columns(pl.lit(None, dtype=pl.Float64).alias("qliq_vfm"))
    if "qliq_wfm" not in daily.columns:
        daily = daily.with_columns(pl.lit(None, dtype=pl.Float64).alias("qliq_wfm"))
    if "qliq" not in daily.columns:
        daily = daily.with_columns(pl.lit(None, dtype=pl.Float64).alias("qliq"))

    daily = daily.with_columns(pl.coalesce(["predicted_qliq", "qliq_vfm", "qliq_wfm", "qliq"]).alias("vqliq"))
    for column in ("vqliq", "esp_frequency", "active_power", "gas_factor"):
        if column in daily.columns:
            daily = daily.with_columns(
                pl.col(column)
                .rolling_median(window_size=SMOOTH_WINDOW_DAYS, min_samples=1)
                .over("well_id")
                .alias(f"{column}_smooth")
            )
    return daily


def _build_factor_days(
    period_start: datetime,
    period_end: datetime,
    allowed_wells: set[str],
    allowed_fields: set[str],
) -> dict[tuple[str, date], set[str]]:
    factors_by_day: dict[tuple[str, date], set[str]] = defaultdict(set)
    start_day = period_start.date()
    end_day = period_end.date()
    for interval in get_candidate_auto_episode_intervals():
        well_id = str(interval.get("wellId", "")).strip()
        if not well_id:
            continue
        if allowed_wells and well_id not in allowed_wells:
            continue
        if allowed_fields and _field_code(well_id) not in allowed_fields:
            continue

        factor = _factor_from_label(str(interval.get("label", "")))
        if factor is None:
            continue

        interval_start = _parse_datetime(interval.get("startDate"))
        interval_end = _parse_datetime(interval.get("endDate"), end_of_day=True)
        if interval_start is None or interval_end is None:
            continue
        if interval_start > period_end or interval_end < period_start:
            continue

        day = max(interval_start.date(), start_day)
        last_day = min(interval_end.date(), end_day)
        while day <= last_day:
            factors_by_day[(well_id, day)].add(factor)
            day += timedelta(days=1)
    return factors_by_day


def _active_factors(row: dict[str, object], previous_row: dict[str, object] | None, episode_factors: set[str]) -> list[str]:
    active = set(episode_factors)
    if previous_row is not None:
        gas = row.get("gas_factor_smooth")
        previous_gas = previous_row.get("gas_factor_smooth")
        if (
            isinstance(gas, (int, float))
            and isinstance(previous_gas, (int, float))
            and math.isfinite(float(gas))
            and math.isfinite(float(previous_gas))
            and float(previous_gas) > 0
            and abs(float(gas) / float(previous_gas) - 1) > GAS_FACTOR_CHANGE
        ):
            active.add("gas_factor")
    return [factor for factor in FACTOR_KEYS if factor in active]


def _attribute_well(rows: list[dict[str, object]], factors_by_day: dict[tuple[str, date], set[str]]) -> FundControlWellFactorRow | None:
    sequence = [row for row in rows if isinstance(row.get("vqliq_smooth"), (int, float))]
    if len(sequence) < 2:
        return None

    well_id = str(sequence[-1]["well_id"])
    contrib = {key: 0.0 for key in [*FACTOR_KEYS, *BUCKET_KEYS]}
    stop_rate: float | None = None

    for index in range(1, len(sequence)):
        previous_row = sequence[index - 1]
        row = sequence[index]
        previous_q = float(previous_row["vqliq_smooth"])
        q = float(row["vqliq_smooth"])
        delta_q = q - previous_q

        if q == 0 and previous_q > 0:
            contrib["stop_gdi"] += delta_q
            stop_rate = previous_q
            continue
        if previous_q == 0 and q > 0:
            contrib["stop_gdi"] += delta_q
            continue

        day = row["day"]
        if isinstance(day, datetime):
            day = day.date()
        if not isinstance(day, date):
            contrib["background"] += delta_q
            continue

        active = _active_factors(row, previous_row, factors_by_day.get((well_id, day), set()))
        if not active:
            contrib["background"] += delta_q
            continue

        share = delta_q / len(active)
        for factor in active:
            contrib[factor] += share

    first_q = float(sequence[0]["vqliq_smooth"])
    last_q = float(sequence[-1]["vqliq_smooth"])
    total = last_q - first_q
    balance_error = sum(contrib.values()) - total

    return FundControlWellFactorRow(
        well_id=well_id,
        field_code=_field_code(well_id),
        vqliq_start=_round(first_q),
        vqliq_end=_round(last_q),
        total_delta=_round(total),
        stop_rate=_round(stop_rate),
        stop_gdi=_round(contrib["stop_gdi"]) or 0.0,
        frequency=_round(contrib["frequency"]) or 0.0,
        periodic=_round(contrib["periodic"]) or 0.0,
        complicated=_round(contrib["complicated"]) or 0.0,
        water_supply=_round(contrib["water_supply"]) or 0.0,
        nur=_round(contrib["nur"]) or 0.0,
        kprod=_round(contrib["kprod"]) or 0.0,
        reservoir_pressure=_round(contrib["reservoir_pressure"]) or 0.0,
        gas_factor=_round(contrib["gas_factor"]) or 0.0,
        calibration_tr=_round(contrib["calibration_tr"]) or 0.0,
        background=_round(contrib["background"]) or 0.0,
        balance_error=round(balance_error, 4),
    )


def _factor_summary(rows: list[FundControlWellFactorRow]) -> list[FundControlFactorSummaryRow]:
    result: list[FundControlFactorSummaryRow] = []
    for key in FACTOR_KEYS:
        name, action_loss, action_gain = FACTOR_META[key]
        values = [(row.well_id, float(getattr(row, key))) for row in rows]
        losses = sorted([(well, value) for well, value in values if value < 0], key=lambda item: item[1])[:5]
        gains = sorted([(well, value) for well, value in values if value > 0], key=lambda item: item[1], reverse=True)[:5]
        result.append(
            FundControlFactorSummaryRow(
                factor=name,
                total=round(sum(value for _, value in values), 1),
                sum_loss=round(sum(value for _, value in values if value < 0), 1),
                sum_gain=round(sum(value for _, value in values if value > 0), 1),
                top5_down="; ".join(f"{well}:{value:.0f}" for well, value in losses),
                top5_up="; ".join(f"{well}:{value:.0f}" for well, value in gains),
                action_loss=action_loss,
                action_gain=action_gain,
            )
        )
    return result


def build_fund_control(
    preset: FundControlPreset = "week",
    date_from: date | None = None,
    date_to: date | None = None,
    field_code: str | None = None,
    well_id: str | None = None,
) -> FundControlResponse:
    precomputed = _build_precomputed_fund_control(preset, date_from, date_to, field_code, well_id)
    if precomputed is not None:
        return precomputed

    source = get_timeseries_frame()
    virtual_qliq_columns = [
        column
        for column in ("predicted_qliq", "qliq_vfm", "qliq_wfm", "qliq")
        if column in source.columns
    ]
    period_source = (
        source.filter(pl.coalesce(virtual_qliq_columns).is_not_null())
        if virtual_qliq_columns
        else source
    )
    period_start, period_end = _resolve_period(period_source, preset, date_from, date_to)
    if period_end < period_start:
        period_start, period_end = period_end, period_start

    allowed_fields = _split_filter(field_code)
    allowed_wells = _split_filter(well_id)
    period_start_day = period_start.date()
    period_end_day = period_end.date()
    source_start = period_start - timedelta(days=SMOOTH_WINDOW_DAYS + 1)

    source = source.filter(
        (pl.col("date") >= pl.lit(source_start))
        & (pl.col("date") <= pl.lit(period_end))
    )
    if allowed_wells:
        source = source.filter(pl.col("well_id").is_in(list(allowed_wells)))
    if allowed_fields:
        source = source.filter(
            pl.col("well_id").map_elements(
                lambda value: _field_code(str(value)) in allowed_fields,
                return_dtype=pl.Boolean,
            )
        )

    daily = _build_daily_frame(source).filter(
        (pl.col("day") >= pl.lit(period_start_day))
        & (pl.col("day") <= pl.lit(period_end_day))
        & (pl.col("vqliq_smooth").is_not_null())
    )

    factors_by_day = _build_factor_days(period_start, period_end, allowed_wells, allowed_fields)
    rows = [
        row
        for _, group in daily.partition_by("well_id", as_dict=True).items()
        if (row := _attribute_well(group.sort("day").to_dicts(), factors_by_day)) is not None
    ]
    rows.sort(key=lambda item: (item.field_code, item.well_id))

    max_error = max((abs(row.balance_error) for row in rows), default=0.0)
    return FundControlResponse(
        period_start=period_start.isoformat(timespec="seconds"),
        period_end=period_end.isoformat(timespec="seconds"),
        rows=rows,
        factors=_factor_summary(rows),
        max_abs_balance_error=round(max_error, 4),
        balance_check_passed=max_error <= 0.01,
    )


# Keep these definitions last: older versions of this file contained mojibake labels.
# Runtime lookups in _factor_summary/_build_factor_days should use the clean UTF-8 map.
FACTOR_META = {
    "stop_gdi": ("ГДИ / остановка", "Интерпретация ГДИ", None),
    "frequency": ("Частота / РПТЧ", "Пересмотр режима работы", "Пересмотр режима работы"),
    "periodic": ("Периодическая работа", "Пересмотр режима работы", "Пересмотр режима работы"),
    "complicated": ("Осложнённый фонд", "Пересмотр режима работы", "Пересмотр режима работы"),
    "water_supply": ("Подача воды / СППВ", "Пересмотр режима работы", "Пересмотр режима работы"),
    "nur": ("НУР", "Пересмотр режима работы", None),
    "kprod": ("Кпрод", "ОПЗ", None),
    "reservoir_pressure": ("Рпл", "Анализ ячейки заводнения", "Оценка оптимизации"),
    "gas_factor": ("Газовый фактор", "Анализ ячейки заводнения / корр. режима ЭЦН", None),
}


def _factor_from_label(label: str) -> str | None:
    normalized = label.casefold().replace("ё", "е").strip()
    if not normalized:
        return None
    if "останов" in normalized or normalized == "гди" or "гди" in normalized:
        return "stop_gdi"
    if "рптч" in normalized or "увч" in normalized or "умч" in normalized or "част" in normalized:
        return "frequency"
    if "период" in normalized:
        return "periodic"
    if "ослож" in normalized:
        return "complicated"
    if "сппв" in normalized or "подач" in normalized:
        return "water_supply"
    if "нур" in normalized:
        return "nur"
    if "кпрод" in normalized:
        return "kprod"
    if "рпл" in normalized:
        return "reservoir_pressure"
    if "гф" in normalized or "газов" in normalized or "вгф" in normalized:
        return "gas_factor"
    return None

# Final clean runtime mapping. Older generated blocks above contain mojibake
# labels and are kept only to avoid a broad refactor in this hot path.
FACTOR_META = {
    "stop_gdi": ("ГДИ / остановка / пуск", "Интерпретация ГДИ или запуск после остановки", None),
    "frequency": ("Частота / РПТЧ", "Пересмотр режима работы", "Пересмотр режима работы"),
    "periodic": ("Периодическая работа", "Пересмотр режима работы", "Пересмотр режима работы"),
    "complicated": ("Осложненный фонд", "Пересмотр режима работы", "Пересмотр режима работы"),
    "water_supply": ("Подача воды / СППВ", "Пересмотр подачи воды", "Пересмотр подачи воды"),
    "nur": ("НУР", "Пересмотр режима работы", None),
    "kprod": ("Кпрод", "ОПЗ", None),
    "reservoir_pressure": ("Рпл", "Анализ ячейки заводнения", "Оценка оптимизации"),
    "gas_factor": ("Газовый фактор", "Анализ газового фактора", None),
}


def _factor_from_label(label: str) -> str | None:
    normalized = label.casefold().replace("ё", "е").strip()
    if not normalized:
        return None
    if "останов" in normalized or normalized == "гди" or "гди" in normalized:
        return "stop_gdi"
    if "рптч" in normalized or "увч" in normalized or "умч" in normalized or "част" in normalized:
        return "frequency"
    if "период" in normalized:
        return "periodic"
    if "ослож" in normalized:
        return "complicated"
    if "сппв" in normalized or "подач" in normalized:
        return "water_supply"
    if "нур" in normalized:
        return "nur"
    if "кпрод" in normalized:
        return "kprod"
    if "рпл" in normalized:
        return "reservoir_pressure"
    if "гф" in normalized or "газов" in normalized or "вгф" in normalized:
        return "gas_factor"
    return None
