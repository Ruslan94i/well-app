from __future__ import annotations

import csv
import logging
import shutil
from bisect import bisect_left
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from threading import Lock
from typing import Literal

import numpy as np
import polars as pl

from app.core.config import settings
from app.services.csv_timeseries import clear_timeseries_cache


logger = logging.getLogger(__name__)

COLS = [
    "Скважина",
    "well_id",
    "Дата",
    "Дебит жидкости",
    "Давление буферное",
    "Давление затрубное",
    "Загрузка",
    "Обводненность",
    "Р на приеме насоса",
    "Частота вращения двиг.",
    "Активная мощность",
    "БДПВ Объем в пересчете на сутки",
    "БДПВ Расход воды",
    "Давление в коллекторе",
    "Полная мощность",
    "Расход газа на сутки",
    "Расход нефти",
]
REGULAR_TELEMETRY_COLS = [
    "Давление буферное",
    "Давление затрубное",
    "Загрузка",
    "Р на приеме насоса",
    "Частота вращения двиг.",
    "Давление в коллекторе",
]
POWER_COLS = ["Активная мощность", "Полная мощность"]
TELEMETRY_AVG_COLS = REGULAR_TELEMETRY_COLS + POWER_COLS
TRIGGER_COLS = ["Дебит жидкости", "Расход газа на сутки", "Расход нефти"]
MEASUREMENT_COLS = [
    "Скважина",
    "well_id",
    "Дата",
    "Дебит жидкости",
    "Обводненность",
    "БДПВ Объем в пересчете на сутки",
    "БДПВ Расход воды",
    "Расход газа на сутки",
    "Расход нефти",
]
TELEMETRY_OUTPUT_COLS = ["Скважина", "well_id", "Дата", *TELEMETRY_AVG_COLS]
POWER_DAILY_COLS = ["Скважина", "well_id", "Дата", *POWER_COLS]
DAILY_AVG_COLS = ["Скважина", "well_id", "Дата", *COLS[3:]]
EVENT_COLS = [
    "Скважина",
    "well_id",
    "дата_начала",
    "дата_конца",
    "длительность_мин",
    "тип_события",
    "параметр",
    "среднее_значение",
    "макс_отклонение_%",
    "порог_%",
]
AGGREGATE_FILE_NAMES = {
    "measurements.csv",
    "telemetry.csv",
    "telemetry_5.csv",
    "telemetry_10.csv",
    "power_daily.csv",
    "daily_avg.csv",
    "events.csv",
}
OUTPUT_COLUMNS = {
    "measurements.csv": MEASUREMENT_COLS,
    "telemetry.csv": TELEMETRY_OUTPUT_COLS,
    "power_daily.csv": POWER_DAILY_COLS,
    "daily_avg.csv": DAILY_AVG_COLS,
    "events.csv": EVENT_COLS,
}
MIN_ABS = {
    "Давление буферное": 1.0,
    "Давление затрубное": 1.0,
    "Загрузка": 5.0,
    "Р на приеме насоса": 5.0,
    "Частота вращения двиг.": 1.0,
    "Давление в коллекторе": 0.5,
    "Активная мощность": 10.0,
    "Полная мощность": 10.0,
}
FREQ_COL = "Частота вращения двиг."
ROLLING_WINDOW = timedelta(hours=1)
MIN_PERIODS_ROLL = 5
SEG_MIN_GAP = timedelta(minutes=15)
EVENT_GAP = timedelta(minutes=30)
MIN_DURATION = timedelta(minutes=5)

AggregationState = Literal["idle", "running", "done", "error"]


@dataclass
class AggregationStatus:
    status: AggregationState = "idle"
    wells_done: int = 0
    wells_total: int = 0
    message: str | None = None


_status = AggregationStatus()
_status_lock = Lock()


def get_aggregation_status() -> AggregationStatus:
    """Return the latest in-memory aggregation status."""
    with _status_lock:
        return AggregationStatus(
            status=_status.status,
            wells_done=_status.wells_done,
            wells_total=_status.wells_total,
            message=_status.message,
        )


