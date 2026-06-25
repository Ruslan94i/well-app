from __future__ import annotations

import logging
import math
import os
import sys
import warnings
from functools import lru_cache
from pathlib import Path
from typing import Any

import polars as pl

from app.core.config import settings


logger = logging.getLogger(__name__)

MODEL_PATH = settings.water_cut_algorithm_model_path
os.environ.setdefault("LOKY_MAX_CPU_COUNT", "1")

FEATURE_SOURCE_COLUMNS = {
    "telemetry_buffer_pressure": "buffer_pressure",
    "telemetry_casing_pressure": "casing_pressure",
    "telemetry_intake_pressure": "intake_pressure",
    "telemetry_load": "load",
    "telemetry_esp_frequency": "esp_frequency",
    "telemetry_active_power": "active_power",
    "telemetry_qliq": "qliq",
    "telemetry_qoil": "qoil",
    "telemetry_water_cut": "water_cut",
    "tr_bottomhole_pressure": None,
    "tr_oil_rate": None,
    "tr_liquid_rate": None,
    "tr_water_cut": None,
}

DAILY_MEAN_FEATURE_COLUMNS = {
    "buffer_pressure": "telemetry_buffer_pressure_mean",
    "casing_pressure": "telemetry_casing_pressure_mean",
    "intake_pressure": "telemetry_intake_pressure_mean",
    "load": "telemetry_load_mean",
    "esp_frequency": "telemetry_esp_frequency_mean",
    "active_power": "telemetry_active_power_mean",
    "qliq": "telemetry_qliq_mean",
    "qoil": "telemetry_qoil_mean",
    "water_cut": "telemetry_water_cut_mean",
}

DAILY_STD_FEATURE_COLUMNS = {
    "buffer_pressure": "telemetry_buffer_pressure_std",
    "casing_pressure": "telemetry_casing_pressure_std",
    "intake_pressure": "telemetry_intake_pressure_std",
    "load": "telemetry_load_std",
    "esp_frequency": "telemetry_esp_frequency_std",
}

TELEMETRY_RECORD_COLUMNS = [
    "buffer_pressure",
    "casing_pressure",
    "intake_pressure",
    "load",
    "esp_frequency",
    "active_power",
]


def _implied_water_cut_expr() -> pl.Expr:
    return (
        pl.when((pl.col("qliq") > 0) & pl.col("qoil").is_not_null())
        .then((100.0 * (1.0 - (pl.col("qoil") / (pl.col("qliq") * 0.82)))).clip(0.0, 100.0))
        .otherwise(None)
    )


def _with_fallback_water_cut_algorithm(frame: pl.DataFrame) -> pl.DataFrame:
    daily_pdf = _build_daily_feature_frame(frame, [])
    if daily_pdf.empty:
        return _apply_daily_predictions(frame, [])

    values = daily_pdf["water_cut_algorithm_fallback"].tolist()
    return _apply_daily_predictions(frame, values)


def _patch_sklearn_loss_module() -> None:
    try:
        import sklearn._loss as loss  # type: ignore

        if not hasattr(loss, "CyHalfSquaredError") and hasattr(loss, "HalfSquaredError"):
            loss.CyHalfSquaredError = loss.HalfSquaredError
        sys.modules["_loss"] = loss
    except Exception:
        return


@lru_cache(maxsize=1)
def _load_model_bundle(model_path: str, model_mtime_ns: int, model_size: int) -> tuple[Any, list[str]] | None:
    path = Path(model_path)
    if not path.exists() or model_size <= 0:
        return None

    try:
        _patch_sklearn_loss_module()
        import joblib  # type: ignore

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            bundle = joblib.load(path)

        if isinstance(bundle, dict):
            model = bundle.get("model")
            features = bundle.get("features") or getattr(model, "feature_names_in_", None)
        else:
            model = bundle
            features = getattr(model, "feature_names_in_", None)

        if model is None or not features:
            logger.warning("Water cut algorithm model %s has no model/features payload", path)
            return None

        return model, [str(feature) for feature in features]
    except Exception as exc:
        logger.warning("Cannot load water cut algorithm model %s: %s", path, exc)
        return None


def _get_model_bundle() -> tuple[Any, list[str]] | None:
    if not MODEL_PATH.exists():
        return None

    model_stat = MODEL_PATH.stat()
    return _load_model_bundle(str(MODEL_PATH), model_stat.st_mtime_ns, model_stat.st_size)


def _as_numeric_series(pdf: Any, source_column: str | None) -> Any:
    import pandas as pd  # type: ignore

    if source_column is None or source_column not in pdf:
        return pd.Series(math.nan, index=pdf.index, dtype="float64")
    return pd.to_numeric(pdf[source_column], errors="coerce")


