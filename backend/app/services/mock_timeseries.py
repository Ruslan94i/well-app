from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import polars as pl


def _well_seed(well_id: str) -> int:
    return sum(ord(char) for char in well_id)


def _smooth_noise(
    rng: np.random.Generator,
    size: int,
    scale: float,
    window: int,
) -> np.ndarray:
    raw = rng.normal(0.0, scale, size + window - 1)
    kernel = np.ones(window, dtype=float) / window
    return np.convolve(raw, kernel, mode="valid")


def _smooth_step(timeline: np.ndarray, start: float, duration: float) -> np.ndarray:
    scaled = np.clip((timeline - start) / max(duration, 1e-6), 0.0, 1.0)
    return scaled * scaled * (3.0 - 2.0 * scaled)


def _gaussian_pulse(timeline: np.ndarray, center: float, sigma: float) -> np.ndarray:
    return np.exp(-0.5 * ((timeline - center) / max(sigma, 1e-6)) ** 2)


def _get_scenario_params(seed: int) -> dict[str, float]:
    variant = seed % 3

    scenarios: tuple[dict[str, float], ...] = (
        {
            "qliq_start": 124.0,
            "qliq_decline": 0.09,
            "degradation_start": 34.0,
            "degradation_duration": 38.0,
            "degradation_amp": 7.5,
            "downtime_center": 82.0,
            "downtime_sigma": 2.2,
            "downtime_amp": 20.0,
            "replacement_start": 86.0,
            "replacement_duration": 6.0,
            "replacement_amp": 8.0,
            "opz_start": 96.0,
            "opz_fade_start": 112.0,
            "opz_amp": 6.0,
            "water_start": 126.0,
            "water_duration": 34.0,
            "water_amp": 14.0,
            "regime_start": 148.0,
            "regime_duration": 12.0,
            "regime_amp": 2.2,
        },
        {
            "qliq_start": 118.0,
            "qliq_decline": 0.07,
            "degradation_start": 58.0,
            "degradation_duration": 22.0,
            "degradation_amp": 4.8,
            "downtime_center": 54.0,
            "downtime_sigma": 3.2,
            "downtime_amp": 10.5,
            "replacement_start": 103.0,
            "replacement_duration": 8.0,
            "replacement_amp": 5.5,
            "opz_start": 118.0,
            "opz_fade_start": 132.0,
            "opz_amp": 3.8,
            "water_start": 138.0,
            "water_duration": 24.0,
            "water_amp": 7.5,
            "regime_start": 74.0,
            "regime_duration": 10.0,
            "regime_amp": 3.0,
        },
        {
            "qliq_start": 121.0,
            "qliq_decline": 0.08,
            "degradation_start": 24.0,
            "degradation_duration": 30.0,
            "degradation_amp": 5.2,
            "downtime_center": 118.0,
            "downtime_sigma": 2.0,
            "downtime_amp": 8.0,
            "replacement_start": 122.0,
            "replacement_duration": 5.0,
            "replacement_amp": 4.0,
            "opz_start": 70.0,
            "opz_fade_start": 88.0,
            "opz_amp": 4.8,
            "water_start": 92.0,
            "water_duration": 42.0,
            "water_amp": 16.0,
            "regime_start": 146.0,
            "regime_duration": 14.0,
            "regime_amp": 3.6,
        },
    )

    return scenarios[variant]


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
    seed = _well_seed(well_id)
    rng = np.random.default_rng(seed)
    params = _get_scenario_params(seed)

    degradation = _smooth_step(
        timeline,
        start=params["degradation_start"],
        duration=params["degradation_duration"],
    )
    downtime = _gaussian_pulse(
        timeline,
        center=params["downtime_center"],
        sigma=params["downtime_sigma"],
    )
    replacement_reset = _smooth_step(
        timeline,
        start=params["replacement_start"],
        duration=params["replacement_duration"],
    )
    opz_effect = np.where(
        timeline >= params["opz_start"],
        1.0 - np.exp(-0.18 * np.clip(timeline - params["opz_start"], 0.0, None)),
        0.0,
    ) - np.where(
        timeline >= params["opz_fade_start"],
        1.0 - np.exp(-0.08 * np.clip(timeline - params["opz_fade_start"], 0.0, None)),
        0.0,
    )
    opz_effect = np.clip(opz_effect, 0.0, None)
    water_breakthrough = _smooth_step(
        timeline,
        start=params["water_start"],
        duration=params["water_duration"],
    )
    regime_shift = _smooth_step(
        timeline,
        start=params["regime_start"],
        duration=params["regime_duration"],
    )

    qliq_trend = params["qliq_start"] - params["qliq_decline"] * timeline
    qliq = (
        qliq_trend
        - params["degradation_amp"] * degradation
        - params["downtime_amp"] * downtime
        + params["replacement_amp"] * replacement_reset
        + params["opz_amp"] * opz_effect
        - (0.32 * params["water_amp"]) * water_breakthrough
        - (0.9 * params["regime_amp"]) * regime_shift
        + 0.9 * np.sin(timeline / 17.0)
        + _smooth_noise(rng, total_days, scale=0.85, window=7)
    )
    qliq = np.clip(qliq, 62.0, None)

    water_cut = (
        23.0
        + 0.035 * timeline
        + 0.9 * degradation
        - 1.1 * opz_effect
        + params["water_amp"] * water_breakthrough
        + params["regime_amp"] * regime_shift
        + _smooth_noise(rng, total_days, scale=0.55, window=11)
    )
    water_cut = np.clip(water_cut, 8.0, 92.0)

    qoil = (
        qliq * (1.0 - water_cut / 100.0)
        - 1.8 * degradation
        + 2.2 * opz_effect
        - (2.2 + 0.08 * params["water_amp"]) * water_breakthrough
        + _smooth_noise(rng, total_days, scale=0.65, window=5)
    )
    qoil = np.minimum(qoil, qliq * 0.95)
    qoil = np.clip(qoil, 12.0, None)

    gas_factor = (
        198.0
        + 0.03 * timeline
        - 6.0 * degradation
        - 10.0 * downtime
        + 8.5 * replacement_reset
        + 14.0 * opz_effect
        + 12.0 * water_breakthrough
        + 5.0 * regime_shift
        + 4.0 * np.sin(timeline / 29.0)
        + _smooth_noise(rng, total_days, scale=3.2, window=9)
    )
    gas_factor = np.clip(gas_factor, 145.0, 285.0)

    qgas = qoil * gas_factor
    qgas = np.clip(qgas, 1800.0, None)

    gas_liquid_factor = qgas / np.maximum(qliq, 1.0)

    qliq_vfm = (
        qliq * (1.006 + 0.004 * np.sin(timeline / 23.0))
        + _smooth_noise(rng, total_days, scale=0.55, window=5)
    )
    qliq_vfm = np.clip(qliq_vfm, 60.0, None)

    intake_pressure = (
        116.5
        - 0.018 * timeline
        + (2.0 + 0.18 * params["degradation_amp"]) * degradation
        - (3.8 + 0.22 * params["downtime_amp"]) * downtime
        - (1.2 + 0.16 * params["replacement_amp"]) * replacement_reset
        + (1.8 + 0.14 * params["water_amp"]) * water_breakthrough
        + 0.7 * params["regime_amp"] * regime_shift
        + 1.1 * np.sin(timeline / 21.0)
        + _smooth_noise(rng, total_days, scale=0.75, window=7)
    )

    esp_frequency = (
        49.6
        - 0.18 * degradation
        - (1.0 + 0.12 * params["downtime_amp"]) * downtime
        + 0.14 * params["replacement_amp"] * replacement_reset
        - 0.025 * params["water_amp"] * water_breakthrough
        + 0.1 * params["regime_amp"] * regime_shift
        + _smooth_noise(rng, total_days, scale=0.08, window=9)
    )
    esp_frequency = np.clip(esp_frequency, 43.5, 52.5)

    load = (
        61.5
        - 0.025 * timeline
        - (0.9 + 0.12 * params["degradation_amp"]) * degradation
        - (2.8 + 0.18 * params["downtime_amp"]) * downtime
        + params["replacement_amp"] * 0.24 * replacement_reset
        + 0.2 * params["opz_amp"] * opz_effect
        + (0.4 + 0.08 * params["water_amp"]) * water_breakthrough
        + 0.9 * np.sin(timeline / 26.0)
        + _smooth_noise(rng, total_days, scale=0.45, window=7)
    )
    load = np.clip(load, 42.0, 74.0)

    frame = pl.DataFrame(
        {
            "date": dates,
            "qliq": np.round(qliq, 2),
            "qoil": np.round(qoil, 2),
            "qgas": np.round(qgas, 2),
            "gas_factor": np.round(gas_factor, 2),
            "gas_liquid_factor": np.round(gas_liquid_factor, 2),
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