def _set_status(
    status: AggregationState,
    wells_done: int | None = None,
    wells_total: int | None = None,
    message: str | None = None,
) -> None:
    with _status_lock:
        _status.status = status
        if wells_done is not None:
            _status.wells_done = wells_done
        if wells_total is not None:
            _status.wells_total = wells_total
        _status.message = message


def _validate_thresholds(frequency_threshold: int, telemetry_threshold: int) -> None:
    if frequency_threshold not in {5, 10}:
        raise ValueError("frequency_threshold must be 5 or 10")
    if telemetry_threshold not in {5, 10}:
        raise ValueError("telemetry_threshold must be 5 or 10")


def _normalize_numeric(column: str) -> pl.Expr:
    return (
        pl.col(column)
        .cast(pl.Utf8, strict=False)
        .str.replace_all(" ", "")
        .str.replace(",", ".")
        .cast(pl.Float64, strict=False)
        .alias(column)
    )


def _format_datetime_expr(column: str) -> pl.Expr:
    return pl.col(column).dt.strftime("%Y-%m-%d %H:%M:%S").alias(column)


def _empty_frame(columns: list[str]) -> pl.DataFrame:
    return pl.DataFrame({column: [] for column in columns})


def _read_existing_output(path: Path, columns: list[str]) -> pl.DataFrame:
    if not path.exists():
        return _empty_frame(columns)

    try:
        frame = pl.read_csv(path, separator=";", encoding="utf8-lossy", infer_schema_length=0)
    except Exception:
        logger.exception("Failed to read existing aggregate %s", path)
        return _empty_frame(columns)

    for column in columns:
        if column not in frame.columns:
            frame = frame.with_columns(pl.lit(None).alias(column))
    return frame.select(columns)


def _write_csv_atomic(frame: pl.DataFrame, target_path: Path, temp_dir: Path) -> None:
    temp_path = temp_dir / target_path.name
    temp_path.parent.mkdir(parents=True, exist_ok=True)
    frame.write_csv(temp_path, separator=";", include_bom=True)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(temp_path, target_path)


def _checkpoint_root(frequency_threshold: int, telemetry_threshold: int) -> Path:
    return settings.markup_data_path.parent / "_agg_checkpoints" / f"freq_{frequency_threshold}_tele_{telemetry_threshold}"


def _checkpoint_well_dir(root: Path, well_id: str) -> Path:
    return root / well_id


def _find_checkpoint_dir(root: Path, well_id: str) -> Path:
    well_dir = _checkpoint_well_dir(root, well_id)
    if _is_checkpoint_complete(well_dir):
        return well_dir

    legacy_tmp_dir = root / f"{well_id}.tmp"
    if _is_checkpoint_complete(legacy_tmp_dir):
        return legacy_tmp_dir

    return well_dir


def _is_checkpoint_complete(well_dir: Path) -> bool:
    return (well_dir / "DONE").exists() and all((well_dir / file_name).exists() for file_name in OUTPUT_COLUMNS)


def _write_well_checkpoint(root: Path, well_id: str, outputs: dict[str, pl.DataFrame]) -> None:
    well_dir = _checkpoint_well_dir(root, well_id)
    shutil.rmtree(well_dir, ignore_errors=True)
    well_dir.mkdir(parents=True, exist_ok=True)

    for file_name, frame in outputs.items():
        frame.select(OUTPUT_COLUMNS[file_name]).write_csv(well_dir / file_name, separator=";", include_bom=True)

    (well_dir / "DONE").write_text(datetime.now().isoformat(), encoding="utf-8")


def _load_checkpoint_outputs(root: Path, well_ids: set[str]) -> dict[str, list[pl.DataFrame]]:
    outputs: dict[str, list[pl.DataFrame]] = {}
    for well_id in sorted(well_ids):
        well_dir = _find_checkpoint_dir(root, well_id)
        if not _is_checkpoint_complete(well_dir):
            continue

        for file_name, columns in OUTPUT_COLUMNS.items():
            frame = pl.read_csv(
                well_dir / file_name,
                separator=";",
                encoding="utf8-lossy",
                infer_schema_length=0,
            )
            for column in columns:
                if column not in frame.columns:
                    frame = frame.with_columns(pl.lit(None).alias(column))
            outputs.setdefault(file_name, []).append(frame.select(columns))
    return outputs