def _path_cache_key(path: Path) -> tuple[str, int, int]:
    if not path.exists():
        return str(path), 0, 0
    stat = path.stat()
    return str(path), stat.st_mtime_ns, stat.st_size


@lru_cache(maxsize=4)
def _load_tr_daily_frame(path: str, path_mtime_ns: int, path_size: int) -> Any:
    import pandas as pd  # type: ignore

    if path_size <= 0:
        return pd.DataFrame()

    source = Path(path)
    if not source.exists():
        return pd.DataFrame()

    tr = pd.read_csv(source)
    required = {"well_id", "date", "bottomhole_pressure", "oil_rate", "liquid_rate", "water_cut"}
    if not required.issubset(tr.columns):
        logger.warning("TR monitoring file %s has no required columns: %s", source, sorted(required - set(tr.columns)))
        return pd.DataFrame()

    tr = tr[["well_id", "date", "bottomhole_pressure", "oil_rate", "liquid_rate", "water_cut"]].copy()
    tr["well_id"] = tr["well_id"].astype(str)
    tr["_tr_date"] = pd.to_datetime(tr["date"], errors="coerce").dt.floor("D")
    tr = tr.dropna(subset=["well_id", "_tr_date"])
    for column in ("bottomhole_pressure", "oil_rate", "liquid_rate", "water_cut"):
        tr[column] = pd.to_numeric(tr[column], errors="coerce")

    tr = (
        tr.groupby(["well_id", "_tr_date"], as_index=False)
        .agg(
            tr_bottomhole_pressure_mean=("bottomhole_pressure", "mean"),
            tr_oil_rate_mean=("oil_rate", "mean"),
            tr_liquid_rate_mean=("liquid_rate", "mean"),
            tr_water_cut_mean=("water_cut", "mean"),
        )
        .sort_values(["well_id", "_tr_date"])
        .reset_index(drop=True)
    )
    return tr


@lru_cache(maxsize=4)
def _load_hal_daily_frame(path: str, path_mtime_ns: int, path_size: int) -> Any:
    import pandas as pd  # type: ignore

    if path_size <= 0:
        return pd.DataFrame()

    source = Path(path)
    if not source.exists():
        return pd.DataFrame()

    hal = pd.read_csv(source, sep=";")
    if len(hal.columns) == 1:
        hal = pd.read_csv(source)

    value_column = "water_cut_hal" if "water_cut_hal" in hal.columns else "hal" if "hal" in hal.columns else None
    if "well_id" not in hal.columns or "date" not in hal.columns or value_column is None:
        logger.warning("HAL water cut file %s has no required columns", source)
        return pd.DataFrame()

    hal = hal[["well_id", "date", value_column]].copy()
    hal["well_id"] = hal["well_id"].astype(str)
    hal["_hal_date"] = pd.to_datetime(hal["date"], errors="coerce").dt.floor("D")
    hal["hal_value"] = pd.to_numeric(hal[value_column], errors="coerce")
    hal = hal.dropna(subset=["well_id", "_hal_date", "hal_value"])
    return (
        hal.groupby(["well_id", "_hal_date"], as_index=False)["hal_value"]
        .mean()
        .sort_values(["well_id", "_hal_date"])
        .reset_index(drop=True)
    )


def _merge_tr_features(daily: Any) -> Any:
    import pandas as pd  # type: ignore

    tr_feature_columns = [
        "tr_bottomhole_pressure_mean",
        "tr_oil_rate_mean",
        "tr_liquid_rate_mean",
        "tr_water_cut_mean",
    ]
    tr = _load_tr_daily_frame(*_path_cache_key(settings.tr_monitoring_data_path))
    if tr.empty:
        for feature_name in tr_feature_columns:
            daily[feature_name] = math.nan
        return daily

    merged_parts = []
    for well_id, well_daily in daily.groupby("well_id", sort=False):
        well_daily = well_daily.sort_values("_water_cut_day").copy()
        well_tr = tr[tr["well_id"] == str(well_id)].sort_values("_tr_date")
        if well_tr.empty:
            for feature_name in tr_feature_columns:
                well_daily[feature_name] = math.nan
            merged_parts.append(well_daily)
            continue

        merged = pd.merge_asof(
            well_daily,
            well_tr[["_tr_date", *tr_feature_columns]],
            left_on="_water_cut_day",
            right_on="_tr_date",
            direction="backward",
        ).drop(columns=["_tr_date"])
        merged_parts.append(merged)

    return pd.concat(merged_parts, ignore_index=True).sort_values(["well_id", "_water_cut_day"]).reset_index(drop=True)


