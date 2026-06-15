from __future__ import annotations

import math
from datetime import date, datetime, time, timedelta
from typing import Literal

import polars as pl

from app.schemas.period_summary import PeriodSummaryResponse, PeriodSummaryRow
from app.services.auto_episodes import get_candidate_auto_episode_intervals
from app.services.csv_timeseries import get_timeseries_frame


PeriodPreset = Literal["week", "month", "year", "custom"]
METRIC_COLUMNS = [
    "qliq",
    "water_cut",
    "intake_pressure",
    "esp_frequency",
    "load",
    "gas_factor",
    "bdpv_volume_rate",
]


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


def _round_metric(value: float | None) -> float | None:
    if value is None or not math.isfinite(value):
        return None
    return round(value, 2)


def _oil_rate(qliq: float | None, water_cut: float | None) -> float | None:
    if qliq is None or water_cut is None:
        return None
    return _round_metric(qliq * (1 - water_cut / 100) * 0.82)


def _delta(left: float | None, right: float | None) -> float | None:
    if left is None or right is None:
        return None
    return _round_metric(right - left)


def _mean_metrics(frame: pl.DataFrame, start_at: datetime, end_at: datetime) -> dict[str, float | None]:
    if frame.is_empty():
        return {column: None for column in METRIC_COLUMNS}

    window = frame.filter((pl.col("date") >= pl.lit(start_at)) & (pl.col("date") <= pl.lit(end_at)))
    if window.is_empty():
        return {column: None for column in METRIC_COLUMNS}

    values = window.select([pl.col(column).mean().alias(column) for column in METRIC_COLUMNS]).to_dicts()[0]
    return {column: _round_metric(values.get(column)) for column in METRIC_COLUMNS}


def _resolve_period(
    frame: pl.DataFrame,
    preset: PeriodPreset,
    date_from: date | None,
    date_to: date | None,
) -> tuple[datetime, datetime]:
    max_date = frame.select(pl.col("date").max()).item() if not frame.is_empty() else None
    end_at = datetime.combine(date_to, time.max) if date_to else max_date
    if not isinstance(end_at, datetime):
        end_at = datetime.now()

    if preset == "custom" and date_from and date_to:
        return datetime.combine(date_from, time.min), datetime.combine(date_to, time.max)

    days_by_preset = {
        "week": 7,
        "month": 31,
        "year": 365,
    }
    days = days_by_preset.get(preset, 7)
    return end_at - timedelta(days=days), end_at


def _interval_overlaps_period(interval: dict[str, object], period_start: datetime, period_end: datetime) -> bool:
    start_at = _parse_datetime(interval.get("startDate"))
    end_at = _parse_datetime(interval.get("endDate"), end_of_day=True)
    if start_at is None or end_at is None:
        return False
    return start_at <= period_end and end_at >= period_start


def _is_stop_or_gdi(label: str) -> bool:
    normalized = label.casefold().replace("ё", "е")
    return "останов" in normalized or normalized == "гди" or "гди" in normalized


def _is_deferred_effect(label: str) -> bool:
    normalized = label.casefold().replace("ё", "е")
    return "рптч" in normalized or "период" in normalized


def _interval_duration_days(start_at: datetime, end_at: datetime) -> float:
    return round(max((end_at - start_at).total_seconds() / 86400, 1 / 1440), 3)


def _is_stop_or_gdi(label: str) -> bool:
    normalized = label.casefold().replace("\u0451", "\u0435").strip()
    return (
        "stop" in normalized
        or "gdi" in normalized
        or "\u043e\u0441\u0442\u0430\u043d\u043e\u0432" in normalized
        or "\u0433\u0434\u0438" in normalized
    )


def _is_deferred_effect(label: str) -> bool:
    normalized = label.casefold().replace("\u0451", "\u0435").strip()
    return (
        "rptch" in normalized
        or "periodic" in normalized
        or "\u0440\u043f\u0442\u0447" in normalized
        or "\u043f\u0435\u0440\u0438\u043e\u0434" in normalized
    )


