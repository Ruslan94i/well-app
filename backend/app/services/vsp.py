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


def get_well_vsp_periods(well_id: str) -> list[dict[str, object]]:
    normalized_well_id = well_id.strip().casefold()
    periods: list[dict[str, object]] = []

    for row in _load_vsp_rows():
        row_well_id = _clean_text(row.get(COLUMNS["well_id"]))
        if row_well_id.casefold() != normalized_well_id:
            continue

        start = _combine_datetime(row.get(COLUMNS["change_date"]), row.get(COLUMNS["change_time"]))
        end = _combine_datetime(row.get(COLUMNS["close_date"]), row.get(COLUMNS["close_time"]))
        if start is None:
            continue
        if end is None:
            end = start + timedelta(days=1)
        if end <= start:
            continue

        well_state = _clean_text(row.get(COLUMNS["well_state"]))
        well_state_code = _clean_text(row.get(COLUMNS["well_state_code"]))
        is_work = well_state == WORK_STATE and well_state_code == WORK_STATE_CODE

        periods.append(
            {
                "id": f"vsp-{row_well_id}-{_format_datetime(start)}-{len(periods) + 1}",
                "wellId": row_well_id,
                "startDate": _format_datetime(start),
                "endDate": _format_datetime(end),
                "status": "work" if is_work else "downtime",
                "wellState": well_state,
                "wellStateCode": well_state_code,
            }
        )

    return sorted(periods, key=lambda item: (item["startDate"], item["endDate"]))
