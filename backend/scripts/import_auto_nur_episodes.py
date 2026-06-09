from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


MARKUP_PATH = Path(__file__).resolve().parents[1] / "data" / "markup.json"
AUTO_NUR_ID_PREFIX = "auto-nur-"

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
    if not value:
        raise ValueError("empty datetime")
    return datetime.fromisoformat(value.replace(" ", "T"))


def format_time(value: datetime) -> str:
    return value.isoformat(timespec="seconds")


def slugify(value: str) -> str:
    return "".join(char.lower() if char.isalnum() else "-" for char in value).strip("-")


def get_field_group_id(well_id: str) -> str:
    field_code = well_id.split("_", 1)[0].strip().lower()
    return f"field-{field_code or 'other'}"


def duration_days(start: datetime, end: datetime) -> float:
    return round(max(0.0, (end - start).total_seconds()) / 86400, 3)


def parse_float(value: str | None) -> float | None:
    text = (value or "").strip().replace(",", ".")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def build_classification() -> dict[str, str | None]:
    result: dict[str, str | None] = {key: None for key in CLASSIFICATION_KEYS}
    result["nur"] = "nur_yes"
    return result


def build_comment(row: dict[str, str], source_name: str) -> str:
    details = [
        f"Авторазметка НУР из {source_name}",
        f"converged={(row.get('converged') or '').strip()}",
        f"stop_duration_days={(row.get('stop_duration_days') or '').strip()}",
        f"baseline_med_abs_dpdt={(row.get('baseline_med_abs_dpdt') or '').strip()}",
        f"baseline_std_dpdt={(row.get('baseline_std_dpdt') or '').strip()}",
    ]
    return "; ".join(item for item in details if not item.endswith("="))


def row_to_annotation(row: dict[str, str], source_name: str) -> dict[str, Any] | None:
    well_id = (row.get("well_id") or "").strip()
    if not well_id:
        return None

    start = parse_time(row.get("nur_start") or "")
    end = parse_time(row.get("nur_end") or "")
    if end < start:
        return None

    duration = parse_float(row.get("duration_days"))
    if duration is None:
        duration = duration_days(start, end)

    stable_id = "-".join(
        [
            AUTO_NUR_ID_PREFIX.rstrip("-"),
            slugify(well_id),
            start.strftime("%Y%m%d%H%M%S"),
            end.strftime("%Y%m%d%H%M%S"),
        ]
    )

    return {
        "id": stable_id,
        "wellId": well_id,
        "wellGroupId": get_field_group_id(well_id),
        "startDate": format_time(start),
        "endDate": format_time(end),
        "durationDays": round(duration, 3),
        "comment": build_comment(row, source_name),
        "actions": [],
        "annotationKind": "event",
        "eventType": "НУР",
        "classification": build_classification(),
        "confidenceEvent": "medium",
    }


def load_annotations(csv_path: Path) -> tuple[list[dict[str, Any]], Counter[str]]:
    annotations: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()

    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"well_id", "nur_start", "nur_end"}
        missing = required.difference(reader.fieldnames or [])
        if missing:
            raise ValueError(f"CSV is missing columns: {', '.join(sorted(missing))}")

        for row in reader:
            try:
                annotation = row_to_annotation(row, csv_path.name)
            except ValueError:
                counts["skipped_invalid_datetime"] += 1
                continue

            if annotation is None:
                counts["skipped"] += 1
                continue

            annotations.append(annotation)
            counts[annotation["wellId"]] += 1

    return annotations, counts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv_path", type=Path)
    args = parser.parse_args()

    annotations, counts = load_annotations(args.csv_path)

    markup = json.loads(MARKUP_PATH.read_text(encoding="utf-8"))
    previous_annotations = markup.get("annotations", [])
    kept_annotations = [
        annotation
        for annotation in previous_annotations
        if not str(annotation.get("id", "")).startswith(AUTO_NUR_ID_PREFIX)
    ]
    markup["annotations"] = annotations + kept_annotations
    MARKUP_PATH.write_text(json.dumps(markup, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"new_auto_nur_annotations={len(annotations)}")
    print(f"wells={len([key for key in counts if not key.startswith('skipped')])}")
    print(f"kept_annotations={len(kept_annotations)}")
    print(f"total_annotations={len(markup['annotations'])}")
    for well_id, count in counts.most_common(10):
        print(f"  {well_id}: {count}")


if __name__ == "__main__":
    main()
