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


def _implied_water_cut_expr() -> pl.Expr:
    return (
        pl.when((pl.col("qliq") > 0) & pl.col("qoil").is_not_null())
        .then((100.0 * (1.0 - (pl.col("qoil") / (pl.col("qliq") * 0.82)))).clip(0.0, 100.0))
        .otherwise(None)
    )


def _with_fallback_water_cut_algorithm(frame: pl.DataFrame) -> pl.DataFrame:
    if "water_cut_algorithm" not in frame.columns:
        frame = frame.with_columns(pl.lit(None, dtype=pl.Float64).alias("water_cut_algorithm"))

    return (
        frame.with_columns(
            pl.coalesce(
                [
                    pl.col("water_cut_algorithm"),
                    pl.col("water_cut_hal"),
                    pl.col("water_cut"),
                    _implied_water_cut_expr(),
                ]
            )
            .cast(pl.Float64)
            .clip(0.0, 100.0)
            .alias("_water_cut_algorithm_base")
        )
        .with_columns(
            pl.col("_water_cut_algorithm_base")
            .forward_fill()
            .backward_fill()
            .over("well_id")
            .alias("water_cut_algorithm")
        )
        .drop("_water_cut_algorithm_base")
    )


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


def _rolling_mean(series: Any, well_ids: Any, window: int) -> Any:
    return series.groupby(well_ids).transform(lambda values: values.rolling(window, min_periods=1).mean())


def _rolling_std(series: Any, well_ids: Any, window: int) -> Any:
    return series.groupby(well_ids).transform(lambda values: values.rolling(window, min_periods=2).std()).fillna(0.0)


def _build_feature_frame(frame: pl.DataFrame, features: list[str]) -> Any:
    import pandas as pd  # type: ignore

    pdf = pd.DataFrame(frame.select(["well_id", "date", *[column for column in frame.columns if column not in {"well_id", "date"}]]).to_dicts())
    if pdf.empty:
        return pd.DataFrame(columns=features)

    pdf["date"] = pd.to_datetime(pdf["date"], errors="coerce")
    well_ids = pdf["well_id"]
    feature_values: dict[str, Any] = {}

    qliq = _as_numeric_series(pdf, "qliq")
    qoil = _as_numeric_series(pdf, "qoil")
    water_cut = _as_numeric_series(pdf, "water_cut")
    hal = _as_numeric_series(pdf, "water_cut_hal")

    implied_scada = (100.0 * (1.0 - (qoil / (qliq * 0.82)))).where(qliq > 0).clip(0.0, 100.0)
    hal_last = hal.groupby(well_ids).ffill()
    hal_dates = pdf["date"].where(hal.notna()).groupby(well_ids).ffill()
    hal_days_since = (pdf["date"] - hal_dates).dt.total_seconds() / 86400.0
    hal_mean30 = hal.groupby(well_ids).transform(lambda values: values.ffill().rolling(30, min_periods=1).mean())

    for feature in features:
        if feature == "telem_records":
            telemetry_columns = [
                "buffer_pressure",
                "casing_pressure",
                "intake_pressure",
                "load",
                "esp_frequency",
                "active_power",
            ]
            available = [column for column in telemetry_columns if column in pdf]
            feature_values[feature] = pdf[available].notna().sum(axis=1) if available else 0
            continue
        if feature == "implied_wct_scada":
            feature_values[feature] = implied_scada
            continue
        if feature == "implied_wct_tr":
            feature_values[feature] = pd.Series(math.nan, index=pdf.index, dtype="float64")
            continue
        if feature == "hal_last":
            feature_values[feature] = hal_last
            continue
        if feature == "hal_days_since":
            feature_values[feature] = hal_days_since
            continue
        if feature == "hal_mean30":
            feature_values[feature] = hal_mean30
            continue

        source_key = feature
        rolling_window: int | None = None
        if source_key.endswith("_r3"):
            rolling_window = 3
            source_key = source_key[:-3]
        elif source_key.endswith("_r7"):
            rolling_window = 7
            source_key = source_key[:-3]

        statistic = None
        if source_key.endswith("_mean"):
            statistic = "mean"
            source_key = source_key[:-5]
        elif source_key.endswith("_std"):
            statistic = "std"
            source_key = source_key[:-4]

        source_column = FEATURE_SOURCE_COLUMNS.get(source_key)
        series = _as_numeric_series(pdf, source_column)

        if rolling_window is not None:
            feature_values[feature] = _rolling_mean(series, well_ids, rolling_window)
        elif statistic == "std":
            feature_values[feature] = _rolling_std(series, well_ids, 6)
        else:
            feature_values[feature] = series

    result = pd.DataFrame(feature_values, columns=features)
    return result.replace([math.inf, -math.inf], math.nan)


def add_water_cut_algorithm(frame: pl.DataFrame) -> pl.DataFrame:
    if frame.is_empty():
        return frame.with_columns(pl.lit(None, dtype=pl.Float64).alias("water_cut_algorithm"))

    model_bundle = _get_model_bundle()
    if model_bundle is None:
        return _with_fallback_water_cut_algorithm(frame)

    model, features = model_bundle
    try:
        feature_frame = _build_feature_frame(frame, features)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            predictions = model.predict(feature_frame)
        clean_predictions = [
            float(min(100.0, max(0.0, value))) if value is not None and math.isfinite(float(value)) else None
            for value in predictions
        ]
        return _with_fallback_water_cut_algorithm(
            frame.with_columns(pl.Series("water_cut_algorithm", clean_predictions, dtype=pl.Float64))
        )
    except Exception as exc:
        logger.warning("Water cut algorithm prediction failed; using fallback values: %s", exc)
        return _with_fallback_water_cut_algorithm(frame)