def _merge_and_write_output(
    file_name: str,
    new_frame: pl.DataFrame,
    columns: list[str],
    temp_dir: Path,
    affected_wells: set[str],
    replace_existing_wells: bool,
) -> None:
    target_path = settings.aggregated_telemetry_data_path / file_name
    existing = _read_existing_output(target_path, columns)
    for column in columns:
        if column not in new_frame.columns:
            new_frame = new_frame.with_columns(pl.lit(None).alias(column))
    next_frame = new_frame.select(columns)

    if not existing.is_empty():
        if replace_existing_wells and affected_wells and "well_id" in existing.columns:
            existing = existing.filter(~pl.col("well_id").is_in(sorted(affected_wells)))
        next_frame = pl.concat([existing, next_frame], how="vertical_relaxed")

    if "well_id" in next_frame.columns:
        sort_columns = [column for column in ["well_id", "Дата", "дата_начала"] if column in next_frame.columns]
        if sort_columns:
            next_frame = next_frame.sort(sort_columns)

    _write_csv_atomic(next_frame, target_path, temp_dir)


def load_well(path: Path) -> pl.DataFrame:
    """Load one raw well telemetry CSV and normalize dates and numeric columns."""
    frame = pl.read_csv(
        path,
        separator=";",
        encoding="utf8-lossy",
        infer_schema_length=0,
        null_values=[""],
        ignore_errors=True,
        truncate_ragged_lines=True,
    )

    for column in COLS:
        if column not in frame.columns:
            frame = frame.with_columns(pl.lit(None).alias(column))

    frame = frame.select(COLS).with_columns(
        pl.col("Дата")
        .cast(pl.Utf8, strict=False)
        .str.strptime(pl.Datetime, format="%d.%m.%Y %H:%M", strict=False)
        .fill_null(pl.col("Дата").cast(pl.Utf8, strict=False).str.strptime(pl.Datetime, format="%d.%m.%Y %H:%M:%S", strict=False))
        .fill_null(pl.col("Дата").cast(pl.Utf8, strict=False).str.strptime(pl.Datetime, format="%Y-%m-%d %H:%M:%S", strict=False))
        .alias("Дата"),
        *[_normalize_numeric(column) for column in COLS[3:]],
    )
    return (
        frame.drop_nulls("Дата")
        .filter(pl.col("well_id").is_not_null() & (pl.col("well_id").cast(pl.Utf8).str.strip_chars() != ""))
        .unique(subset=["well_id", "Дата"], keep="first")
        .sort("Дата")
    )


def _rolling_delta_masks(
    dates: list[datetime],
    values: list[float | None],
    threshold_pct: int,
    min_abs: float,
) -> tuple[list[bool], list[float | None]]:
    valid_values: list[float | None] = []
    for value in values:
        if value is None or not np.isfinite(value) or abs(value) < min_abs:
            valid_values.append(None)
        else:
            valid_values.append(float(value))

    masks: list[bool] = []
    deltas: list[float | None] = []
    left = 0
    rolling_sum = 0.0
    rolling_count = 0

    for index, current_date in enumerate(dates):
        current_value = valid_values[index]
        while left < index and dates[left] < current_date - ROLLING_WINDOW:
            old_value = valid_values[left]
            if old_value is not None:
                rolling_sum -= old_value
                rolling_count -= 1
            left += 1

        if rolling_count >= MIN_PERIODS_ROLL and current_value is not None:
            rolling_mean = rolling_sum / rolling_count
            if abs(rolling_mean) >= min_abs:
                delta = abs(current_value - rolling_mean) / abs(rolling_mean) * 100
                deltas.append(delta)
                masks.append(delta >= threshold_pct)
            else:
                deltas.append(None)
                masks.append(False)
        else:
            deltas.append(None)
            masks.append(False)

        if current_value is not None:
            rolling_sum += current_value
            rolling_count += 1

    return masks, deltas


