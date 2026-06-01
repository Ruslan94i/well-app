from __future__ import annotations

import csv
from datetime import date, datetime, timedelta
from io import StringIO
from typing import Any

from app.schemas.markup import FrequencyBreakpoint, FrequencyBreakpointSuppression, SavedAnnotation
from app.services.artificial_lift import get_well_artificial_lift_periods
from app.services.auto_episodes import get_well_auto_episode_intervals
from app.services.csv_timeseries import get_available_well_ids, get_well_timeseries
from app.services.json_markup import load_markup_state
from app.services.tr_monitoring import get_well_tr_monitoring
from app.services.vsp import get_well_vsp_periods
from app.services.xlsx_reference import get_well_context


FREQUENCY_CHANGE_THRESHOLD = 0.1
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
    "episode_ids",
    "episode_types",
    "episode_confidences",
    "episode_start_dates",
    "episode_end_dates",
    "episode_actions",
    "episode_comments",
    "auto_episode_ids",
    "auto_episode_labels",
    "auto_episode_start_dates",
    "auto_episode_end_dates",
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
    return f"frequency-{source}-{well_id}-{point_date.replace('-', '')}"


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
            point_date = _date_key(point.get("date"))
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
            "date": _date_key(point.get("date")),
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

    start_date = _date_key(telemetry_rows[0].get("date"))
    end_date = _date_key(telemetry_rows[-1].get("date"))
    boundary_dates = [start_date]
    boundary_dates.extend(
        _format_cell(breakpoint.get("date"))
        for breakpoint in breakpoints
        if start_date < _format_cell(breakpoint.get("date")) <= end_date
    )
    unique_boundary_dates = sorted(set(boundary_dates))
    segments: list[dict[str, object]] = []

    for index, segment_start in enumerate(unique_boundary_dates):
        next_start = unique_boundary_dates[index + 1] if index + 1 < len(unique_boundary_dates) else ""
        if next_start:
            parsed_next = _parse_date(next_start)
            if parsed_next is None:
                continue
            segment_end = (parsed_next - timedelta(days=1)).isoformat()
        else:
            segment_end = end_date

        if segment_end < segment_start:
            continue

        segments.append(
            {
                "id": f"frequency-segment-{well_id}-{segment_start}-{segment_end}",
                "startDate": segment_start,
                "endDate": segment_end,
            }
        )

    return segments


def _prepare_date_intervals(items: list[object]) -> list[tuple[object, str, str]]:
    intervals: list[tuple[object, str, str]] = []
    for item in items:
        start_date = _date_key(_get_value(item, "startDate"))
        end_date = _date_key(_get_value(item, "endDate")) or "9999-12-31"
        if start_date:
            intervals.append((item, start_date, end_date))
    return intervals


def _active_prepared_date_intervals(
    intervals: list[tuple[object, str, str]],
    point_date: str,
) -> list[object]:
    return [item for item, start_date, end_date in intervals if start_date <= point_date <= end_date]


def _prepare_datetime_intervals(items: list[object]) -> list[tuple[object, datetime, datetime]]:
    intervals: list[tuple[object, datetime, datetime]] = []
    for item in items:
        start_time = _parse_datetime(_get_value(item, "startDate"))
        end_time = _parse_datetime(_get_value(item, "endDate"))
        if start_time is not None and end_time is not None:
            intervals.append((item, start_time, end_time))
    return intervals


def _active_prepared_datetime_intervals(
    intervals: list[tuple[object, datetime, datetime]],
    point_time: datetime,
) -> list[object]:
    return [item for item, start_time, end_time in intervals if start_time <= point_time <= end_time]


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


def _fill_annotations(row: dict[str, object], annotations: list[SavedAnnotation]) -> None:
    row["episode_ids"] = _join_field(annotations, "id")
    row["episode_types"] = _join_field(annotations, "eventType")
    row["episode_confidences"] = _join_field(annotations, "confidenceEvent")
    row["episode_start_dates"] = _join_field(annotations, "startDate")
    row["episode_end_dates"] = _join_field(annotations, "endDate")
    row["episode_actions"] = _join_values(["; ".join(annotation.actions) for annotation in annotations])
    row["episode_comments"] = _join_field(annotations, "comment")


def _fill_auto_episodes(row: dict[str, object], intervals: list[object]) -> None:
    row["auto_episode_ids"] = _join_field(intervals, "id")
    row["auto_episode_labels"] = _join_field(intervals, "label")
    row["auto_episode_start_dates"] = _join_field(intervals, "startDate")
    row["auto_episode_end_dates"] = _join_field(intervals, "endDate")


