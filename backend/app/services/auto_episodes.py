from __future__ import annotations

import csv
import logging
import math
import re
from datetime import date, datetime, timedelta
from functools import lru_cache
from io import StringIO
from pathlib import Path

from app.core.config import settings


logger = logging.getLogger(__name__)

AUTO_EPISODE_FILE_CANDIDATES = [
    settings.auto_episode_segments_data_path,
    settings.reference_data_path / "claude_episode_segments.csv",
    settings.reference_data_path / "claude_auto_episodes.csv",
    settings.reference_data_path / "auto_episodes.csv",
]
AUTO_EPISODE_COLORS = ["#38bdf8", "#f97316", "#22c55e", "#eab308", "#ec4899", "#a855f7", "#14b8a6"]
EXCEL_EPOCH = date(1899, 12, 30)

WELL_ID_COLUMNS = {"wellid", "well", "скважина", "скв", "скважинаid"}
START_DATE_COLUMNS = {
    "startdate",
    "start",
    "datefrom",
    "from",
    "начало",
    "датаначала",
    "началоэпизода",
    "началоинтервала",
}
END_DATE_COLUMNS = {
    "enddate",
    "end",
    "dateto",
    "to",
    "конец",
    "датаокончания",
    "конецэпизода",
    "конецинтервала",
}
LABEL_COLUMNS = {
    "label",
    "episode",
    "episodetype",
    "predepisode",
    "predictedepisode",
    "predlabel",
    "predictedlabel",
    "prediction",
    "class",
    "category",
    "reason",
    "название",
    "эпизод",
    "типэпизода",
    "класс",
    "категория",
    "причина",
}
COLOR_COLUMNS = {"color", "colour", "цвет"}
ID_COLUMNS = {"id", "episodeid", "intervalid", "ид", "идентификатор"}
DATE_COLUMNS = {"date", "дата", "pointdate", "датазамера"}
CONFIDENCE_COLUMNS = {"confidence", "conf", "probability", "score", "уверенность", "вероятность"}


def _clean_cell(value: object) -> str:
    return str(value or "").replace("\ufeff", "").replace("\xa0", " ").strip()


def _repair_mojibake(value: object) -> str:
    cleaned = _clean_cell(value)
    if not cleaned or not any(marker in cleaned for marker in ("Р", "С")):
        return cleaned

    try:
        repaired = cleaned.encode("cp1251").decode("utf-8")
    except UnicodeError:
        return cleaned

    return repaired if repaired else cleaned


def _normalize_key(value: object) -> str:
    cleaned = _clean_cell(value).casefold().replace("ё", "е")
    return re.sub(r"[\s_\-./():,]+", "", cleaned)


def _get_cell(row: dict[str, str], aliases: set[str]) -> str:
    for key, value in row.items():
        if _normalize_key(key) in aliases:
            return _clean_cell(value)
    return ""


def _parse_date(value: object) -> date | None:
    cleaned = _clean_cell(value)
    if not cleaned:
        return None

    numeric_value = cleaned.replace(",", ".")
    try:
        serial_date = float(numeric_value)
    except ValueError:
        serial_date = None

    if serial_date is not None and 20000 <= serial_date <= 80000:
        return EXCEL_EPOCH + timedelta(days=int(serial_date))

    if re.match(r"^\d{4}-\d{2}-\d{2}", cleaned):
        try:
            return datetime.strptime(cleaned[:10], "%Y-%m-%d").date()
        except ValueError:
            return None

    for date_format in (
        "%d.%m.%Y %H:%M:%S",
        "%d.%m.%Y %H:%M",
        "%d.%m.%Y",
        "%d/%m/%Y",
        "%Y/%m/%d",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ):
        try:
            return datetime.strptime(cleaned, date_format).date()
        except ValueError:
            continue

    return None


def _parse_float(value: object) -> float | None:
    cleaned = _clean_cell(value)
    if not cleaned:
        return None

    try:
        parsed = float(cleaned.replace(" ", "").replace(",", "."))
    except ValueError:
        return None

    return parsed if math.isfinite(parsed) else None


def _default_color(label: str) -> str:
    hash_value = sum(ord(char) for char in label or "auto-episode")
    return AUTO_EPISODE_COLORS[hash_value % len(AUTO_EPISODE_COLORS)]