def _daily_boundaries(start: datetime, end: datetime) -> list[datetime]:
    first_midnight = datetime.combine(start.date(), datetime.min.time())
    if first_midnight < start:
        first_midnight += timedelta(days=1)

    boundaries = [start]
    current = first_midnight
    while current < end:
        boundaries.append(current)
        current += timedelta(days=1)
    return boundaries


def get_segment_boundaries(df: pl.DataFrame, col_thresholds: dict[str, int]) -> list[datetime]:
    """Build telemetry segment boundaries using daily cuts and rolling deviation starts."""
    if df.is_empty():
        return []

    dates = df.get_column("Дата").to_list()
    boundaries: list[datetime] = _daily_boundaries(dates[0], dates[-1])

    for column, threshold in col_thresholds.items():
        values = df.get_column(column).to_list()
        masks, _ = _rolling_delta_masks(dates, values, threshold, MIN_ABS[column])
        previous = False
        for index, current in enumerate(masks):
            if current and not previous:
                boundaries.append(max(dates[0], dates[index] - ROLLING_WINDOW))
            previous = current

    boundaries = sorted(set(boundaries))
    merged: list[datetime] = []
    for boundary in boundaries:
        if not merged or boundary - merged[-1] >= SEG_MIN_GAP:
            merged.append(boundary)
    return merged


def _mean_values_between(
    dates: list[datetime],
    columns: dict[str, list[float | None]],
    start: datetime,
    end: datetime,
) -> dict[str, float | None]:
    start_index = bisect_left(dates, start)
    end_index = bisect_left(dates, end)
    result: dict[str, float | None] = {}
    for column, values in columns.items():
        segment_values = [value for value in values[start_index:end_index] if value is not None and np.isfinite(value)]
        result[column] = round(float(np.mean(segment_values)), 4) if segment_values else None
    return result


def _build_measurements(df: pl.DataFrame) -> pl.DataFrame:
    daily_bdpv = (
        df.with_columns(pl.col("Дата").dt.date().alias("_day"))
        .group_by(["well_id", "_day"])
        .agg(
            pl.col("БДПВ Объем в пересчете на сутки").mean().alias("БДПВ Объем в пересчете на сутки"),
            pl.col("БДПВ Расход воды").mean().alias("БДПВ Расход воды"),
        )
    )
    trigger_mask = pl.any_horizontal(
        [pl.col(column).is_not_null() & (pl.col(column).abs() > 0) for column in TRIGGER_COLS]
    )
    return (
        df.with_columns(pl.col("Дата").dt.date().alias("_day"))
        .filter(trigger_mask)
        .drop(["БДПВ Объем в пересчете на сутки", "БДПВ Расход воды"])
        .join(daily_bdpv, on=["well_id", "_day"], how="left")
        .select(MEASUREMENT_COLS)
        .with_columns(_format_datetime_expr("Дата"))
    )


def _build_telemetry(df: pl.DataFrame, frequency_threshold: int, telemetry_threshold: int) -> pl.DataFrame:
    thresholds = {column: telemetry_threshold for column in TELEMETRY_AVG_COLS}
    thresholds[FREQ_COL] = frequency_threshold
    boundaries = get_segment_boundaries(df, thresholds)
    if not boundaries:
        return _empty_frame(TELEMETRY_OUTPUT_COLS)

    dates = df.get_column("Дата").to_list()
    column_values = {column: df.get_column(column).to_list() for column in TELEMETRY_AVG_COLS}
    rows: list[dict[str, object]] = []
    well_name = df.get_column("Скважина")[0]
    well_id = df.get_column("well_id")[0]
    interval_ends = [*boundaries[1:], dates[-1] + timedelta(minutes=1)]

    for start, end in zip(boundaries, interval_ends):
        means = _mean_values_between(dates, column_values, start, end)
        rows.append({"Скважина": well_name, "well_id": well_id, "Дата": start, **means})

    return pl.DataFrame(rows, infer_schema_length=None).with_columns(_format_datetime_expr("Дата")).select(TELEMETRY_OUTPUT_COLS)