def _fill_frequency(
    row: dict[str, object],
    point_date: str,
    breakpoints_by_date: dict[str, dict[str, object]],
    segments: list[dict[str, object]],
) -> None:
    segment = next(
        (
            item
            for item in segments
            if _format_cell(item.get("startDate")) <= point_date <= _format_cell(item.get("endDate"))
        ),
        None,
    )
    if segment:
        row["frequency_segment_id"] = segment.get("id")
        row["frequency_segment_start_date"] = segment.get("startDate")
        row["frequency_segment_end_date"] = segment.get("endDate")

    breakpoint = breakpoints_by_date.get(point_date)
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
    manual_breakpoints: list[FrequencyBreakpoint],
    suppressed_breakpoints: list[FrequencyBreakpointSuppression],
) -> list[dict[str, object]]:
    telemetry_rows = get_well_timeseries(well_id=well_id)
    if not telemetry_rows:
        return []

    tr_rows = sorted(get_well_tr_monitoring(well_id=well_id), key=lambda item: _date_key(item.get("date")))
    esp_periods = get_well_artificial_lift_periods(well_id)
    vsp_periods = get_well_vsp_periods(well_id)
    auto_episode_intervals = get_well_auto_episode_intervals(well_id)
    context = get_well_context(well_id)
    well_annotations = [annotation for annotation in annotations if annotation.wellId == well_id]
    esp_interval_index = _prepare_date_intervals(esp_periods)
    vsp_interval_index = _prepare_datetime_intervals(vsp_periods)
    annotation_interval_index = _prepare_date_intervals(well_annotations)
    auto_episode_interval_index = _prepare_date_intervals(auto_episode_intervals)
    breakpoints = _merge_frequency_breakpoints(
        _build_auto_frequency_breakpoints(telemetry_rows, well_id),
        manual_breakpoints,
        suppressed_breakpoints,
        well_id,
    )
    breakpoints_by_date = {_format_cell(breakpoint.get("date")): breakpoint for breakpoint in breakpoints}
    frequency_segments = _build_frequency_segments(telemetry_rows, well_id, breakpoints)
    gtm_by_date = _events_by_date(list(context.gtm), "startDate")
    opz_by_date = _events_by_date(list(context.opz), "date")
    gdi_by_date = _events_by_date(list(context.gdi), "endDate")
    rows: list[dict[str, object]] = []

    for telemetry in telemetry_rows:
        point_date = _date_key(telemetry.get("date"))
        parsed_point_date = _parse_date(point_date)
        if parsed_point_date is None:
            continue

        point_time = datetime.combine(parsed_point_date, datetime.min.time())
        row: dict[str, object] = {
            "well_id": well_id,
            "field_code": _well_field_code(well_id),
            "telemetry_time": point_time,
            "telemetry_date": point_date,
        }

        for column in TELEMETRY_COLUMNS:
            row[f"telemetry_{column}"] = telemetry.get(column)

        active_tr_row = _stepwise_tr_row(tr_rows, parsed_point_date)
        if active_tr_row:
            for column in TR_COLUMNS:
                row[f"tr_{column}"] = active_tr_row.get(column)
            row["tr_source_date"] = _date_key(active_tr_row.get("date"))

        _fill_esp(row, _active_prepared_date_intervals(esp_interval_index, point_date))
        _fill_vsp(row, _active_prepared_datetime_intervals(vsp_interval_index, point_time))
        _fill_annotations(row, _active_prepared_date_intervals(annotation_interval_index, point_date))
        _fill_auto_episodes(row, _active_prepared_date_intervals(auto_episode_interval_index, point_date))
        _fill_frequency(row, point_date, breakpoints_by_date, frequency_segments)
        _fill_gtm(row, gtm_by_date.get(point_date, []))
        _fill_opz(row, opz_by_date.get(point_date, []))
        _fill_gdi(row, gdi_by_date.get(point_date, []))
        rows.append(row)

    return rows


def build_graph_data_export_csv() -> str:
    markup = load_markup_state()
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=EXPORT_COLUMNS, extrasaction="ignore")
    writer.writeheader()

    for well_id in get_available_well_ids():
        for row in _build_export_rows_for_well(
            well_id=well_id,
            annotations=markup.annotations,
            manual_breakpoints=markup.manualFrequencyBreakpoints,
            suppressed_breakpoints=markup.suppressedFrequencyBreakpoints,
        ):
            writer.writerow({column: _format_cell(row.get(column)) for column in EXPORT_COLUMNS})

    return output.getvalue()
