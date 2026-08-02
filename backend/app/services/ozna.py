from __future__ import annotations

import csv
import json
import logging
import math
import shutil
import tempfile
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from app.core.config import settings


logger = logging.getLogger(__name__)

SOURCE_COLUMNS = {
    "well_code": "Скважина",
    "well_id_src": "well_id",
    "measured_at": "Дата и время измерения",
    "pressure_atm": "Давление, атм",
    "temperature_c": "Температура, °C",
    "qliq_m3d": "Дебит жидкости, м3/сут",
    "qoil_tpd": "Дебит нефти, т/сут",
    "qgas_m3d": "Расход газа, м3/сут",
    "water_cut_pct": "Обводненность, %",
    "gas_factor_m3t": "Газовый фактор, м3/т",
    "source_file": "Исходный файл импорта",
}
RAW_COLUMNS = [
    "well_code",
    "well_id_src",
    "measured_at",
    "pressure_atm",
    "temperature_c",
    "qliq_m3d",
    "qoil_tpd",
    "qoil_m3d",
    "qgas_m3d",
    "water_cut_pct",
    "gas_factor_m3t",
    "rho_used_kg_m3",
    "rho_source",
    "rho_implied_ozna",
    "density_delta_pct",
    "density_quality_flag",
    "source_file",
    "session_id",
]
SESSION_COLUMNS = [
    "session_id",
    "well_code",
    "well_id_src",
    "started_at",
    "ended_at",
    "mid_at",
    "duration_min",
    "n_points",
    "source_files",
    "rho_used_kg_m3",
    "rho_source",
    "rho_implied_ozna",
    "density_delta_pct",
    "quality_flags",
    "qliq_median",
    "qliq_mean",
    "qliq_p10",
    "qliq_p90",
    "qliq_std",
    "qliq_cv_pct",
    "qliq_drift_pct",
    "qliq_n_valid",
    "qoil_tpd_median",
    "qoil_tpd_mean",
    "qoil_tpd_p10",
    "qoil_tpd_p90",
    "qoil_tpd_std",
    "qoil_tpd_cv_pct",
    "qoil_tpd_drift_pct",
    "qoil_tpd_n_valid",
    "qoil_m3d_median",
    "qoil_m3d_mean",
    "qoil_m3d_p10",
    "qoil_m3d_p90",
    "qoil_m3d_std",
    "qoil_m3d_cv_pct",
    "qoil_m3d_drift_pct",
    "qoil_m3d_n_valid",
    "qgas_median",
    "qgas_mean",
    "qgas_p10",
    "qgas_p90",
    "qgas_std",
    "qgas_cv_pct",
    "qgas_drift_pct",
    "qgas_n_valid",
]
PVT_DENSITY_COLUMNS = ["field_prefix", "rho_degassed_kg_m3_at_1.0132bar"]
OZNA_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


@dataclass(frozen=True)
class OznaRecomputeResult:
    raw_rows: int
    session_rows: int
    matched_wells: int
    unmatched_wells: tuple[str, ...]
    quality_counts: dict[str, int]
    raw_path: Path
    sessions_path: Path


def _field_prefix(well_code: object) -> str:
    prefix = str(well_code or "").split("_", 1)[0].strip()
    return "AZ" if prefix == "Az" else prefix


def _normalize_number(value: object) -> float | None:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    text = str(value).replace("\ufeff", "").replace("\xa0", " ").strip()
    if not text or text in {"—", "#ЗНАЧ!", "#ДЕЛ/0!"}:
        return None
    text = text.replace(" ", "").replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def _format_dt(value: object) -> str:
    if pd.isna(value):
        return ""
    return pd.Timestamp(value).strftime(OZNA_DATE_FORMAT)


def _read_density_by_prefix(path: Path) -> dict[str, float]:
    if not path.exists():
        raise FileNotFoundError(f"OZNA PVT density reference not found: {path}")

    densities: dict[str, float] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source, delimiter=";")
        for row in reader:
            prefix = str(row.get("field_prefix") or "").strip()
            value = _normalize_number(row.get("rho_degassed_kg_m3_at_1.0132bar"))
            if prefix and value is not None:
                densities[prefix] = value
    if not densities:
        raise ValueError(f"OZNA PVT density reference has no usable rows: {path}")
    return densities