def _merge_hal_features(daily: Any, raw_pdf: Any) -> Any:
    import pandas as pd  # type: ignore

    hal = _load_hal_daily_frame(*_path_cache_key(settings.water_cut_hal_data_path))
    if hal.empty and "water_cut_hal" in raw_pdf:
        fallback = raw_pdf[["well_id", "_water_cut_day", "water_cut_hal"]].copy()
        fallback["hal_value"] = pd.to_numeric(fallback["water_cut_hal"], errors="coerce")
        fallback = fallback.dropna(subset=["well_id", "_water_cut_day", "hal_value"])
        hal = (
            fallback.groupby(["well_id", "_water_cut_day"], as_index=False)["hal_value"]
            .mean()
            .rename(columns={"_water_cut_day": "_hal_date"})
            .sort_values(["well_id", "_hal_date"])
            .reset_index(drop=True)
        )

    daily["hal_last"] = math.nan
    daily["hal_days_since"] = math.nan
    daily["hal_mean30"] = math.nan
    if hal.empty:
        return daily

    merged_parts = []
    for well_id, well_daily in daily.groupby("well_id", sort=False):
        well_daily = well_daily.sort_values("_water_cut_day").copy()
        well_hal = hal[hal["well_id"] == str(well_id)].sort_values("_hal_date")
        if well_hal.empty:
            merged_parts.append(well_daily)
            continue

        merged = pd.merge_asof(
            well_daily.drop(columns=["hal_last", "hal_days_since", "hal_mean30"]),
            well_hal[["_hal_date", "hal_value"]].rename(columns={"hal_value": "hal_last"}),
            left_on="_water_cut_day",
            right_on="_hal_date",
            direction="backward",
        )
        merged["hal_days_since"] = (merged["_water_cut_day"] - merged["_hal_date"]).dt.total_seconds() / 86400.0

        hal_series = well_hal.set_index("_hal_date")["hal_value"].sort_index()
        merged["hal_mean30"] = merged["_water_cut_day"].map(
            lambda day: hal_series[(hal_series.index <= day) & (hal_series.index > day - pd.Timedelta(days=30))].mean()
        )
        merged = merged.drop(columns=["_hal_date"])
        merged_parts.append(merged)

    return pd.concat(merged_parts, ignore_index=True).sort_values(["well_id", "_water_cut_day"]).reset_index(drop=True)


def _rolling_mean(series: Any, well_ids: Any, window: int) -> Any:
    return series.groupby(well_ids).transform(lambda values: values.rolling(window, min_periods=1).mean())


def _rolling_std(series: Any, well_ids: Any, window: int) -> Any:
    return series.groupby(well_ids).transform(lambda values: values.rolling(window, min_periods=2).std()).fillna(0.0)


def _build_daily_feature_frame(frame: pl.DataFrame, features: list[str]) -> Any:
    import pandas as pd  # type: ignore

    selected_columns = ["well_id", "date", *[column for column in frame.columns if column not in {"well_id", "date"}]]
    pdf = pd.DataFrame(frame.select(selected_columns).to_dicts())
    if pdf.empty:
        return pd.DataFrame(columns=features)

    pdf["date"] = pd.to_datetime(pdf["date"], errors="coerce")
    pdf = pdf.dropna(subset=["well_id", "date"]).copy()
    pdf["_water_cut_day"] = pdf["date"].dt.floor("D")
    grouped = pdf.groupby(["well_id", "_water_cut_day"], sort=True, dropna=False)

    daily = grouped.size().rename("_raw_rows").reset_index()
    daily["telem_records"] = daily["_raw_rows"]

    for source_column, feature_name in DAILY_MEAN_FEATURE_COLUMNS.items():
        if source_column in pdf:
            values = grouped[source_column].mean().rename(feature_name).reset_index()
            daily = daily.merge(values, on=["well_id", "_water_cut_day"], how="left")
        else:
            daily[feature_name] = math.nan

    for source_column, feature_name in DAILY_STD_FEATURE_COLUMNS.items():
        if source_column in pdf:
            values = grouped[source_column].std().rename(feature_name).reset_index()
            daily = daily.merge(values, on=["well_id", "_water_cut_day"], how="left")
        else:
            daily[feature_name] = math.nan

    daily = daily.sort_values(["well_id", "_water_cut_day"]).reset_index(drop=True)
    if daily.duplicated(["well_id", "_water_cut_day"]).any():
        raise ValueError("Water cut daily feature frame must contain exactly one row per well/day")

    daily = _merge_tr_features(daily)
    daily = _merge_hal_features(daily, pdf)

    qliq = daily["telemetry_qliq_mean"]
    qoil = daily["telemetry_qoil_mean"]
    tr_liquid = daily["tr_liquid_rate_mean"]
    tr_oil = daily["tr_oil_rate_mean"]
    daily["implied_wct_scada"] = (100.0 * (qliq - qoil) / qliq).where(qliq > 0).clip(0.0, 100.0)
    daily["implied_wct_tr"] = (100.0 * (tr_liquid - tr_oil) / tr_liquid).where(tr_liquid > 0).clip(0.0, 100.0)

    daily["water_cut_algorithm_fallback"] = (
        daily[["hal_last", "telemetry_water_cut_mean", "implied_wct_scada"]]
        .bfill(axis=1)
        .iloc[:, 0]
        .clip(0.0, 100.0)
    )
    daily["water_cut_algorithm_fallback"] = daily.groupby("well_id")["water_cut_algorithm_fallback"].transform(
        lambda values: values.ffill().bfill()
    )

    feature_values: dict[str, Any] = {}
    well_ids = daily["well_id"]

    for feature in features:
        if feature == "telem_records":
            feature_values[feature] = daily["telem_records"]
            continue

        source_key = feature
        rolling_window: int | None = None
        if source_key.endswith("_r3"):
            rolling_window = 3
            source_key = source_key[:-3]
        elif source_key.endswith("_r7"):
            rolling_window = 7
            source_key = source_key[:-3]

        if rolling_window is not None:
            series = pd.to_numeric(daily[source_key], errors="coerce") if source_key in daily else pd.Series(math.nan, index=daily.index)
            feature_values[feature] = _rolling_mean(series, well_ids, rolling_window)
        elif source_key in daily:
            feature_values[feature] = pd.to_numeric(daily[source_key], errors="coerce")
        else:
            feature_values[feature] = pd.Series(math.nan, index=daily.index, dtype="float64")

    result = pd.DataFrame(feature_values, columns=features)
    result.insert(0, "_water_cut_day", daily["_water_cut_day"])
    result.insert(0, "well_id", daily["well_id"])
    result["water_cut_algorithm_fallback"] = daily["water_cut_algorithm_fallback"]
    return result.replace([math.inf, -math.inf], math.nan)