def _build_daily_average(df: pl.DataFrame) -> pl.DataFrame:
    return (
        df.with_columns(pl.col("Дата").dt.date().alias("Дата"))
        .group_by(["Скважина", "well_id", "Дата"])
        .agg([pl.col(column).mean().round(4).alias(column) for column in COLS[3:]])
        .sort(["well_id", "Дата"])
        .select(DAILY_AVG_COLS)
    )


def _build_power_daily(df: pl.DataFrame) -> pl.DataFrame:
    return (
        df.with_columns(pl.col("Дата").dt.date().alias("Дата"))
        .group_by(["Скважина", "well_id", "Дата"])
        .agg([pl.col(column).mean().round(4).alias(column) for column in POWER_COLS])
        .sort(["well_id", "Дата"])
        .select(POWER_DAILY_COLS)
    )


def _append_period_event(
    rows: list[dict[str, object]],
    well_name: str,
    well_id: str,
    start: datetime,
    end: datetime,
    event_type: str,
    parameter: str,
    values: list[float | None],
    deltas: list[float | None],
    threshold: int | None,
) -> None:
    duration = end - start
    if duration < MIN_DURATION and event_type.startswith("отклонение"):
        return

    valid_values = [value for value in values if value is not None and np.isfinite(value)]
    valid_deltas = [delta for delta in deltas if delta is not None and np.isfinite(delta)]
    rows.append(
        {
            "Скважина": well_name,
            "well_id": well_id,
            "дата_начала": start,
            "дата_конца": end,
            "длительность_мин": round(duration.total_seconds() / 60, 2),
            "тип_события": event_type,
            "параметр": parameter,
            "среднее_значение": round(float(np.mean(valid_values)), 4) if valid_values else None,
            "макс_отклонение_%": round(float(np.max(valid_deltas)), 4) if valid_deltas else None,
            "порог_%": threshold,
        }
    )


def _build_events(df: pl.DataFrame, frequency_threshold: int, telemetry_threshold: int) -> pl.DataFrame:
    if df.is_empty():
        return _empty_frame(EVENT_COLS)

    dates = df.get_column("Дата").to_list()
    frequency_values = df.get_column(FREQ_COL).to_list()
    well_name = df.get_column("Скважина")[0]
    well_id = df.get_column("well_id")[0]
    rows: list[dict[str, object]] = []

    previous_running = bool(frequency_values[0] and frequency_values[0] > 0)
    for index, value in enumerate(frequency_values[1:], start=1):
        running = bool(value and value > 0)
        if running != previous_running:
            event_type = "запуск" if running else "остановка"
            _append_period_event(
                rows,
                well_name,
                well_id,
                dates[index],
                dates[index],
                event_type,
                FREQ_COL,
                [value],
                [],
                None,
            )
        previous_running = running

    pump_running = [bool(value and value > 0) for value in frequency_values]
    thresholds = {column: telemetry_threshold for column in TELEMETRY_AVG_COLS}
    thresholds[FREQ_COL] = frequency_threshold

    for column, threshold in thresholds.items():
        values = df.get_column(column).to_list()
        masks, deltas = _rolling_delta_masks(dates, values, threshold, MIN_ABS[column])
        start_index: int | None = None
        last_index: int | None = None
        for index, is_deviation in enumerate(masks):
            active = is_deviation and pump_running[index]
            if active and start_index is None:
                start_index = index
            elif active and last_index is not None and dates[index] - dates[last_index] > EVENT_GAP:
                _append_period_event(
                    rows,
                    well_name,
                    well_id,
                    dates[start_index],
                    dates[last_index],
                    f"отклонение_{threshold}%",
                    column,
                    values[start_index : last_index + 1],
                    deltas[start_index : last_index + 1],
                    threshold,
                )
                start_index = index
            elif not active and start_index is not None and last_index is not None:
                _append_period_event(
                    rows,
                    well_name,
                    well_id,
                    dates[start_index],
                    dates[last_index],
                    f"отклонение_{threshold}%",
                    column,
                    values[start_index : last_index + 1],
                    deltas[start_index : last_index + 1],
                    threshold,
                )
                start_index = None

            if active:
                last_index = index

        if start_index is not None and last_index is not None:
            _append_period_event(
                rows,
                well_name,
                well_id,
                dates[start_index],
                dates[last_index],
                f"отклонение_{threshold}%",
                column,
                values[start_index : last_index + 1],
                deltas[start_index : last_index + 1],
                threshold,
            )

    if not rows:
        return _empty_frame(EVENT_COLS)

    return (
        pl.DataFrame(rows, infer_schema_length=None)
        .with_columns(_format_datetime_expr("дата_начала"), _format_datetime_expr("дата_конца"))
        .select(EVENT_COLS)
    )


