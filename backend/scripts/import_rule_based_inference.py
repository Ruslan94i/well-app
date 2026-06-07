from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


MARKUP_PATH = Path(__file__).resolve().parents[1] / "data" / "markup.json"
AUTO_ID_PREFIX = "auto-inference-"

LABEL_TO_CLASSIFICATION: dict[str, tuple[str, str, str]] = {
    "Работа": ("well_state", "work", "Работа"),
    "Остановка": ("well_state", "stop", "Остановка"),
    "ГДИ: ГДИ": ("gdi", "gdi", "ГДИ"),
    "Режим работы ЭЦН: УВЧ": ("esp_uvch", "uvch", "УВЧ"),
    "РПТЧ: РПТЧ": ("esp_rptch", "rptch", "РПТЧ"),
    "Периодическая работа: Периодическая работа": (
        "esp_periodic",
        "periodic_operation",
        "Периодическая работа",
    ),
    "НУР: Да": ("nur", "nur_yes", "НУР"),
    "НУР: НУР": ("nur", "nur_yes", "НУР"),
    "Рпл: Рост Рпл": ("reservoir_pressure_trend", "Pres_growth", "Рост Рпл"),
    "Рпл: Снижение Рпл": ("reservoir_pressure_trend", "Pres_decline", "Снижение Рпл"),
    "Обводненность: Рост обводненности": ("water_cut_trend", "WCT_growth", "Рост обводненности"),
    "Обводненность: Снижение обводненности": ("water_cut_trend", "WCT_decline", "Снижение обводненности"),
    "Кпрод: Рост Кпрод": ("productivity_trend", "Kprod_growth", "Рост Кпрод"),
    "Кпрод: Снижение Кпрод": ("productivity_trend", "Kprod_decline", "Снижение Кпрод"),
    "Деградация ЭЦН: Есть": ("esp_degradation", "degr_yes", "Деградация ЭЦН"),
    "Осложненный фонд: Осложненный фонд": ("complicated_fund", "slozhn_fond", "Осложненный фонд"),
    "СППВ: СППВ": ("sppv", "sppv", "СППВ"),
}
MULTILABEL_COLUMNS = [
    "Работа",
    "Остановка",
    "ГДИ",
    "УВЧ",
    "РПТЧ",
    "НУР",
    "Периодическая работа",
    "Снижение Рпл",
    "Рост Рпл",
    "Рост обводненности",
    "Снижение обводненности",
    "Снижение Кпрод",
    "Рост Кпрод",
    "Осложненный фонд",
    "СППВ",
    "Деградация ЭЦН",
]
MULTILABEL_TO_LABEL = {
    "Работа": "Работа",
    "Остановка": "Остановка",
    "ГДИ": "ГДИ: ГДИ",
    "УВЧ": "Режим работы ЭЦН: УВЧ",
    "РПТЧ": "РПТЧ: РПТЧ",
    "НУР": "НУР: НУР",
    "Периодическая работа": "Периодическая работа: Периодическая работа",
    "Снижение Рпл": "Рпл: Снижение Рпл",
    "Рост Рпл": "Рпл: Рост Рпл",
    "Рост обводненности": "Обводненность: Рост обводненности",
    "Снижение обводненности": "Обводненность: Снижение обводненности",
    "Снижение Кпрод": "Кпрод: Снижение Кпрод",
    "Рост Кпрод": "Кпрод: Рост Кпрод",
    "Осложненный фонд": "Осложненный фонд: Осложненный фонд",
    "СППВ": "СППВ: СППВ",
    "Деградация ЭЦН": "Деградация ЭЦН: Есть",
}

CLASSIFICATION_KEYS = [
    "well_state",
    "gdi",
    "esp_uvch",
    "esp_rptch",
    "esp_periodic",
    "nur",
    "reservoir_pressure_trend",
    "water_cut_trend",
    "productivity_trend",
    "complicated_fund",
    "sppv",
    "esp_degradation",
    "esp_mode",
]


def parse_time(value: str) -> datetime:
    value = value.strip()
    if "T" in value:
        return datetime.fromisoformat(value)
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")


def format_time(value: datetime) -> str:
    return value.isoformat(timespec="seconds")


def slugify(value: str) -> str:
    return "".join(char.lower() if char.isalnum() else "-" for char in value).strip("-")


def get_field_group_id(well_id: str) -> str:
    field_code = well_id.split("_", 1)[0].strip().lower()
    return f"field-{field_code or 'other'}"


def build_classification(key: str, value: str) -> dict[str, str | None]:
    result: dict[str, str | None] = {item: None for item in CLASSIFICATION_KEYS}
    result[key] = value
    return result


def duration_days(start: datetime, end: datetime) -> float:
    seconds = max(0.0, (end - start).total_seconds())
    return round(seconds / 86400, 3)


def is_truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "да", "y"}