def _apply_daily_predictions(frame: pl.DataFrame, predictions: list[float | None]) -> pl.DataFrame:
    daily_pdf = _build_daily_feature_frame(frame, [])
    if daily_pdf.empty:
        return frame.with_columns(pl.lit(None, dtype=pl.Float64).alias("water_cut_algorithm"))

    if predictions:
        if len(predictions) != len(daily_pdf):
            raise ValueError(
                "Water cut prediction count must match daily well/day rows "
                f"({len(predictions)} predictions for {len(daily_pdf)} daily rows)"
            )
        values = predictions
    else:
        values = [
            float(value) if value is not None and math.isfinite(float(value)) else None
            for value in daily_pdf["water_cut_algorithm_fallback"].tolist()
        ]

    daily_predictions = pl.DataFrame(
        {
            "well_id": daily_pdf["well_id"].astype(str).tolist(),
            "_water_cut_day": daily_pdf["_water_cut_day"].dt.to_pydatetime().tolist(),
            "_water_cut_algorithm_daily": values,
        },
        schema={
            "well_id": pl.Utf8,
            "_water_cut_day": pl.Datetime,
            "_water_cut_algorithm_daily": pl.Float64,
        },
        strict=False,
    )

    return (
        frame.with_row_index("_water_cut_row")
        .with_columns(pl.col("date").dt.truncate("1d").alias("_water_cut_day"))
        .join(daily_predictions, on=["well_id", "_water_cut_day"], how="left")
        .with_columns(
            pl.when(
                pl.col("_water_cut_row")
                == pl.col("_water_cut_row").min().over(["well_id", "_water_cut_day"])
            )
            .then(pl.col("_water_cut_algorithm_daily"))
            .otherwise(None)
            .cast(pl.Float64)
            .alias("water_cut_algorithm")
        )
        .drop(["_water_cut_row", "_water_cut_day", "_water_cut_algorithm_daily"])
    )


def add_water_cut_algorithm(frame: pl.DataFrame) -> pl.DataFrame:
    if frame.is_empty():
        return frame.with_columns(pl.lit(None, dtype=pl.Float64).alias("water_cut_algorithm"))

    model_bundle = _get_model_bundle()
    if model_bundle is None:
        return _with_fallback_water_cut_algorithm(frame)

    model, features = model_bundle
    try:
        feature_frame = _build_daily_feature_frame(frame, features)
        if feature_frame.duplicated(["well_id", "_water_cut_day"]).any():
            raise ValueError("Water cut model features must be unique by well/day")
        prediction_features = feature_frame.reindex(columns=features)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            predictions = model.predict(prediction_features)
        clean_predictions = [
            float(min(100.0, max(0.0, value))) if value is not None and math.isfinite(float(value)) else None
            for value in predictions
        ]
        return _apply_daily_predictions(frame, clean_predictions)
    except Exception as exc:
        logger.warning("Water cut algorithm prediction failed; using fallback values: %s", exc)
        return _with_fallback_water_cut_algorithm(frame)
