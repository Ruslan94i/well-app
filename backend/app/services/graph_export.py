from __future__ import annotations

import csv
import logging
import time
from datetime import date, datetime, timedelta
from io import StringIO
from typing import Any

from app.schemas.markup import AutoEpisodeReview, FrequencyBreakpoint, FrequencyBreakpointSuppression, SavedAnnotation
from app.services.artificial_lift import get_well_artificial_lift_periods
from app.services.auto_episodes import get_well_candidate_auto_episode_intervals
from app.services.csv_timeseries import get_available_well_ids, get_well_timeseries
from app.services.json_markup import load_markup_state
from app.services.tr_monitoring import get_well_tr_monitoring
from app.services.vsp import get_well_vsp_periods
from app.services.xlsx_reference import get_well_context


SCHEMA_VERSION = "3"
FREQUENCY_CHANGE_THRESHOLD = 0.1
CSV_STREAM_CHUNK_ROWS = 1000
AUTO_ANNOTATION_ID_PREFIXES = ("auto-", "auto-inference-")
logger = logging.getLogger(__name__)
CLASSIFICATION_TO_TARGET = {
    "well_state=work": ("target_well_state", "Работа"),
    "well_state=stop": ("target_well_state", "Остановка"),
    "reservoir_pressure_trend=Pres_growth": ("target_rpl_trend", "rising"),
    "reservoir_pressure_trend=Pres_decline": ("target_rpl_trend", "falling"),
    "water_cut_trend=WCT_growth": ("target_wct_trend", "growing"),
    "productivity_trend=Kprod_decline": ("target_kprod_trend", "declining"),
    "esp_periodic=periodic_operation": ("target_periodic", "1"),
    "esp_uvch=uvch": ("target_uvch", "1"),
    "esp_uvch=umch": ("target_umch", "1"),
    "esp_rptch=rptch": ("target_rptch", "1"),
    "nur=nur_yes": ("target_nur", "1"),
    "gdi=gdi": ("target_gdi", "1"),
    "complicated_fund=slozhn_fond": ("target_complicated_fund", "1"),
    "sppv=sppv": ("target_sppv", "1"),
    "vgf=vgf_yes": ("target_vgf", "1"),
    "gas_factor_trend=GF_growth": ("target_gas_factor_trend", "rising"),
    "gas_factor_trend=GF_decline": ("target_gas_factor_trend", "falling"),
    "deoptimization=esp_limit": ("target_deoptimization", "esp_limit"),
    "deoptimization=infrastructure_limit": ("target_deoptimization", "infrastructure_limit"),
    "esp_degradation=degr_yes": ("target_esp_degradation", "1"),
}
TARGET_COLUMNS = [
    "target_well_state",
    "target_gdi",
    "target_uvch",
    "target_umch",
    "target_rptch",
    "target_periodic",
    "target_nur",
    "target_rpl_trend",
    "target_esp_degradation",
    "target_wct_trend",
    "target_kprod_trend",
    "target_complicated_fund",
    "target_sppv",
    "target_vgf",
    "target_gas_factor_trend",
    "target_deoptimization",
]
AUTO_TARGET_COLUMNS = [f"auto_{column}" for column in TARGET_COLUMNS]
AUTO_LABEL_TO_TARGET = {
    "работа": ("auto_target_well_state", "Работа"),
    "остановка": ("auto_target_well_state", "Остановка"),
    "гди": ("auto_target_gdi", "1"),
    "увч": ("auto_target_uvch", "1"),
    "умч": ("auto_target_umch", "1"),
    "рптч": ("auto_target_rptch", "1"),
    "периодическая работа": ("auto_target_periodic", "1"),
    "нур": ("auto_target_nur", "1"),
    "рост рпл": ("auto_target_rpl_trend", "rising"),
    "снижение рпл": ("auto_target_rpl_trend", "falling"),
    "деградация эцн": ("auto_target_esp_degradation", "1"),
    "рост обводненности": ("auto_target_wct_trend", "growing"),
    "снижение обводненности": ("auto_target_wct_trend", "falling"),
    "рост кпрод": ("auto_target_kprod_trend", "rising"),
    "снижение кпрод": ("auto_target_kprod_trend", "declining"),
    "осложненный фонд": ("auto_target_complicated_fund", "1"),
    "сппв": ("auto_target_sppv", "1"),
    "вгф": ("auto_target_vgf", "1"),
    "рост гф": ("auto_target_gas_factor_trend", "rising"),
    "снижение гф": ("auto_target_gas_factor_trend", "falling"),
    "ограничение эцн": ("auto_target_deoptimization", "esp_limit"),
    "ограничение инфраструктуры": ("auto_target_deoptimization", "infrastructure_limit"),
}
TELEMETRY_COLUMNS = [
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
TR_COLUMNS = [
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
EXPORT_COLUMNS = [
    "well_id",
    "field_code",
    "telemetry_time",
    "seconds_since_prev",
    "telemetry_date",
    *[f"telemetry_{column}" for column in TELEMETRY_COLUMNS],
    *[f"tr_{column}" for column in TR_COLUMNS],
    "tr_source_date",
    "esp_id",
    "esp_start_date",
    "esp_end_date",
    "esp_failure_date",
    "esp_lift_reason",
    "esp_size",
    "esp_nominal_rate",
    "esp_nominal_head",
    "esp_gas_separator_type",
    "esp_motor_power_kw",
    "esp_is_fountain",
    "vsp_status",
    "vsp_start_time",
    "vsp_end_time",
    "vsp_well_state",
    "vsp_well_state_code",
    *TARGET_COLUMNS,
    "auto_episode_ids",
    "auto_episode_labels",
    "auto_episode_start_dates",
    "auto_episode_end_dates",
    "auto_episode_confidences",
    *AUTO_TARGET_COLUMNS,
    "auto_episode_review_ids",
    "auto_episode_error_types",
    "auto_episode_error_comments",
    "frequency_segment_id",
    "frequency_segment_start_date",
    "frequency_segment_end_date",
    "frequency_breakpoint_id",
    "frequency_breakpoint_source",
    "frequency_breakpoint_reason",
    "frequency_breakpoint_from",
    "frequency_breakpoint_to",
    "gtm_ids",
    "gtm_names",
    "gtm_start_date",
    "gtm_end_date",
    "gtm_direction",
    "gtm_duration_days",
    "gtm_oil_before",
    "gtm_liquid_before",
    "gtm_water_cut_before",
    "gtm_oil_after",
    "gtm_liquid_after",
    "gtm_water_cut_after",
    "gtm_comment",
    "opz_ids",
    "opz_types",
    "opz_category",
    "opz_composition",
    "opz_volume",
    "opz_capex_opex",
    "opz_result",
    "opz_delta_oil",
    "opz_comment",
    "gdi_ids",
    "gdi_types",
    "gdi_start_date",
    "gdi_end_date",
    "gdi_accepted_vdp_pressure",
    "gdi_productivity_vogel",
    "gdi_quality",
    "gdi_executor",
    "gdi_duration_hours",
    "gdi_comment",
    "event_gtm",
    "event_opz",
    "event_gdi",
    "days_since_gtm",
    "days_since_opz",
    "days_since_gdi",
]


def _get_value(item: object, key: str) -> Any:
    if isinstance(item, dict):
        return item.get(key)
    return getattr(item, key, None)


def _date_key(value: object) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if value is None:
        return ""
    return str(value).strip()[:10]


def _parse_date(value: object) -> date | None:
    key = _date_key(value)
    if not key:
        return None
    try:
        return datetime.strptime(key, "%Y-%m-%d").date()
    except ValueError:
        return None


def _parse_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    if value is None:
        return None

    cleaned = str(value).strip()
    if not cleaned:
        return None

    for date_format in ("%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(cleaned, date_format)
        except ValueError:
            continue

    return None


def _format_cell(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat(sep=" ", timespec="seconds")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _join_values(values: list[object]) -> str:
    return " | ".join(_format_cell(value) for value in values if _format_cell(value))


def _join_field(items: list[object], field_name: str) -> str:
    return _join_values([_get_value(item, field_name) for item in items])


def _well_field_code(well_id: str) -> str:
    return well_id.split("_", 1)[0] if "_" in well_id else ""


def _frequency_value(value: object) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _is_positive_frequency(value: float | None) -> bool:
    return value is not None and value > 0


def _format_frequency(value: float | None) -> str:
    return "no data" if value is None else f"{value:.2f}".rstrip("0").rstrip(".")


def _create_frequency_breakpoint_id(source: str, well_id: str, point_date: str) -> str:
    return f"frequency-{source}-{well_id}-{point_date.replace('-', '').replace(':', '').replace('T', '')}"


def _upsert_auto_breakpoint(
    breakpoints_by_date: dict[str, dict[str, object]],
    breakpoint: dict[str, object],
) -> None:
    point_date = _format_cell(breakpoint.get("date"))
    existing = breakpoints_by_date.get(point_date)
    if not existing:
        breakpoints_by_date[point_date] = breakpoint
        return

    existing_reason = _format_cell(existing.get("reason"))
    breakpoint_reason = _format_cell(breakpoint.get("reason"))
    breakpoints_by_date[point_date] = {
        **existing,
        "reason": f"{existing_reason}; {breakpoint_reason}" if existing_reason else breakpoint_reason,
        "fromFrequency": existing.get("fromFrequency") or breakpoint.get("fromFrequency"),
        "toFrequency": existing.get("toFrequency") or breakpoint.get("toFrequency"),
    }


def _build_auto_frequency_breakpoints(
    telemetry_rows: list[dict[str, object]],
    well_id: str,
) -> list[dict[str, object]]:
    breakpoints_by_date: dict[str, dict[str, object]] = {}
    previous_point: dict[str, object] | None = None

    for point in telemetry_rows:
        frequency = _frequency_value(point.get("esp_frequency"))
        if frequency is None:
            continue

        if previous_point is not None:
            previous_frequency = _frequency_value(previous_point.get("frequency"))
            previous_date = _format_cell(previous_point.get("date"))
            point_date = _format_cell(point.get("date"))
            previous_is_positive = _is_positive_frequency(previous_frequency)
            current_is_positive = _is_positive_frequency(frequency)
            breakpoint_date = ""
            reason = ""

            if not previous_is_positive and current_is_positive:
                breakpoint_date = point_date
                reason = f"ESP frequency changed from 0 to {_format_frequency(frequency)}"
            elif previous_is_positive and not current_is_positive:
                breakpoint_date = previous_date
                reason = f"ESP frequency changed from {_format_frequency(previous_frequency)} to 0"
            elif previous_is_positive and current_is_positive and previous_frequency is not None:
                if frequency > previous_frequency:
                    increase_ratio = (frequency - previous_frequency) / previous_frequency
                    if increase_ratio >= FREQUENCY_CHANGE_THRESHOLD:
                        breakpoint_date = point_date
                        reason = f"ESP frequency increased by {round(increase_ratio * 100)}%"
                elif frequency < previous_frequency:
                    previous_was_higher_ratio = (previous_frequency - frequency) / frequency
                    if previous_was_higher_ratio >= FREQUENCY_CHANGE_THRESHOLD:
                        breakpoint_date = previous_date
                        reason = f"ESP frequency decrease: previous value higher by {round(previous_was_higher_ratio * 100)}%"

            if breakpoint_date and reason:
                _upsert_auto_breakpoint(
                    breakpoints_by_date,
                    {
                        "id": _create_frequency_breakpoint_id("auto", well_id, breakpoint_date),
                        "wellId": well_id,
                        "date": breakpoint_date,
                        "source": "auto",
                        "reason": reason,
                        "fromFrequency": previous_frequency,
                        "toFrequency": frequency,
                    },
                )

        previous_point = {
            "date": _format_cell(point.get("date")),
            "frequency": frequency,
        }

    return sorted(breakpoints_by_date.values(), key=lambda item: _format_cell(item.get("date")))


def _merge_frequency_breakpoints(
    auto_breakpoints: list[dict[str, object]],
    manual_breakpoints: list[FrequencyBreakpoint],
    suppressed_breakpoints: list[FrequencyBreakpointSuppression],
    well_id: str,
) -> list[dict[str, object]]:
    suppressed_dates = {
        suppression.date
        for suppression in suppressed_breakpoints
        if suppression.wellId == well_id
    }
    breakpoints_by_date: dict[str, dict[str, object]] = {}

    for breakpoint in auto_breakpoints:
        point_date = _format_cell(breakpoint.get("date"))
        if point_date not in suppressed_dates:
            breakpoints_by_date[point_date] = breakpoint

    for breakpoint in manual_breakpoints:
        if breakpoint.wellId != well_id:
            continue
        breakpoints_by_date[breakpoint.date] = {
            "id": breakpoint.id,
            "wellId": breakpoint.wellId,
            "date": breakpoint.date,
            "source": breakpoint.source,
            "reason": breakpoint.reason,
            "fromFrequency": breakpoint.fromFrequency,
            "toFrequency": breakpoint.toFrequency,
        }

    return sorted(breakpoints_by_date.values(), key=lambda item: _format_cell(item.get("date")))


def _build_frequency_segments(
    telemetry_rows: list[dict[str, object]],
    well_id: str,
    breakpoints: list[dict[str, object]],
) -> list[dict[str, object]]:
    if not telemetry_rows:
        return []

    start_date = _format_cell(telemetry_rows[0].get("date"))
    end_date = _format_cell(telemetry_rows[-1].get("date"))
    boundary_dates = [start_date]
    boundary_dates.extend(
        _format_cell(breakpoint.get("date"))
        for breakpoint in breakpoints
        if start_date < _format_cell(breakpoint.get("date")) <= end_date
    )
    unique_boundary_dates = sorted(set(boundary_dates), key=lambda value: _parse_datetime(value) or datetime.max)
    segments: list[dict[str, object]] = []

    for index, segment_start in enumerate(unique_boundary_dates):
        next_start = unique_boundary_dates[index + 1] if index + 1 < len(unique_boundary_dates) else ""
        if next_start:
            parsed_next = _parse_datetime(next_start)
            if parsed_next is None:
                continue
            segment_end = (parsed_next - timedelta(seconds=1)).isoformat()
        else:
            segment_end = end_date

        segment_start_time = _parse_datetime(segment_start)
        segment_end_time = _parse_datetime(segment_end)
        if segment_start_time is None or segment_end_time is None or segment_end_time < segment_start_time:
            continue

        segments.append(
            {
                "id": f"frequency-segment-{well_id}-{segment_start}-{segment_end}",
                "startDate": segment_start,
                "endDate": segment_end,
            }
        )

    return segments


def _prepare_datetime_intervals(items: list[object]) -> list[tuple[object, datetime, datetime]]:
    intervals: list[tuple[object, datetime, datetime]] = []
    for item in items:
        start_time = _parse_datetime(_get_value(item, "startDate"))
        end_time = _parse_datetime(_get_value(item, "endDate")) or datetime.max.replace(microsecond=0)
        if start_time is not None:
            intervals.append((item, start_time, end_time))
    return sorted(intervals, key=lambda item: item[1])


def _active_prepared_datetime_intervals(
    intervals: list[tuple[object, datetime, datetime]],
    point_time: datetime,
) -> list[object]:
    return [item for item, start_time, end_time in intervals if start_time <= point_time <= end_time]


class _DatetimeIntervalCursor:
    def __init__(self, intervals: list[tuple[object, datetime, datetime]]) -> None:
        self._intervals = intervals
        self._next_index = 0
        self._active: list[tuple[object, datetime, datetime]] = []

    def active_at(self, point_time: datetime) -> list[object]:
        while self._next_index < len(self._intervals) and self._intervals[self._next_index][1] <= point_time:
            self._active.append(self._intervals[self._next_index])
            self._next_index += 1

        if self._active:
            self._active = [
                (item, start_time, end_time)
                for item, start_time, end_time in self._active
                if end_time >= point_time
            ]

        return [item for item, _, _ in self._active]


class _StepwiseDateCursor:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self._rows = [
            (row_date, row)
            for row in rows
            if (row_date := _parse_date(row.get("date"))) is not None
        ]
        self._rows.sort(key=lambda item: item[0])
        self._next_index = 0
        self._active_row: dict[str, object] | None = None

    def active_at(self, point_date: date) -> dict[str, object] | None:
        while self._next_index < len(self._rows) and self._rows[self._next_index][0] <= point_date:
            self._active_row = self._rows[self._next_index][1]
            self._next_index += 1

        return self._active_row


class _EventTimeCursor:
    def __init__(self, event_times: list[datetime]) -> None:
        self._event_times = event_times
        self._next_index = 0
        self._latest_event_time: datetime | None = None

    def advance(self, point_time: datetime, previous_point_time: datetime | None) -> bool:
        triggered = False
        while self._next_index < len(self._event_times) and self._event_times[self._next_index] <= point_time:
            event_time = self._event_times[self._next_index]
            if previous_point_time is None:
                triggered = triggered or event_time.date() == point_time.date()
            else:
                triggered = triggered or previous_point_time < event_time <= point_time
            self._latest_event_time = event_time
            self._next_index += 1

        return triggered

    def days_since(self, point_time: datetime) -> float | None:
        if self._latest_event_time is None:
            return None

        return round((point_time - self._latest_event_time).total_seconds() / 86400, 6)


def _stepwise_tr_row(rows: list[dict[str, object]], point_date: date) -> dict[str, object] | None:
    active_row: dict[str, object] | None = None
    for row in rows:
        row_date = _parse_date(row.get("date"))
        if row_date is None:
            continue
        if row_date <= point_date:
            active_row = row
            continue
        break
    return active_row


def _events_by_date(items: list[object], date_field: str) -> dict[str, list[object]]:
    events: dict[str, list[object]] = {}
    for item in items:
        point_date = _date_key(_get_value(item, date_field))
        if point_date:
            events.setdefault(point_date, []).append(item)
    return events


def _event_datetimes(items: list[object], date_field: str) -> list[datetime]:
    event_times: list[datetime] = []
    for item in items:
        event_date = _parse_date(_get_value(item, date_field))
        if event_date is not None:
            event_times.append(datetime.combine(event_date, datetime.min.time()))
    return sorted(set(event_times))


def _is_first_telemetry_after_event(
    event_times: list[datetime],
    point_time: datetime,
    previous_point_time: datetime | None,
) -> bool:
    return any(
        event_time <= point_time
        and (
            previous_point_time < event_time
            if previous_point_time is not None
            else event_time.date() == point_time.date()
        )
        for event_time in event_times
    )


def _days_since_event(event_times: list[datetime], point_time: datetime) -> float | None:
    latest_event_time = next((event_time for event_time in reversed(event_times) if event_time <= point_time), None)
    if latest_event_time is None:
        return None

    return round((point_time - latest_event_time).total_seconds() / 86400, 6)


def _nan_if_none(value: object) -> object:
    return "NaN" if value is None else value


def _fill_esp(row: dict[str, object], items: list[object]) -> None:
    row["esp_id"] = _join_field(items, "espId")
    row["esp_start_date"] = _join_field(items, "startDate")
    row["esp_end_date"] = _join_field(items, "endDate")
    row["esp_failure_date"] = _join_field(items, "failureDate")
    row["esp_lift_reason"] = _join_field(items, "liftReason")
    row["esp_size"] = _join_field(items, "espSize")
    row["esp_nominal_rate"] = _join_field(items, "nominalRate")
    row["esp_nominal_head"] = _join_field(items, "nominalHead")
    row["esp_gas_separator_type"] = _join_field(items, "gasSeparatorType")
    row["esp_motor_power_kw"] = _join_field(items, "motorPowerKw")
    row["esp_is_fountain"] = _join_field(items, "isFountain")


def _fill_vsp(row: dict[str, object], items: list[object]) -> None:
    row["vsp_status"] = _join_field(items, "status")
    row["vsp_start_time"] = _join_field(items, "startDate")
    row["vsp_end_time"] = _join_field(items, "endDate")
    row["vsp_well_state"] = _join_field(items, "wellState")
    row["vsp_well_state_code"] = _join_field(items, "wellStateCode")


def _fill_annotation_targets(row: dict[str, object], annotations: list[SavedAnnotation]) -> None:
    targets: dict[str, tuple[datetime, str]] = {}

    for annotation in annotations:
        start_time = _parse_datetime(annotation.startDate) or datetime.min
        classification = annotation.classification
        for key, value in classification.items():
            if value is None:
                continue

            target = CLASSIFICATION_TO_TARGET.get(f"{key}={value}")
            if not target:
                if key == "esp_degradation" and value == "degr_yes":
                    target = ("target_esp_degradation", "1")
                elif key == "productivity_trend" and value == "Kprod_growth":
                    target = ("target_kprod_trend", "rising")
                elif key == "water_cut_trend" and value == "WCT_decline":
                    target = ("target_wct_trend", "falling")

            if not target:
                continue

            target_column, target_value = target
            previous_target = targets.get(target_column)
            if previous_target is None or start_time >= previous_target[0]:
                targets[target_column] = (start_time, target_value)

    for column in TARGET_COLUMNS:
        row[column] = targets.get(column, (datetime.min, ""))[1]


def _fill_auto_episodes(row: dict[str, object], intervals: list[object]) -> None:
    row["auto_episode_ids"] = _join_field(intervals, "id")
    row["auto_episode_labels"] = _join_field(intervals, "label")
    row["auto_episode_start_dates"] = _join_field(intervals, "startDate")
    row["auto_episode_end_dates"] = _join_field(intervals, "endDate")
    row["auto_episode_confidences"] = _join_field(intervals, "confidence")


def _normalize_auto_label(value: object) -> str:
    return str(value or "").strip().casefold().replace("ё", "е")


def _fill_auto_episode_targets(row: dict[str, object], intervals: list[object]) -> None:
    targets: dict[str, tuple[datetime, str]] = {}

    for interval in intervals:
        target = AUTO_LABEL_TO_TARGET.get(_normalize_auto_label(_get_value(interval, "label")))
        if not target:
            continue

        start_time = _parse_datetime(_get_value(interval, "startDate")) or datetime.min
        target_column, target_value = target
        previous_target = targets.get(target_column)
        if previous_target is None or start_time >= previous_target[0]:
            targets[target_column] = (start_time, target_value)

    for column in AUTO_TARGET_COLUMNS:
        row[column] = targets.get(column, (datetime.min, ""))[1]


def _fill_auto_episode_reviews(row: dict[str, object], reviews: list[object]) -> None:
    row["auto_episode_review_ids"] = _join_field(reviews, "id")
    row["auto_episode_error_types"] = _join_field(reviews, "errorType")
    row["auto_episode_error_comments"] = _join_field(reviews, "comment")


def _is_manual_annotation(annotation: SavedAnnotation) -> bool:
    return not any(annotation.id.startswith(prefix) for prefix in AUTO_ANNOTATION_ID_PREFIXES)


def _fill_frequency(
    row: dict[str, object],
    point_time: datetime,
    breakpoints_by_time: dict[datetime, dict[str, object]],
    segment: dict[str, object] | None,
) -> None:
    if segment:
        row["frequency_segment_id"] = segment.get("id")
        row["frequency_segment_start_date"] = segment.get("startDate")
        row["frequency_segment_end_date"] = segment.get("endDate")

    breakpoint = breakpoints_by_time.get(point_time)
    if breakpoint:
        row["frequency_breakpoint_id"] = breakpoint.get("id")
        row["frequency_breakpoint_source"] = breakpoint.get("source")
        row["frequency_breakpoint_reason"] = breakpoint.get("reason")
        row["frequency_breakpoint_from"] = breakpoint.get("fromFrequency")
        row["frequency_breakpoint_to"] = breakpoint.get("toFrequency")


def _fill_gtm(row: dict[str, object], items: list[object]) -> None:
    row["gtm_ids"] = _join_field(items, "id")
    row["gtm_names"] = _join_field(items, "operationType")
    row["gtm_start_date"] = _join_field(items, "startDate")
    row["gtm_end_date"] = _join_field(items, "endDate")
    row["gtm_direction"] = _join_field(items, "direction")
    row["gtm_duration_days"] = _join_field(items, "durationDays")
    row["gtm_oil_before"] = _join_field(items, "oilBefore")
    row["gtm_liquid_before"] = _join_field(items, "liquidBefore")
    row["gtm_water_cut_before"] = _join_field(items, "waterCutBefore")
    row["gtm_oil_after"] = _join_field(items, "oilAfter")
    row["gtm_liquid_after"] = _join_field(items, "liquidAfter")
    row["gtm_water_cut_after"] = _join_field(items, "waterCutAfter")
    row["gtm_comment"] = _join_field(items, "comment")


def _fill_opz(row: dict[str, object], items: list[object]) -> None:
    row["opz_ids"] = _join_field(items, "id")
    row["opz_types"] = _join_field(items, "operationType")
    row["opz_category"] = _join_field(items, "category")
    row["opz_composition"] = _join_field(items, "composition")
    row["opz_volume"] = _join_field(items, "volume")
    row["opz_capex_opex"] = _join_field(items, "capexOpex")
    row["opz_result"] = _join_field(items, "result")
    row["opz_delta_oil"] = _join_field(items, "deltaOil")
    row["opz_comment"] = _join_field(items, "comment")


def _fill_gdi(row: dict[str, object], items: list[object]) -> None:
    row["gdi_ids"] = _join_field(items, "id")
    row["gdi_types"] = _join_field(items, "operationType")
    row["gdi_start_date"] = _join_field(items, "startDate")
    row["gdi_end_date"] = _join_field(items, "endDate")
    row["gdi_accepted_vdp_pressure"] = _join_field(items, "acceptedVdpPressure")
    row["gdi_productivity_vogel"] = _join_field(items, "productivityVogel")
    row["gdi_quality"] = _join_field(items, "quality")
    row["gdi_executor"] = _join_field(items, "executor")
    row["gdi_duration_hours"] = _join_field(items, "durationHours")
    row["gdi_comment"] = _join_field(items, "comment")


def _build_export_rows_for_well(
    well_id: str,
    annotations: list[SavedAnnotation],
    auto_episode_reviews: list[AutoEpisodeReview],
    manual_breakpoints: list[FrequencyBreakpoint],
    suppressed_breakpoints: list[FrequencyBreakpointSuppression],
    *,
    include_auto_episodes: bool = True,
):
    telemetry_rows = sorted(
        get_well_timeseries(well_id=well_id),
        key=lambda item: _parse_datetime(item.get("date")) or datetime.max,
    )
    if not telemetry_rows:
        return

    tr_rows = sorted(get_well_tr_monitoring(well_id=well_id), key=lambda item: _date_key(item.get("date")))
    esp_periods = get_well_artificial_lift_periods(well_id)
    vsp_periods = get_well_vsp_periods(well_id)
    auto_episode_intervals = get_well_candidate_auto_episode_intervals(well_id) if include_auto_episodes else []
    context = get_well_context(well_id)
    well_annotations = [annotation for annotation in annotations if annotation.wellId == well_id]
    well_auto_episode_reviews = [review for review in auto_episode_reviews if review.wellId == well_id]
    tr_cursor = _StepwiseDateCursor(tr_rows)
    esp_cursor = _DatetimeIntervalCursor(_prepare_datetime_intervals(esp_periods))
    vsp_cursor = _DatetimeIntervalCursor(_prepare_datetime_intervals(vsp_periods))
    annotation_cursor = _DatetimeIntervalCursor(_prepare_datetime_intervals(well_annotations))
    auto_episode_cursor = _DatetimeIntervalCursor(_prepare_datetime_intervals(auto_episode_intervals))
    auto_episode_review_cursor = _DatetimeIntervalCursor(_prepare_datetime_intervals(well_auto_episode_reviews))
    breakpoints = _merge_frequency_breakpoints(
        _build_auto_frequency_breakpoints(telemetry_rows, well_id),
        manual_breakpoints,
        suppressed_breakpoints,
        well_id,
    )
    breakpoints_by_time = {
        parsed_time: breakpoint
        for breakpoint in breakpoints
        if (parsed_time := _parse_datetime(breakpoint.get("date"))) is not None
    }
    frequency_segments = _build_frequency_segments(telemetry_rows, well_id, breakpoints)
    frequency_segment_cursor = _DatetimeIntervalCursor(_prepare_datetime_intervals(frequency_segments))
    gtm_items = list(context.gtm)
    opz_items = list(context.opz)
    gdi_items = list(context.gdi)
    gtm_by_date = _events_by_date(gtm_items, "startDate")
    opz_by_date = _events_by_date(opz_items, "date")
    gdi_by_date = _events_by_date(gdi_items, "endDate")
    gtm_event_times = _event_datetimes(gtm_items, "startDate")
    opz_event_times = _event_datetimes(opz_items, "date")
    gdi_event_times = _event_datetimes(gdi_items, "endDate")
    gtm_event_cursor = _EventTimeCursor(gtm_event_times)
    opz_event_cursor = _EventTimeCursor(opz_event_times)
    gdi_event_cursor = _EventTimeCursor(gdi_event_times)
    previous_point_time: datetime | None = None

    for telemetry in telemetry_rows:
        point_date = _date_key(telemetry.get("date"))
        parsed_point_date = _parse_date(point_date)
        if parsed_point_date is None:
            continue

        point_time = _parse_datetime(telemetry.get("date")) or datetime.combine(parsed_point_date, datetime.min.time())
        row: dict[str, object] = {
            "well_id": well_id,
            "field_code": _well_field_code(well_id),
            "telemetry_time": point_time,
            "seconds_since_prev": "NaN"
            if previous_point_time is None
            else round((point_time - previous_point_time).total_seconds(), 6),
            "telemetry_date": point_date,
        }

        for column in TELEMETRY_COLUMNS:
            row[f"telemetry_{column}"] = telemetry.get(column)

        active_tr_row = tr_cursor.active_at(parsed_point_date)
        if active_tr_row:
            for column in TR_COLUMNS:
                row[f"tr_{column}"] = active_tr_row.get(column)
            row["tr_source_date"] = _date_key(active_tr_row.get("date"))

        active_frequency_segments = frequency_segment_cursor.active_at(point_time)
        gtm_event_triggered = gtm_event_cursor.advance(point_time, previous_point_time)
        opz_event_triggered = opz_event_cursor.advance(point_time, previous_point_time)
        gdi_event_triggered = gdi_event_cursor.advance(point_time, previous_point_time)

        _fill_esp(row, esp_cursor.active_at(point_time))
        _fill_vsp(row, vsp_cursor.active_at(point_time))
        _fill_annotation_targets(row, annotation_cursor.active_at(point_time))
        active_auto_episodes = auto_episode_cursor.active_at(point_time)
        _fill_auto_episodes(row, active_auto_episodes)
        _fill_auto_episode_targets(row, active_auto_episodes)
        _fill_auto_episode_reviews(row, auto_episode_review_cursor.active_at(point_time))
        _fill_frequency(row, point_time, breakpoints_by_time, active_frequency_segments[0] if active_frequency_segments else None)
        _fill_gtm(row, gtm_by_date.get(point_date, []))
        _fill_opz(row, opz_by_date.get(point_date, []))
        _fill_gdi(row, gdi_by_date.get(point_date, []))
        row["event_gtm"] = 1 if gtm_event_triggered else ""
        row["event_opz"] = 1 if opz_event_triggered else ""
        row["event_gdi"] = 1 if gdi_event_triggered else ""
        row["days_since_gtm"] = _nan_if_none(gtm_event_cursor.days_since(point_time))
        row["days_since_opz"] = _nan_if_none(opz_event_cursor.days_since(point_time))
        row["days_since_gdi"] = _nan_if_none(gdi_event_cursor.days_since(point_time))
        yield row
        previous_point_time = point_time


def _normalize_field_codes(field_code: str | None) -> set[str]:
    if not field_code:
        return set()

    return {item.strip() for item in field_code.split(",") if item.strip()}


def _normalize_well_ids(well_id: str | None) -> set[str]:
    if not well_id:
        return set()

    return {item.strip() for item in well_id.split(",") if item.strip()}


def _new_csv_writer() -> tuple[StringIO, csv.DictWriter]:
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=EXPORT_COLUMNS, extrasaction="ignore")
    return output, writer


def _take_csv_chunk(output: StringIO) -> str:
    chunk = output.getvalue()
    output.seek(0)
    output.truncate(0)
    return chunk


def iter_graph_data_export_csv(field_code: str | None = None, well_id: str | None = None):
    markup = load_markup_state()
    field_codes = _normalize_field_codes(field_code)
    requested_well_ids = _normalize_well_ids(well_id)
    output, writer = _new_csv_writer()
    writer.writeheader()
    yield _take_csv_chunk(output)
    rows_in_chunk = 0

    for well_id in sorted(get_available_well_ids()):
        if requested_well_ids and well_id not in requested_well_ids:
            continue

        if field_codes and _well_field_code(well_id) not in field_codes:
            continue

        well_start = time.perf_counter()
        well_rows = 0
        for row in _build_export_rows_for_well(
            well_id=well_id,
            annotations=markup.annotations,
            auto_episode_reviews=markup.autoEpisodeReviews,
            manual_breakpoints=markup.manualFrequencyBreakpoints,
            suppressed_breakpoints=markup.suppressedFrequencyBreakpoints,
        ):
            writer.writerow({column: _format_cell(row.get(column)) for column in EXPORT_COLUMNS})
            rows_in_chunk += 1
            well_rows += 1
            if rows_in_chunk >= CSV_STREAM_CHUNK_ROWS:
                yield _take_csv_chunk(output)
                rows_in_chunk = 0
        logger.info("Exported CSV rows for well %s: %s rows in %.2fs", well_id, well_rows, time.perf_counter() - well_start)

    if output.tell():
        yield _take_csv_chunk(output)


def build_graph_data_export_csv(field_code: str | None = None, well_id: str | None = None) -> str:
    return "".join(iter_graph_data_export_csv(field_code=field_code, well_id=well_id))


def iter_manual_graph_data_export_csv(field_code: str | None = None):
    markup = load_markup_state()
    field_codes = _normalize_field_codes(field_code)
    manual_annotations = [annotation for annotation in markup.annotations if _is_manual_annotation(annotation)]
    manually_marked_well_ids = {annotation.wellId for annotation in manual_annotations}
    output, writer = _new_csv_writer()
    writer.writeheader()
    yield _take_csv_chunk(output)
    rows_in_chunk = 0

    for well_id in sorted(get_available_well_ids()):
        if well_id not in manually_marked_well_ids:
            continue

        if field_codes and _well_field_code(well_id) not in field_codes:
            continue

        well_start = time.perf_counter()
        well_rows = 0
        for row in _build_export_rows_for_well(
            well_id=well_id,
            annotations=manual_annotations,
            auto_episode_reviews=markup.autoEpisodeReviews,
            manual_breakpoints=markup.manualFrequencyBreakpoints,
            suppressed_breakpoints=markup.suppressedFrequencyBreakpoints,
            include_auto_episodes=True,
        ):
            writer.writerow({column: _format_cell(row.get(column)) for column in EXPORT_COLUMNS})
            rows_in_chunk += 1
            well_rows += 1
            if rows_in_chunk >= CSV_STREAM_CHUNK_ROWS:
                yield _take_csv_chunk(output)
                rows_in_chunk = 0
        logger.info("Exported manual CSV rows for well %s: %s rows in %.2fs", well_id, well_rows, time.perf_counter() - well_start)

    if output.tell():
        yield _take_csv_chunk(output)


def build_manual_graph_data_export_csv(field_code: str | None = None) -> str:
    return "".join(iter_manual_graph_data_export_csv(field_code=field_code))
