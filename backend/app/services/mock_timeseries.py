from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import polars as pl


def _well_seed(well_id: str) -> int:
    return sum(ord(char) for char in well_id)


def generate_well_timeseries(
    well_id: str,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[dict[str, object]]:
    total_days = 180
    end_date = date.today()
    start_date = end_date - timedelta(days=total_days - 1)

    dates = [start_date + timedelta(days=index) for index in range(total_days)]
    timeline = np.arange(total_days, dtype=float)

    rng = np.random.default_rng(_well_seed(well_id))

    qliq_base = np.linspace(125.0, 88.0, total_days)
    qliq = qliq_base + rng.normal(0.0, 1.8, total_days)
    qliq = np.clip(qliq, 60.0, None)

    water_cut = np.linspace(22.0, 46.0, total_days) + rng.normal(0.0, 0.7, total_days)
    water_cut = np.clip(water_cut, 5.0, 95.0)

    qoil = qliq * (1 - water_cut / 100.0) + rng.normal(0.0, 1.0, total_days)
    qoil = np.clip(qoil, 20.0, None)

    qliq_vfm = qliq * 1.01 + rng.normal(0.0, 1.3, total_days)
    intake_pressure = 118.0 + 5.5 * np.sin(timeline / 13.0) + rng.normal(0.0, 1.2, total_days)
    esp_frequency = 49.8 + 0.25 * np.sin(timeline / 24.0) + rng.normal(0.0, 0.05, total_days)
    load = 63.0 + 1.7 * np.sin(timeline / 17.0) + rng.normal(0.0, 0.45, total_days)

    frame = pl.DataFrame(
        {
            "date": dates,
            "qliq": np.round(qliq, 2),
            "qoil": np.round(qoil, 2),
            "qliq_vfm": np.round(qliq_vfm, 2),
            "water_cut": np.round(water_cut, 2),
            "intake_pressure": np.round(intake_pressure, 2),
            "esp_frequency": np.round(esp_frequency, 2),
            "load": np.round(load, 2),
        }
    )

    if date_from is not None:
        frame = frame.filter(pl.col("date") >= pl.lit(date_from))

    if date_to is not None:
        frame = frame.filter(pl.col("date") <= pl.lit(date_to))

    frame = frame.with_columns(pl.col("date").dt.strftime("%Y-%m-%d"))

    return frame.to_dicts()

