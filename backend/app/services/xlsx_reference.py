from __future__ import annotations

import math
import re
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from zipfile import ZipFile

from app.core.config import settings
from app.schemas.context import GdiEvent, GtmEvent, OpzEvent, WellContext


XML_NS = {
    "main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "rel": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "pkgrel": "http://schemas.openxmlformats.org/package/2006/relationships",
}
EXCEL_EPOCH = datetime(1899, 12, 30)


def get_well_context(well_id: str) -> WellContext:
    normalized_well_id = well_id.strip()
    return WellContext(
        wellId=normalized_well_id,
        gtm=_get_gtm_events(normalized_well_id),
        opz=_get_opz_events(normalized_well_id),
        gdi=_get_gdi_events(normalized_well_id),
    )


def _get_reference_path(filename: str) -> Path:
    return settings.reference_data_path / filename


def _read_reference_rows(filename: str, sheet_name: str) -> list[dict[str, object]]:
    path = _get_reference_path(filename)
    if not path.exists():
        return []

    file_stat = path.stat()
    return _read_reference_rows_cached(str(path), sheet_name, file_stat.st_mtime_ns, file_stat.st_size)


@lru_cache(maxsize=12)
def _read_reference_rows_cached(path: str, sheet_name: str, mtime_ns: int, size: int) -> list[dict[str, object]]:
    del mtime_ns, size
    with ZipFile(path) as workbook:
        shared_strings = _read_shared_strings(workbook)
        worksheet_path = _get_worksheet_path(workbook, sheet_name)
        if worksheet_path is None:
            return []

        rows = _read_sheet_rows(workbook, worksheet_path, shared_strings)

    if not rows:
        return []

    headers = [_clean_text(value) for value in rows[0]]
    result: list[dict[str, object]] = []

    for values in rows[1:]:
        row: dict[str, object] = {}
        for index, header in enumerate(headers):
            if not header:
                continue
            row[header] = values[index] if index < len(values) else ""
        if any(_clean_text(value) for value in row.values()):
            result.append(row)

    return result


def _read_shared_strings(workbook: ZipFile) -> list[str]:
    try:
        root = ET.fromstring(workbook.read("xl/sharedStrings.xml"))
    except KeyError:
        return []

    return [
        "".join(text.text or "" for text in item.findall(".//main:t", XML_NS))
        for item in root.findall("main:si", XML_NS)
    ]


def _get_worksheet_path(workbook: ZipFile, sheet_name: str) -> str | None:
    workbook_root = ET.fromstring(workbook.read("xl/workbook.xml"))
    rels_root = ET.fromstring(workbook.read("xl/_rels/workbook.xml.rels"))
    rel_by_id = {
        rel.attrib["Id"]: rel.attrib["Target"]
        for rel in rels_root.findall("pkgrel:Relationship", XML_NS)
    }

    for sheet in workbook_root.findall("main:sheets/main:sheet", XML_NS):
        if sheet.attrib.get("name") != sheet_name:
            continue

        rel_id = sheet.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
        target = rel_by_id.get(rel_id or "")
        if not target:
            return None
        return target if target.startswith("xl/") else f"xl/{target.lstrip('/')}"

    return None


def _read_sheet_rows(workbook: ZipFile, worksheet_path: str, shared_strings: list[str]) -> list[list[object]]:
    worksheet_root = ET.fromstring(workbook.read(worksheet_path))
    rows: list[list[object]] = []

    for row_node in worksheet_root.findall("main:sheetData/main:row", XML_NS):
        values: list[object] = []
        for cell in row_node.findall("main:c", XML_NS):
            cell_index = _cell_column_index(cell.attrib.get("r", ""))
            while len(values) < cell_index:
                values.append("")
            values.append(_cell_value(cell, shared_strings))
        rows.append(values)

    return rows


def _cell_column_index(cell_ref: str) -> int:
    match = re.match(r"([A-Z]+)", cell_ref)
    if not match:
        return 0

    column_index = 0
    for char in match.group(1):
        column_index = column_index * 26 + ord(char) - ord("A") + 1
    return column_index - 1


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


def _parse_int(value: object) -> int | None:
    parsed = _parse_float(value)
    if parsed is None:
        return None
    return int(round(parsed))


def _parse_rounded_float(value: object, digits: int) -> float | None:
    parsed = _parse_float(value)
    if parsed is None:
        return None
    return round(parsed, digits)


def _normalize_header(value: object) -> str:
    return re.sub(r"\s+", " ", _clean_text(value)).casefold()


def _row_value(row: dict[str, object], *column_names: str) -> object:
    for column_name in column_names:
        if column_name in row:
            return row[column_name]

    normalized_names = {_normalize_header(column_name) for column_name in column_names}
    for key, value in row.items():
        if _normalize_header(key) in normalized_names:
            return value

    return ""