def _aggregate_one_well(path: Path, frequency_threshold: int, telemetry_threshold: int) -> dict[str, pl.DataFrame]:
    df = load_well(path)
    if df.is_empty():
        raise ValueError(f"No valid telemetry rows found in {path}")

    return {
        "measurements.csv": _build_measurements(df),
        "telemetry.csv": _build_telemetry(df, frequency_threshold, telemetry_threshold),
        "power_daily.csv": _build_power_daily(df),
        "daily_avg.csv": _build_daily_average(df),
        "events.csv": _build_events(df, frequency_threshold, telemetry_threshold),
    }


def _read_existing_wells() -> set[str]:
    output_path = settings.aggregated_telemetry_data_path / "telemetry.csv"
    if not output_path.exists():
        return set()

    try:
        frame = pl.read_csv(output_path, separator=";", encoding="utf8-lossy", columns=["well_id"])
    except Exception:
        logger.exception("Failed to read existing wells from %s", output_path)
        return set()

    return set(frame.get_column("well_id").drop_nulls().cast(pl.Utf8).unique().to_list())


def _collect_csv_paths(telemetry_folder: Path, well_ids: set[str] | None = None) -> list[Path]:
    paths = sorted(
        path
        for path in telemetry_folder.glob("*.csv")
        if path.parent.name != "aggregated" and path.name.lower() not in AGGREGATE_FILE_NAMES
    )
    if well_ids is None:
        return paths

    normalized = {well_id.strip() for well_id in well_ids}
    return [path for path in paths if path.stem in normalized]


def run_aggregation(
    telemetry_folder: Path | None = None,
    frequency_threshold: int = 5,
    telemetry_threshold: int = 10,
    well_ids: set[str] | None = None,
    replace_existing_wells: bool = False,
) -> None:
    """Generate aggregated telemetry CSV files from raw per-well telemetry."""
    _validate_thresholds(frequency_threshold, telemetry_threshold)
    source_folder = telemetry_folder or settings.telemetry_data_path
    paths = _collect_csv_paths(source_folder, well_ids)
    existing_wells = set() if replace_existing_wells or well_ids else _read_existing_wells()
    pending_paths = [path for path in paths if path.stem not in existing_wells]
    checkpoint_root = _checkpoint_root(frequency_threshold, telemetry_threshold)

    if replace_existing_wells or well_ids:
        for path in pending_paths:
            shutil.rmtree(_checkpoint_well_dir(checkpoint_root, path.stem), ignore_errors=True)
            shutil.rmtree(checkpoint_root / f"{path.stem}.tmp", ignore_errors=True)

    _set_status("running", wells_done=0, wells_total=len(pending_paths), message=None)
    if not pending_paths:
        _set_status("done", wells_done=0, wells_total=0, message="No wells to aggregate")
        return

    affected_wells: set[str] = set()
    errors: list[str] = []

    for index, path in enumerate(pending_paths, start=1):
        try:
            well_dir = _find_checkpoint_dir(checkpoint_root, path.stem)
            if _is_checkpoint_complete(well_dir):
                logger.info("Reusing telemetry aggregation checkpoint for %s", path.stem)
            else:
                logger.info("Aggregating telemetry for %s", path.stem)
                well_outputs = _aggregate_one_well(path, frequency_threshold, telemetry_threshold)
                _write_well_checkpoint(checkpoint_root, path.stem, well_outputs)
            affected_wells.add(path.stem)
        except Exception as exc:
            logger.exception("Failed to aggregate well telemetry from %s", path)
            errors.append(f"{path.stem}: {exc}")
        finally:
            _set_status("running", wells_done=index, wells_total=len(pending_paths), message=None)

    try:
        temp_dir = settings.markup_data_path.parent / "_tmp_agg"
        shutil.rmtree(temp_dir, ignore_errors=True)
        temp_dir.mkdir(parents=True, exist_ok=True)
        outputs = _load_checkpoint_outputs(checkpoint_root, affected_wells)
        for file_name, frames in outputs.items():
            if not frames:
                continue
            new_frame = pl.concat(frames, how="vertical_relaxed")
            _merge_and_write_output(
                file_name,
                new_frame,
                OUTPUT_COLUMNS[file_name],
                temp_dir,
                affected_wells,
                replace_existing_wells,
            )
    except Exception as exc:
        logger.exception("Failed to write aggregated telemetry files")
        _set_status("error", message=f"Failed to write aggregated telemetry files: {exc}")
        raise
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    clear_timeseries_cache()
    message = "; ".join(errors[:5]) if errors else f"Aggregated {len(affected_wells)} wells"
    _set_status("error" if errors and not affected_wells else "done", message=message)