def _series_stats(values: pd.Series) -> dict[str, float | int | None]:
    clean = pd.to_numeric(values, errors="coerce").dropna()
    n_valid = int(clean.shape[0])
    if n_valid == 0:
        return {
            "median": None,
            "mean": None,
            "p10": None,
            "p90": None,
            "std": None,
            "cv_pct": None,
            "drift_pct": None,
            "n_valid": 0,
        }

    mean = float(clean.mean())
    std = float(clean.std(ddof=0)) if n_valid > 1 else 0.0
    cv_pct = None if abs(mean) < 1e-12 else 100.0 * std / abs(mean)

    third = max(n_valid // 3, 1)
    first = float(clean.iloc[:third].median())
    last = float(clean.iloc[-third:].median())
    drift_pct = None if abs(first) < 1e-12 else 100.0 * (last - first) / abs(first)

    return {
        "median": float(clean.median()),
        "mean": mean,
        "p10": float(clean.quantile(0.10)),
        "p90": float(clean.quantile(0.90)),
        "std": std,
        "cv_pct": cv_pct,
        "drift_pct": drift_pct,
        "n_valid": n_valid,
    }


def _round_or_none(value: object, digits: int = 6) -> float | None:
    if value is None or pd.isna(value):
        return None
    return round(float(value), digits)


def _quality_flags(row: dict[str, object]) -> list[str]:
    flags: list[str] = []
    duration = row.get("duration_min")
    n_points = row.get("n_points")
    qliq_cv = row.get("qliq_cv_pct")
    qliq_drift = row.get("qliq_drift_pct")
    density_delta = row.get("density_delta_pct")

    if isinstance(duration, (int, float)) and duration < settings.ozna_short_session_minutes:
        flags.append("SHORT_SESSION")
    if isinstance(n_points, (int, float)) and n_points < settings.ozna_few_points_min:
        flags.append("FEW_POINTS")
    if isinstance(qliq_cv, (int, float)) and qliq_cv > settings.ozna_unstable_cv_pct:
        flags.append("UNSTABLE")
    if isinstance(qliq_drift, (int, float)) and abs(qliq_drift) > settings.ozna_drifting_pct:
        flags.append("DRIFTING")
    if isinstance(density_delta, (int, float)) and abs(density_delta) > 2.0:
        flags.append("DENSITY_MISMATCH")
    return flags


def _write_csv_atomic(frame: pd.DataFrame, target_path: Path) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8-sig", newline="", suffix=".csv", delete=False, dir=target_path.parent) as tmp:
        tmp_path = Path(tmp.name)
        frame.to_csv(tmp, index=False, sep=";", lineterminator="\n")
    shutil.move(str(tmp_path), target_path)


def _load_reference_wells(path: Path) -> set[str]:
    if not path.exists():
        return set()
    try:
        wells = pd.read_csv(path, usecols=["well_id"], nrows=None, encoding="utf-8-sig")
    except Exception:
        logger.warning("Failed to read reference wells from %s", path, exc_info=True)
        return set()
    return {str(value).strip() for value in wells["well_id"].dropna().unique() if str(value).strip()}


def _prepare_raw_frame(source_path: Path, density_path: Path) -> pd.DataFrame:
    densities = _read_density_by_prefix(density_path)
    source = pd.read_csv(source_path, sep=";", encoding="utf-8-sig", dtype=str)
    missing = [column for column in SOURCE_COLUMNS.values() if column not in source.columns]
    if missing:
        raise ValueError(f"OZNA source is missing columns: {', '.join(missing)}")

    raw = source.rename(columns={source: target for target, source in SOURCE_COLUMNS.items()})[
        list(SOURCE_COLUMNS)
    ].copy()
    raw["well_code"] = raw["well_code"].astype(str).str.strip()
    raw["well_id_src"] = raw["well_id_src"].astype(str).str.strip()
    raw["source_file"] = raw["source_file"].astype(str).str.strip()
    raw["measured_at"] = pd.to_datetime(raw["measured_at"], format=OZNA_DATE_FORMAT, errors="coerce")
    for column in ("pressure_atm", "temperature_c", "qliq_m3d", "qoil_tpd", "qgas_m3d", "water_cut_pct", "gas_factor_m3t"):
        raw[column] = raw[column].map(_normalize_number)

    raw = raw.dropna(subset=["well_code", "measured_at"])
    raw = raw[raw["well_code"].ne("")]
    raw = raw.drop_duplicates(subset=["well_code", "measured_at", "source_file"], keep="first")
    raw = raw.sort_values(["well_code", "measured_at", "source_file"]).reset_index(drop=True)
    raw["field_prefix"] = raw["well_code"].map(_field_prefix)
    raw["rho_used_kg_m3"] = raw["field_prefix"].map(densities)
    raw["rho_source"] = np.where(raw["rho_used_kg_m3"].notna(), "pvt_density_by_prefix", "")
    raw["qoil_m3d"] = np.where(raw["rho_used_kg_m3"].gt(0), raw["qoil_tpd"] / (raw["rho_used_kg_m3"] / 1000.0), np.nan)

    oil_volume_from_qliq = raw["qliq_m3d"] * (1.0 - raw["water_cut_pct"] / 100.0)
    raw["rho_implied_ozna"] = np.where(oil_volume_from_qliq.gt(0), raw["qoil_tpd"] / oil_volume_from_qliq * 1000.0, np.nan)
    raw["density_delta_pct"] = np.where(
        raw["rho_used_kg_m3"].gt(0) & raw["rho_implied_ozna"].notna(),
        100.0 * (raw["rho_implied_ozna"] - raw["rho_used_kg_m3"]) / raw["rho_used_kg_m3"],
        np.nan,
    )
    raw["density_quality_flag"] = np.where(raw["density_delta_pct"].abs().gt(2.0), "DENSITY_MISMATCH", "")

    gap = raw.groupby("well_code")["measured_at"].diff()
    new_session = gap.isna() | gap.gt(pd.Timedelta(minutes=settings.ozna_session_gap_minutes))
    raw["_session_number"] = new_session.groupby(raw["well_code"]).cumsum().astype(int)
    raw["session_id"] = raw["well_code"] + "-" + raw["_session_number"].astype(str).str.zfill(5)
    return raw


def _build_sessions(raw: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for (well_code, session_id), group in raw.groupby(["well_code", "session_id"], sort=True):
        group = group.sort_values("measured_at")
        started = group["measured_at"].iloc[0]
        ended = group["measured_at"].iloc[-1]
        row: dict[str, object] = {
            "session_id": session_id,
            "well_code": well_code,
            "well_id_src": group["well_id_src"].dropna().iloc[0] if group["well_id_src"].notna().any() else "",
            "started_at": started,
            "ended_at": ended,
            "mid_at": started + (ended - started) / 2,
            "duration_min": round(float((ended - started).total_seconds() / 60.0), 6),
            "n_points": int(group.shape[0]),
            "source_files": "|".join(sorted({str(value) for value in group["source_file"].dropna().unique() if str(value)})),
            "rho_used_kg_m3": _round_or_none(group["rho_used_kg_m3"].dropna().median() if group["rho_used_kg_m3"].notna().any() else None),
            "rho_source": group["rho_source"].dropna().iloc[0] if group["rho_source"].notna().any() else "",
            "rho_implied_ozna": _round_or_none(group["rho_implied_ozna"].dropna().median() if group["rho_implied_ozna"].notna().any() else None),
            "density_delta_pct": _round_or_none(group["density_delta_pct"].dropna().median() if group["density_delta_pct"].notna().any() else None),
        }
        for source_column, prefix in (
            ("qliq_m3d", "qliq"),
            ("qoil_tpd", "qoil_tpd"),
            ("qoil_m3d", "qoil_m3d"),
            ("qgas_m3d", "qgas"),
        ):
            stats = _series_stats(group[source_column])
            for stat_name, value in stats.items():
                row[f"{prefix}_{stat_name}"] = _round_or_none(value) if stat_name != "n_valid" else value
        row["quality_flags"] = "|".join(_quality_flags(row))
        rows.append(row)

    sessions = pd.DataFrame(rows, columns=SESSION_COLUMNS)
    for column in ("started_at", "ended_at", "mid_at"):
        sessions[column] = pd.to_datetime(sessions[column], errors="coerce").map(_format_dt)
    return sessions


def recompute_ozna(
    source_path: Path | None = None,
    raw_path: Path | None = None,
    sessions_path: Path | None = None,
    density_path: Path | None = None,
) -> OznaRecomputeResult:
    source_path = source_path or settings.ozna_source_data_path
    raw_path = raw_path or settings.ozna_raw_data_path
    sessions_path = sessions_path or settings.ozna_sessions_data_path
    density_path = density_path or settings.ozna_pvt_density_data_path

    raw = _prepare_raw_frame(source_path, density_path)
    sessions = _build_sessions(raw)

    raw_out = raw.copy()
    raw_out["measured_at"] = raw_out["measured_at"].map(_format_dt)
    raw_out = raw_out[RAW_COLUMNS]
    _write_csv_atomic(raw_out, raw_path)
    _write_csv_atomic(sessions, sessions_path)
    clear_ozna_cache()

    reference_wells = _load_reference_wells(settings.episodes_compute_enriched_data_path)
    source_wells = set(raw["well_code"].unique())
    matched = source_wells & reference_wells if reference_wells else source_wells
    unmatched = tuple(sorted(source_wells - reference_wells)) if reference_wells else ()
    quality_counts: dict[str, int] = {}
    for flags in sessions["quality_flags"].fillna(""):
        for flag in str(flags).split("|"):
            if flag:
                quality_counts[flag] = quality_counts.get(flag, 0) + 1

    return OznaRecomputeResult(
        raw_rows=int(raw_out.shape[0]),
        session_rows=int(sessions.shape[0]),
        matched_wells=len(matched),
        unmatched_wells=unmatched,
        quality_counts=quality_counts,
        raw_path=raw_path,
        sessions_path=sessions_path,
    )


def _read_csv_dict_rows(path: Path, well_ids: set[str] | None = None) -> list[dict[str, str]]:
    if not path.exists():
        return []
    rows: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source, delimiter=";")
        for row in reader:
            well_code = str(row.get("well_code") or "").strip()
            if well_ids is not None and well_code not in well_ids:
                continue
            rows.append(row)
    return rows


@lru_cache(maxsize=2)
def _load_sessions_cached(path: str, mtime_ns: int, size: int) -> list[dict[str, str]]:
    return _read_csv_dict_rows(Path(path))


def load_ozna_sessions() -> list[dict[str, str]]:
    path = settings.ozna_sessions_data_path
    if not path.exists():
        return []
    stat = path.stat()
    return _load_sessions_cached(str(path), stat.st_mtime_ns, stat.st_size)


def get_ozna_sessions_for_well(well_id: str) -> list[dict[str, str]]:
    return [row for row in load_ozna_sessions() if str(row.get("well_code") or "").strip() == well_id]


def get_ozna_raw_rows_for_session(session_id: str) -> list[dict[str, str]]:
    wanted = str(session_id or "").strip()
    if not wanted:
        return []
    rows = [row for row in iter_ozna_raw_rows(None) if str(row.get("session_id") or "").strip() == wanted]
    rows.sort(key=lambda item: (str(item.get("well_code") or ""), str(item.get("measured_at") or "")))
    return rows


def iter_ozna_raw_rows(well_ids: set[str] | None = None) -> Iterable[dict[str, str]]:
    yield from _read_csv_dict_rows(settings.ozna_raw_data_path, well_ids=well_ids)


def iter_ozna_session_rows(well_ids: set[str] | None = None) -> Iterable[dict[str, str]]:
    yield from _read_csv_dict_rows(settings.ozna_sessions_data_path, well_ids=well_ids)


def clear_ozna_cache() -> None:
    _load_sessions_cached.cache_clear()


def result_to_json(result: OznaRecomputeResult) -> str:
    return json.dumps(
        {
            "raw_rows": result.raw_rows,
            "session_rows": result.session_rows,
            "matched_wells": result.matched_wells,
            "unmatched_wells_count": len(result.unmatched_wells),
            "unmatched_wells_sample": list(result.unmatched_wells[:50]),
            "quality_counts": result.quality_counts,
            "raw_path": str(result.raw_path),
            "sessions_path": str(result.sessions_path),
        },
        ensure_ascii=False,
        indent=2,
    )