def _read_text(path: Path) -> str:
    content = path.read_bytes()
    for encoding in ("utf-8-sig", "cp1251"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8-sig", errors="replace")


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    text = _read_text(path)
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel

    reader = csv.DictReader(StringIO(text), dialect=dialect)
    return [dict(row) for row in reader]


def _get_source_path() -> Path | None:
    for path in AUTO_EPISODE_FILE_CANDIDATES:
        if path.exists():
            return path
    return None


def _load_auto_episode_rows() -> list[dict[str, object]]:
    source_path = _get_source_path()
    if source_path is None:
        return []

    file_stat = source_path.stat()
    return _load_auto_episode_rows_cached(str(source_path), file_stat.st_mtime_ns, file_stat.st_size)


@lru_cache(maxsize=4)
def _load_auto_episode_rows_cached(path: str, file_mtime_ns: int, file_size: int) -> list[dict[str, object]]:
    del file_mtime_ns, file_size
    source_path = Path(path)
    logger.info("Loading auto episode intervals from %s", source_path)

    rows: list[dict[str, object]] = []
    point_rows: list[dict[str, object]] = []
    for index, raw_row in enumerate(_read_csv_rows(source_path), start=1):
        well_id = _get_cell(raw_row, WELL_ID_COLUMNS)
        start_date = _parse_date(_get_cell(raw_row, START_DATE_COLUMNS))
        end_date = _parse_date(_get_cell(raw_row, END_DATE_COLUMNS))
        point_date = _parse_date(_get_cell(raw_row, DATE_COLUMNS))
        label = _repair_mojibake(_get_cell(raw_row, LABEL_COLUMNS)) or "Автоэпизод"
        confidence = _parse_float(_get_cell(raw_row, CONFIDENCE_COLUMNS))

        if well_id and point_date is not None and start_date is None and end_date is None:
            point_rows.append(
                {
                    "wellId": well_id,
                    "normalizedWellId": well_id.casefold(),
                    "date": point_date,
                    "label": label,
                    "confidence": confidence,
                }
            )
            continue

        if not well_id or start_date is None or end_date is None or end_date < start_date:
            continue

        interval_id = _get_cell(raw_row, ID_COLUMNS) or f"auto-episode-{well_id}-{start_date.isoformat()}-{index}"
        color = _get_cell(raw_row, COLOR_COLUMNS) or _default_color(label)

        rows.append(
            {
                "id": interval_id,
                "wellId": well_id,
                "normalizedWellId": well_id.casefold(),
                "startDate": start_date.isoformat(),
                "endDate": end_date.isoformat(),
                "label": label,
                "color": color,
                "confidence": confidence,
            }
        )

    rows.extend(_build_intervals_from_point_rows(point_rows))
    rows.sort(key=lambda item: (str(item["normalizedWellId"]), str(item["startDate"]), str(item["endDate"])))
    logger.info("Loaded %s auto episode intervals from %s", len(rows), source_path)
    return rows


def _build_intervals_from_point_rows(point_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    intervals: list[dict[str, object]] = []
    current: dict[str, object] | None = None
    interval_index = 0

    for point in sorted(
        point_rows,
        key=lambda item: (str(item["normalizedWellId"]), item["date"] if isinstance(item["date"], date) else date.min),
    ):
        point_date = point["date"]
        label = str(point["label"])
        if not isinstance(point_date, date):
            continue

        should_start_new = True
        if current is not None:
            previous_end = current["endDateValue"]
            should_start_new = not (
                current["normalizedWellId"] == point["normalizedWellId"]
                and current["label"] == label
                and isinstance(previous_end, date)
                and point_date == previous_end + timedelta(days=1)
            )

        if should_start_new:
            if current is not None:
                intervals.append(_finalize_point_interval(current, interval_index))
                interval_index += 1

            confidence = point["confidence"]
            confidence_count = 1 if confidence is not None else 0
            current = {
                "wellId": point["wellId"],
                "normalizedWellId": point["normalizedWellId"],
                "startDateValue": point_date,
                "endDateValue": point_date,
                "label": label,
                "confidenceSum": float(confidence) if confidence is not None else 0.0,
                "confidenceCount": confidence_count,
            }
            continue

        confidence = point["confidence"]
        current["endDateValue"] = point_date
        if confidence is not None:
            current["confidenceSum"] = float(current["confidenceSum"]) + float(confidence)
            current["confidenceCount"] = int(current["confidenceCount"]) + 1

    if current is not None:
        intervals.append(_finalize_point_interval(current, interval_index))

    return intervals


def _finalize_point_interval(interval: dict[str, object], index: int) -> dict[str, object]:
    well_id = str(interval["wellId"])
    start_date = interval["startDateValue"]
    end_date = interval["endDateValue"]
    label = str(interval["label"])
    confidence_count = int(interval["confidenceCount"])
    confidence = (
        round(float(interval["confidenceSum"]) / confidence_count, 3)
        if confidence_count > 0
        else None
    )

    if not isinstance(start_date, date) or not isinstance(end_date, date):
        raise ValueError("Auto episode interval has invalid date bounds")

    return {
        "id": f"auto-episode-{well_id}-{start_date.isoformat()}-{index}",
        "wellId": well_id,
        "normalizedWellId": str(interval["normalizedWellId"]),
        "startDate": start_date.isoformat(),
        "endDate": end_date.isoformat(),
        "label": label,
        "color": _default_color(label),
        "confidence": confidence,
    }


def get_well_auto_episode_intervals(well_id: str) -> list[dict[str, object]]:
    normalized_well_id = well_id.strip().casefold()
    return [
        {key: value for key, value in row.items() if key not in {"normalizedWellId", "wellId"}}
        for row in _load_auto_episode_rows()
        if row["normalizedWellId"] == normalized_well_id
    ]