def build_period_summary(
    preset: PeriodPreset = "week",
    date_from: date | None = None,
    date_to: date | None = None,
    field_code: str | None = None,
    well_id: str | None = None,
) -> PeriodSummaryResponse:
    frame = get_timeseries_frame()
    period_start, period_end = _resolve_period(frame, preset, date_from, date_to)
    if period_end < period_start:
        period_start, period_end = period_end, period_start

    period_span = max(period_end - period_start, timedelta(minutes=1))
    window_days = (period_span * 0.2).total_seconds() / 86400
    allowed_fields = _split_filter(field_code)
    allowed_wells = _split_filter(well_id)

    intervals = sorted(
        [
            interval
            for interval in get_candidate_auto_episode_intervals()
            if _interval_overlaps_period(interval, period_start, period_end)
            and str(interval.get("wellId", "")).strip()
            and str(interval.get("label", "")).strip()
            and (not allowed_wells or str(interval.get("wellId", "")).strip() in allowed_wells)
            and (not allowed_fields or _field_code(str(interval.get("wellId", "")).strip()) in allowed_fields)
        ],
        key=lambda item: (
            str(item.get("wellId", "")),
            str(item.get("startDate", "")),
            str(item.get("endDate", "")),
            str(item.get("label", "")),
        ),
    )

    rows: list[PeriodSummaryRow] = []
    for interval in intervals:
        well_id = str(interval.get("wellId", "")).strip()
        category = str(interval.get("label", "")).strip()
        interval_start = _parse_datetime(interval.get("startDate"))
        interval_end = _parse_datetime(interval.get("endDate"), end_of_day=True)
        if interval_start is None or interval_end is None:
            continue

        duration_days = _interval_duration_days(interval_start, interval_end)
        well_frame = frame.filter(pl.col("well_id") == pl.lit(well_id))
        interval_span = max(interval_end - interval_start, timedelta(minutes=1))
        interval_window = interval_span * 0.2
        first = _mean_metrics(well_frame, interval_start, interval_start + interval_window)
        second = _mean_metrics(well_frame, interval_end - interval_window, interval_end)
        qoil_1 = _oil_rate(first["qliq"], first["water_cut"])
        qoil_2 = _oil_rate(second["qliq"], second["water_cut"])
        delta_qliq = _delta(first["qliq"], second["qliq"])
        delta_qoil = _delta(qoil_1, qoil_2)
        stop_qliq: float | None = None
        accumulated_qliq: float | None = None
        accumulated_qoil: float | None = None

        if _is_stop_or_gdi(category):
            stop_baseline = _mean_metrics(well_frame, interval_start - interval_window, interval_start)
            stop_qliq = stop_baseline["qliq"] if stop_baseline["qliq"] is not None else first["qliq"]
            stop_qoil = _oil_rate(stop_qliq, stop_baseline["water_cut"])
            if stop_qoil is None:
                stop_qoil = qoil_1
            accumulated_qliq = _round_metric(stop_qliq * duration_days) if stop_qliq is not None else None
            accumulated_qoil = _round_metric(stop_qoil * duration_days) if stop_qoil is not None else None
            first = {key: None for key in METRIC_COLUMNS}
            second = {key: None for key in METRIC_COLUMNS}
            qoil_1 = None
            qoil_2 = None
            delta_qliq = None
            delta_qoil = None
        elif _is_deferred_effect(category):
            first = {key: None for key in METRIC_COLUMNS}
            second = {key: None for key in METRIC_COLUMNS}
            qoil_1 = None
            qoil_2 = None
            delta_qliq = None
            delta_qoil = None
        else:
            accumulated_qliq = _round_metric(delta_qliq * duration_days) if delta_qliq is not None else None
            accumulated_qoil = _round_metric(delta_qoil * duration_days) if delta_qoil is not None else None

        rows.append(
            PeriodSummaryRow(
                field_code=_field_code(well_id),
                well_id=well_id,
                category=category,
                interval_start=interval_start.isoformat(timespec="seconds"),
                interval_end=interval_end.isoformat(timespec="seconds"),
                duration_days=duration_days,
                stop_qliq=stop_qliq,
                qliq_1=first["qliq"],
                qliq_2=second["qliq"],
                qoil_1=qoil_1,
                qoil_2=qoil_2,
                water_cut_1=first["water_cut"],
                water_cut_2=second["water_cut"],
                intake_pressure_1=first["intake_pressure"],
                intake_pressure_2=second["intake_pressure"],
                frequency_1=first["esp_frequency"],
                frequency_2=second["esp_frequency"],
                load_1=first["load"],
                load_2=second["load"],
                gas_factor_1=first["gas_factor"],
                gas_factor_2=second["gas_factor"],
                bdpv_1=first["bdpv_volume_rate"],
                bdpv_2=second["bdpv_volume_rate"],
                delta_qliq=delta_qliq,
                delta_qoil=delta_qoil,
                accumulated_qliq=accumulated_qliq,
                accumulated_qoil=accumulated_qoil,
            )
        )

    return PeriodSummaryResponse(
        period_start=period_start.isoformat(timespec="seconds"),
        period_end=period_end.isoformat(timespec="seconds"),
        window_days=round(window_days, 2),
        rows=rows,
    )