def _latest_datetime_in_file(path: Path) -> datetime | None:
    try:
        frame = load_well(path)
    except Exception:
        logger.exception("Failed to read existing raw telemetry %s", path)
        return None

    if frame.is_empty():
        return None
    return frame.get_column("Дата").max()


def _append_new_rows(source_path: Path, target_path: Path, last_datetime: datetime | None) -> bool:
    source = load_well(source_path)
    if last_datetime is not None:
        source = source.filter(pl.col("Дата") > pl.lit(last_datetime))

    if source.is_empty():
        return False

    output = source.select(COLS).with_columns(pl.col("Дата").dt.strftime("%d.%m.%Y %H:%M").alias("Дата"))
    target_exists = target_path.exists() and target_path.stat().st_size > 0
    with target_path.open("a", encoding="utf-8-sig", newline="") as target_file:
        writer = csv.writer(target_file, delimiter=";")
        if not target_exists:
            writer.writerow(COLS)
        writer.writerows(output.rows())
    return True


def update_wells(
    source_folder: Path,
    telemetry_folder: Path | None = None,
    frequency_threshold: int = 5,
    telemetry_threshold: int = 10,
) -> None:
    """Append newer raw telemetry rows and regenerate aggregates for affected wells."""
    _validate_thresholds(frequency_threshold, telemetry_threshold)
    target_folder = telemetry_folder or settings.telemetry_data_path
    source_paths = sorted(source_folder.glob("*.csv"))
    _set_status("running", wells_done=0, wells_total=len(source_paths), message=None)

    affected_wells: set[str] = set()
    errors: list[str] = []
    for index, source_path in enumerate(source_paths, start=1):
        well_id = source_path.stem.strip()
        target_path = target_folder / f"{well_id}.csv"
        try:
            if not target_path.exists():
                raise FileNotFoundError(f"Target telemetry file does not exist: {target_path}")

            last_datetime = _latest_datetime_in_file(target_path)
            if _append_new_rows(source_path, target_path, last_datetime):
                affected_wells.add(well_id)
        except Exception as exc:
            logger.exception("Failed to update well %s from %s", well_id, source_path)
            errors.append(f"{well_id}: {exc}")
        finally:
            _set_status("running", wells_done=index, wells_total=len(source_paths), message=None)

    if affected_wells:
        run_aggregation(
            telemetry_folder=target_folder,
            frequency_threshold=frequency_threshold,
            telemetry_threshold=telemetry_threshold,
            well_ids=affected_wells,
            replace_existing_wells=True,
        )
        return

    message = "; ".join(errors[:5]) if errors else "No new rows to append"
    _set_status("error" if errors else "done", wells_done=len(source_paths), wells_total=len(source_paths), message=message)