def _parse_date(value: object) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

    cleaned = _clean_text(value)
    if not cleaned:
        return None

    numeric = _parse_float(cleaned)
    if numeric is not None and numeric > 20000:
        return (EXCEL_EPOCH + timedelta(days=numeric)).date()

    for date_format in ("%d.%m.%Y", "%Y-%m-%d", "%d.%m.%Y %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(cleaned, date_format).date()
        except ValueError:
            continue

    return None


def _format_date(value: date | None) -> str | None:
    return value.isoformat() if value else None


def _append_text(parts: list[str], label: str, value: object) -> None:
    cleaned = _clean_text(value)
    if cleaned:
        parts.append(f"{label}: {cleaned}")


def _get_gtm_events(well_id: str) -> list[GtmEvent]:
    rows = _read_reference_rows("gtm.xlsx", "База ГТМ")
    events: list[GtmEvent] = []

    for row in rows:
        if _clean_text(row.get("Скважина")) != well_id:
            continue

        start_date = _parse_date(row.get("Дата запуска скважины"))
        if start_date is None:
            continue

        duration_days = _parse_int(row.get("Суммарная длительность"))
        end_date = start_date + timedelta(days=max(0, duration_days or 0))
        operation_type = _clean_text(_row_value(row, "Имя ГТМ")) or _clean_text(row.get("Тип ГТМ для вывода")) or "ГТМ"
        comment = _clean_text(_row_value(row, "Комментарий"))

        events.append(
            GtmEvent(
                id=f"gtm-{well_id}-{start_date.isoformat()}-{len(events) + 1}",
                wellId=well_id,
                startDate=start_date.isoformat(),
                endDate=end_date.isoformat(),
                operationType=operation_type,
                direction=_clean_text(row.get("Направление ГТМ")) or None,
                durationDays=duration_days,
                oilBefore=_parse_float(row.get("Дебит нефти до ГТМ, т/сут")),
                liquidBefore=_parse_float(row.get("Дебит жидкости до ГТМ, м3")),
                waterCutBefore=_parse_float(row.get("Обводненность до ГТМ, %")),
                oilAfter=_parse_float(row.get("Дебит нефти после ГТМ, т/сут")),
                liquidAfter=_parse_float(_row_value(row, "Дебит жидкости после ГТМ, м3")),
                waterCutAfter=_parse_float(row.get("Обводненность после ГТМ, %")),
                comment=comment,
            )
        )

    return sorted(events, key=lambda event: event.startDate)


def _get_opz_events(well_id: str) -> list[OpzEvent]:
    rows = _read_reference_rows("opz.xlsx", "ОПЗ_БАЗА")
    events: list[OpzEvent] = []

    for row in rows:
        if _clean_text(row.get("Скважина")) != well_id:
            continue

        event_date = _parse_date(row.get("Дата ОПЗ"))
        if event_date is None:
            continue

        operation_type = _clean_text(_row_value(row, "Вид ОПЗ")) or "ОПЗ"

        events.append(
            OpzEvent(
                id=f"opz-{well_id}-{event_date.isoformat()}-{len(events) + 1}",
                wellId=well_id,
                date=event_date.isoformat(),
                operationType=operation_type,
                category=_clean_text(_row_value(row, "Категория (БП/КРС)")) or None,
                composition=_clean_text(_row_value(row, "Состав")) or None,
                volume=_parse_float(_row_value(row, "Объем", "Объем, м3", "Объем реагента, м3", "Объем закачки всего, м3")),
                capexOpex=_clean_text(_row_value(row, "Capex/Opex", "CAPEX/OPEX", "Capex/Opex ")) or None,
                result=_clean_text(row.get("Итог")) or None,
                deltaOil=_parse_float(row.get("ΔQн, т/сут")),
                comment=_clean_text(_row_value(row, "Комментарий")),
            )
        )

    return sorted(events, key=lambda event: event.date)


def _get_gdi_events(well_id: str) -> list[GdiEvent]:
    rows = _read_reference_rows("gdi.xlsx", "ГДИС")
    events: list[GdiEvent] = []

    for row in rows:
        if _clean_text(row.get("Скважина")) != well_id:
            continue

        start_date = _parse_date(row.get("Дата начала"))
        end_date = _parse_date(row.get("Дата окончания")) or start_date
        if start_date is None or end_date is None:
            continue

        operation_type = _clean_text(row.get("Вид ГДИ")) or "ГДИ"
        comment_parts: list[str] = []
        _append_text(comment_parts, "Фонд", row.get("Фонд"))
        _append_text(comment_parts, "Пласт", row.get("Пласт"))

        events.append(
            GdiEvent(
                id=f"gdi-{well_id}-{end_date.isoformat()}-{len(events) + 1}",
                wellId=well_id,
                startDate=start_date.isoformat(),
                endDate=end_date.isoformat(),
                operationType=operation_type,
                acceptedVdpPressure=_parse_int(_row_value(row, "Рпл принятое ВДП, кгс/см2")),
                productivityVogel=_parse_rounded_float(
                    _row_value(
                        row,
                        "Кпрод Вогель, , м3/сут/ ат",
                        "Кпрод Вогель,, м3/сут/ ат",
                        "Кпрод Вогель, м3/сут/ ат",
                        "Кпрод Вогель, м3/сут/ат",
                    ),
                    1,
                ),
                quality=_parse_int(_row_value(row, "Кач-во ГДИ", "Качество ГДИ")),
                executor=_clean_text(row.get("Исполнитель")) or None,
                durationHours=_parse_float(row.get("Длит-ть ГДИ, ч")),
                comment="; ".join(comment_parts),
            )
        )

    return sorted(events, key=lambda event: event.startDate)