def load_rows(csv_path: Path) -> tuple[list[dict[str, Any]], Counter[str]]:
    rows: list[dict[str, Any]] = []
    label_counts: Counter[str] = Counter()

    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = set(reader.fieldnames or [])
        required = {"well_id", "telemetry_time"}
        missing = required.difference(reader.fieldnames or [])
        if missing:
            raise ValueError(f"CSV is missing columns: {', '.join(sorted(missing))}")

        has_pred_label = "pred_label" in fieldnames
        active_multilabel_columns = [column for column in MULTILABEL_COLUMNS if column in fieldnames]
        if not has_pred_label and not active_multilabel_columns:
            raise ValueError("CSV has neither pred_label nor supported multilabel columns")

        for row in reader:
            well_id = (row.get("well_id") or "").strip()
            time_value = (row.get("telemetry_time") or "").strip()
            if not well_id or not time_value:
                continue

            labels: list[str] = []
            if has_pred_label:
                label = (row.get("pred_label") or row.get("target_label") or "").strip()
                if label:
                    labels.append(label)
            else:
                labels = [
                    MULTILABEL_TO_LABEL[column]
                    for column in active_multilabel_columns
                    if is_truthy(row.get(column))
                ]

            parsed_time = parse_time(time_value)
            recognized_labels: list[str] = []
            for label in labels:
                label_counts[label] += 1
                if label in LABEL_TO_CLASSIFICATION:
                    recognized_labels.append(label)

            if not recognized_labels:
                if not labels:
                    label_counts[""] += 1
                rows.append({"well_id": well_id, "time": parsed_time, "labels": []})
                continue

            rows.append(
                {
                    "well_id": well_id,
                    "time": parsed_time,
                    "labels": recognized_labels,
                }
            )

    return rows, label_counts


def build_intervals(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_well: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_well[row["well_id"]].append(row)

    intervals: list[dict[str, Any]] = []
    for well_id, well_rows in by_well.items():
        well_rows.sort(key=lambda item: item["time"])
        active_intervals: dict[tuple[str, str], dict[str, Any]] = {}

        for row in well_rows:
            active_identities: set[tuple[str, str]] = set()
            label_by_identity: dict[tuple[str, str], tuple[str, str, str]] = {}

            for label in row.get("labels", []):
                key, value, event_type = LABEL_TO_CLASSIFICATION[label]
                identity = (key, value)
                active_identities.add(identity)
                label_by_identity[identity] = (key, value, event_type)

                if identity in active_intervals:
                    active_intervals[identity]["end"] = row["time"]
                    active_intervals[identity]["rows"] += 1
                    continue

                active_intervals[identity] = {
                    "well_id": well_id,
                    "identity": identity,
                    "classification_key": key,
                    "classification_value": value,
                    "event_type": event_type,
                    "start": row["time"],
                    "end": row["time"],
                    "rows": 1,
                }

            for identity in list(active_intervals):
                if identity not in active_identities:
                    intervals.append(active_intervals.pop(identity))

        intervals.extend(active_intervals.values())

    return intervals


def interval_to_annotation(interval: dict[str, Any], source_name: str) -> dict[str, Any]:
    well_id = interval["well_id"]
    start = interval["start"]
    end = interval["end"]
    key = interval["classification_key"]
    value = interval["classification_value"]
    stable_id = "-".join(
        [
            AUTO_ID_PREFIX.rstrip("-"),
            slugify(well_id),
            start.strftime("%Y%m%d%H%M%S"),
            end.strftime("%Y%m%d%H%M%S"),
            slugify(key),
            slugify(value),
        ]
    )

    return {
        "id": stable_id,
        "wellId": well_id,
        "wellGroupId": get_field_group_id(well_id),
        "startDate": format_time(start),
        "endDate": format_time(end),
        "durationDays": duration_days(start, end),
        "comment": f"Авторазметка по инференсу {source_name}; rows={interval['rows']}",
        "actions": [],
        "annotationKind": "event",
        "eventType": interval["event_type"],
        "classification": build_classification(key, value),
        "confidenceEvent": "medium",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv_path", type=Path)
    args = parser.parse_args()

    rows, label_counts = load_rows(args.csv_path)
    intervals = build_intervals(rows)
    annotations = [interval_to_annotation(interval, args.csv_path.name) for interval in intervals]

    markup = json.loads(MARKUP_PATH.read_text(encoding="utf-8"))
    previous_annotations = markup.get("annotations", [])
    kept_annotations = [
        annotation
        for annotation in previous_annotations
        if not str(annotation.get("id", "")).startswith(AUTO_ID_PREFIX)
    ]
    markup["annotations"] = annotations + kept_annotations
    MARKUP_PATH.write_text(json.dumps(markup, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"source_rows={sum(label_counts.values())}")
    print(f"recognized_rows={len(rows)}")
    print(f"new_auto_inference_annotations={len(annotations)}")
    print(f"kept_annotations={len(kept_annotations)}")
    print(f"total_annotations={len(markup['annotations'])}")
    print("labels:")
    for label, count in label_counts.most_common():
        print(f"  {label or '<empty>'}: {count}")


if __name__ == "__main__":
    main()
