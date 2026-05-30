from __future__ import annotations

import logging
import math
import re
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from functools import lru_cache
from zipfile import ZipFile

from app.core.config import settings


logger = logging.getLogger(__name__)

ARTIFICIAL_LIFT_FILE_PATH = settings.artificial_lift_data_path
EXCEL_EPOCH = datetime(1899, 12, 30)
XML_NS = {
    "main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
}

COLUMNS = {
    "well_id": "A",
    "goal": "E",
    "install_date": "H",
    "failure_date": "J",
    "dismantle_date": "K",
    "lift_reason": "N",
    "esp_type": "T",
    "esp_size": "V",
    "nominal_rate": "Y",
    "gas_separator_type": "BL",
    "motor_power_kw": "CR",
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
        parsed = float(normalized)
    except ValueError:
        return None

    return parsed if math.isfinite(parsed) else None


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


def _format_date(value: date | None) -> str | None:
    return value.isoformat() if value else None


def _cell_column(cell_ref: str) -> str:
    match = re.match(r"([A-Z]+)", cell_ref)
    return match.group(1) if match else ""


def _read_shared_strings(workbook: ZipFile) -> list[str]:
    try:
        root = ET.fromstring(workbook.read("xl/sharedStrings.xml"))
    except KeyError:
        return []

    return [
        "".join(text.text or "" for text in item.findall(".//main:t", XML_NS))
        for item in root.findall("main:si", XML_NS)
    ]


def _cell_value(cell: ET.Element, shared_strings: list[str]) -> object:
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        return "".join(text.text or "" for text in cell.findall(".//main:t", XML_NS))

    value_node = cell.find("main:v", XML_NS)
    if value_node is None:
        return ""

    raw_value = value_node.text or ""
    if cell_type == "s":
        try:
            return shared_strings[int(raw_value)]
        except (ValueError, IndexError):
            return raw_value

    return raw_value


def _read_equipment_rows() -> list[dict[str, object]]:
    if not ARTIFICIAL_LIFT_FILE_PATH.exists():
        logger.warning("Artificial lift file not found at %s", ARTIFICIAL_LIFT_FILE_PATH)
        return []

    file_stat = ARTIFICIAL_LIFT_FILE_PATH.stat()
    return _read_equipment_rows_cached(file_stat.st_mtime_ns, file_stat.st_size)


@lru_cache(maxsize=2)
def _read_equipment_rows_cached(file_mtime_ns: int, file_size: int) -> list[dict[str, object]]:
    del file_mtime_ns, file_size
    rows: list[dict[str, object]] = []
    required_columns = set(COLUMNS.values())

    with ZipFile(ARTIFICIAL_LIFT_FILE_PATH) as workbook:
        shared_strings = _read_shared_strings(workbook)
        worksheet_root = ET.fromstring(workbook.read("xl/worksheets/sheet1.xml"))
        for row_node in worksheet_root.findall("main:sheetData/main:row", XML_NS):
            row_number = int(row_node.attrib.get("r", "0") or "0")
            if row_number <= 3:
                continue

            row: dict[str, object] = {}
            for cell in row_node.findall("main:c", XML_NS):
                column = _cell_column(cell.attrib.get("r", ""))
                if column in required_columns:
                    row[column] = _cell_value(cell, shared_strings)

            if _clean_text(row.get(COLUMNS["well_id"])):
                rows.append(row)

    logger.info("Loaded %s artificial lift rows from %s", len(rows), ARTIFICIAL_LIFT_FILE_PATH)
    return rows


def _is_fountain_goal(goal: object) -> bool:
    normalized = _clean_text(goal).casefold()
    return normalized.startswith("фонтан")


def get_well_artificial_lift_periods(well_id: str) -> list[dict[str, object]]:
    normalized_well_id = well_id.strip().casefold()
    periods: list[dict[str, object]] = []

    for row in _read_equipment_rows():
        row_well_id = _clean_text(row.get(COLUMNS["well_id"]))
        if row_well_id.casefold() != normalized_well_id:
            continue

        install_date = _parse_date(row.get(COLUMNS["install_date"]))
        if install_date is None:
            continue

        is_fountain = _is_fountain_goal(row.get(COLUMNS["goal"]))
        esp_id = "Воронка" if is_fountain else _clean_text(row.get(COLUMNS["esp_type"]))
        if not esp_id:
            esp_id = "УЭЦН"

        dismantle_date = _parse_date(row.get(COLUMNS["dismantle_date"]))
        failure_date = _parse_date(row.get(COLUMNS["failure_date"]))

        periods.append(
            {
                "id": f"artificial-lift-{row_well_id}-{install_date.isoformat()}-{len(periods) + 1}",
                "wellId": row_well_id,
                "espId": esp_id,
                "startDate": install_date.isoformat(),
                "endDate": _format_date(dismantle_date),
                "failureDate": _format_date(failure_date),
                "liftReason": _clean_text(row.get(COLUMNS["lift_reason"])) or None,
                "espSize": None if is_fountain else _clean_text(row.get(COLUMNS["esp_size"])) or None,
                "nominalRate": None if is_fountain else _parse_float(row.get(COLUMNS["nominal_rate"])),
                "gasSeparatorType": None if is_fountain else _clean_text(row.get(COLUMNS["gas_separator_type"])) or None,
                "motorPowerKw": None if is_fountain else _parse_float(row.get(COLUMNS["motor_power_kw"])),
                "isFountain": is_fountain,
            }
        )

    return sorted(periods, key=lambda item: item["startDate"])
