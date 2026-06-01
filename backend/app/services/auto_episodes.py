from __future__ import annotations

import csv
import logging
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


def _clean_cell(value: object) -> str:
    return str(value or "").replace("\ufeff", "").replace("\xa0", " ").strip()


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
    for index, raw_row in enumerate(_read_csv_rows(source_path), start=1):
        well_id = _get_cell(raw_row, WELL_ID_COLUMNS)
        start_date = _parse_date(_get_cell(raw_row, START_DATE_COLUMNS))
        end_date = _parse_date(_get_cell(raw_row, END_DATE_COLUMNS))
        label = _get_cell(raw_row, LABEL_COLUMNS) or "Автоэпизод"

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
            }
        )

    rows.sort(key=lambda item: (str(item["normalizedWellId"]), str(item["startDate"]), str(item["endDate"])))
    logger.info("Loaded %s auto episode intervals from %s", len(rows), source_path)
    return rows


def get_well_auto_episode_intervals(well_id: str) -> list[dict[str, object]]:
    normalized_well_id = well_id.strip().casefold()
    return [
        {key: value for key, value in row.items() if key not in {"normalizedWellId", "wellId"}}
        for row in _load_auto_episode_rows()
        if row["normalizedWellId"] == normalized_well_id
    ]
