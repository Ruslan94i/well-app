from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from datetime import date, datetime, time, timedelta
from functools import lru_cache
from zipfile import ZipFile

from app.core.config import settings


logger = logging.getLogger(__name__)

VSP_FILE_PATH = settings.intra_shift_downtime_data_path
EXCEL_EPOCH = datetime(1899, 12, 30)
WORK_STATE = "В работе"
WORK_STATE_CODE = "SS0001"
INVALID_WELL_IDS = {"Da_51Da_515", "Da_515Da_515"}
DUPLICATED_WELL_ID_PATTERN = re.compile(r"^([A-Za-z]+_\d+)\1$")
XML_NS = {
    "main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
}

COLUMNS = {
    "well_id": "A",
    "change_date": "D",
    "change_time": "E",
    "well_state": "F",
    "well_state_code": "G",
    "close_date": "J",
    "close_time": "K",
}


def _clean_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).replace("\ufeff", "").replace("\xa0", " ").strip()


def _normalize_well_id(value: object) -> str:
    cleaned = _clean_text(value)
    if cleaned in INVALID_WELL_IDS or DUPLICATED_WELL_ID_PATTERN.match(cleaned):
        return ""
    return cleaned


def _parse_float(value: object) -> float | None:
    cleaned = _clean_text(value)
    if not cleaned:
        return None

    normalized = cleaned.replace(" ", "").replace(",", ".")
    try:
        return float(normalized)
    except ValueError:
        return None


def _parse_date(value: object) -> date | None:
    cleaned = _clean_text(value)
    if not cleaned:
        return None

    numeric = _parse_float(cleaned)
    if numeric is not None and numeric > 20000:
        return (EXCEL_EPOCH + timedelta(days=numeric)).date()

    for date_format in ("%d.%m.%Y", "%Y-%m-%d", "%d.%m.%Y %H:%M:%S"):
        try:
            return datetime.strptime(cleaned, date_format).date()
        except ValueError:
            continue

    return None


def _parse_time(value: object) -> time:
    cleaned = _clean_text(value)
    if not cleaned:
        return time(0, 0)

    numeric = _parse_float(cleaned)
    if numeric is not None and 0 <= numeric < 1:
        seconds = int(round(numeric * 86400)) % 86400
        return (datetime(2000, 1, 1) + timedelta(seconds=seconds)).time().replace(microsecond=0)

    for time_format in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(cleaned, time_format).time()
        except ValueError:
            continue

    return time(0, 0)


def _combine_datetime(date_value: object, time_value: object) -> datetime | None:
    parsed_date = _parse_date(date_value)
    if parsed_date is None:
        return None
    return datetime.combine(parsed_date, _parse_time(time_value))


def _cell_column(cell_ref: str) -> str:
    match = re.match(r"([A-Z]+)", cell_ref)
    return match.group(1) if match else ""


def _cell_value(cell: ET.Element) -> object:
    if cell.attrib.get("t") == "inlineStr":
        return "".join(text.text or "" for text in cell.findall(".//main:t", XML_NS))

    value_node = cell.find("main:v", XML_NS)
    return value_node.text if value_node is not None else ""


def _load_vsp_rows() -> list[dict[str, object]]:
    if not VSP_FILE_PATH.exists():
        logger.warning("VSP file not found at %s", VSP_FILE_PATH)
        return []

    file_stat = VSP_FILE_PATH.stat()
    return _load_vsp_rows_cached(file_stat.st_mtime_ns, file_stat.st_size)


@lru_cache(maxsize=2)
def _load_vsp_rows_cached(file_mtime_ns: int, file_size: int) -> list[dict[str, object]]:
    del file_mtime_ns, file_size
    rows: list[dict[str, object]] = []
    required_columns = set(COLUMNS.values())

    with ZipFile(VSP_FILE_PATH) as workbook:
        worksheet_root = ET.fromstring(workbook.read("xl/worksheets/sheet1.xml"))
        for row_node in worksheet_root.findall("main:sheetData/main:row", XML_NS):
            row_number = int(row_node.attrib.get("r", "0") or "0")
            if row_number <= 1:
                continue

            row: dict[str, object] = {}
            for cell in row_node.findall("main:c", XML_NS):
                column = _cell_column(cell.attrib.get("r", ""))
                if column in required_columns:
                    row[column] = _cell_value(cell)

            if _clean_text(row.get(COLUMNS["well_id"])):
                rows.append(row)

    logger.info("Loaded %s VSP rows from %s", len(rows), VSP_FILE_PATH)
    return rows


def _format_datetime(value: datetime) -> str:
    return value.isoformat(timespec="minutes")


def _build_well_periods(well_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    periods: list[dict[str, object]] = []

    for index, item in enumerate(well_rows):
        start = item["start"]
        explicit_end = item["end"]
        next_start = well_rows[index + 1]["start"] if index + 1 < len(well_rows) else None

        if explicit_end is not None and explicit_end > start:
            end = explicit_end
        elif next_start is not None and next_start > start:
            end = next_start
        else:
            end = start + timedelta(days=1)

        if end <= start:
            continue

        periods.append(
            {
                "id": f"vsp-{item['well_id']}-{_format_datetime(start)}-{len(periods) + 1}",
                "wellId": item["well_id"],
                "startDate": _format_datetime(start),
                "endDate": _format_datetime(end),
                "status": item["status"],
                "wellState": item["well_state"],
                "wellStateCode": item["well_state_code"],
            }
        )

    return sorted(periods, key=lambda item: (item["startDate"], item["endDate"]))


@lru_cache(maxsize=2)
def _load_vsp_period_index(file_mtime_ns: int, file_size: int) -> dict[str, list[dict[str, object]]]:
    del file_mtime_ns, file_size
    well_rows_by_id: dict[str, list[dict[str, object]]] = {}

    for row in _load_vsp_rows():
        row_well_id = _normalize_well_id(row.get(COLUMNS["well_id"]))
        if not row_well_id:
            continue

        start = _combine_datetime(row.get(COLUMNS["change_date"]), row.get(COLUMNS["change_time"]))
        if start is None:
            continue

        end = _combine_datetime(row.get(COLUMNS["close_date"]), row.get(COLUMNS["close_time"]))
        well_state = _clean_text(row.get(COLUMNS["well_state"]))
        well_state_code = _clean_text(row.get(COLUMNS["well_state_code"]))
        is_work = well_state_code == WORK_STATE_CODE or well_state == WORK_STATE

        well_rows_by_id.setdefault(row_well_id.casefold(), []).append(
            {
                "well_id": row_well_id,
                "start": start,
                "end": end,
                "status": "work" if is_work else "downtime",
                "well_state": well_state,
                "well_state_code": well_state_code,
            }
        )

    period_index: dict[str, list[dict[str, object]]] = {}
    for normalized_well_id, well_rows in well_rows_by_id.items():
        well_rows.sort(key=lambda item: (item["start"], item["end"] or datetime.max))
        period_index[normalized_well_id] = _build_well_periods(well_rows)

    logger.info("Built VSP period index for %s wells", len(period_index))
    return period_index


def _get_vsp_period_index() -> dict[str, list[dict[str, object]]]:
    if not VSP_FILE_PATH.exists():
        logger.warning("VSP file not found at %s", VSP_FILE_PATH)
        return {}

    file_stat = VSP_FILE_PATH.stat()
    return _load_vsp_period_index(file_stat.st_mtime_ns, file_stat.st_size)


def get_well_vsp_periods(well_id: str) -> list[dict[str, object]]:
    normalized_well_id = _normalize_well_id(well_id).casefold()
    return list(_get_vsp_period_index().get(normalized_well_id, []))
