"""Continuous adaptive HAL water-cut line.

A single stateful filter replaces rolling windows + separate event masks.
It produces one smooth daily line on running intervals and updates its target only
from accepted HAL samples.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class WaterCutParams:
    # Samples within this distance from the current level are ordinary updates.
    normal_delta_pp: float = 4.0
    # Larger changes require confirmation by another sample in the same direction.
    event_delta_pp: float = 5.0
    event_confirm_samples: int = 2
    event_max_span_days: int = 21

    # How strongly an accepted sample moves the target.
    stable_sample_gain: float = 0.35
    startup_sample_gain: float = 0.80

    # How quickly the daily displayed line moves toward the target.
    stable_daily_alpha: float = 0.18
    event_daily_alpha: float = 0.55
    startup_daily_alpha: float = 0.70
    event_reaction_days: int = 5

    # Post stop->run period.
    startup_days: int = 7
    startup_min_samples: int = 3


DEFAULT_PARAMS = WaterCutParams()


def _validate_daily(series: pd.Series, name: str) -> pd.Series:
    if not isinstance(series, pd.Series):
        raise TypeError(f"{name} must be a pandas Series")
    if not isinstance(series.index, pd.DatetimeIndex):
        raise TypeError(f"{name} must use a DatetimeIndex")
    out = series.copy()
    out.index = out.index.normalize()
    if not out.index.is_unique:
        raise ValueError(f"{name} must contain one value per calendar day")
    return out.sort_index()


def build_water_cut_line(
    hal_daily: pd.Series,
    running_daily: pd.Series,
    params: WaterCutParams = DEFAULT_PARAMS,
) -> pd.DataFrame:
    """Return a smooth daily line and sample-level diagnostics.

    Rules:
    - first sample after a real stop->run starts a new level immediately;
    - ordinary samples move the target gently;
    - one large sample becomes pending and does not move the line;
    - a second large sample in the same direction confirms the change;
    - after confirmation, the line approaches the new target quickly but smoothly;
    - between samples, the line remains continuous and uses no future data;
    - stop resets the state and produces NaN.
    """
    hal = _validate_daily(hal_daily, "hal_daily")
    running = _validate_daily(running_daily, "running_daily")

    if hal.empty and running.empty:
        return pd.DataFrame()

    starts = [s.index.min() for s in (hal, running) if not s.empty]
    ends = [s.index.max() for s in (hal, running) if not s.empty]
    index = pd.date_range(min(starts), max(ends), freq="D")

    hal = pd.to_numeric(hal.reindex(index), errors="coerce")
    hal = hal.where(hal.between(0.0, 100.0))
    running = running.reindex(index).fillna(False).astype(bool)

    accepted = pd.Series(np.nan, index=index, dtype=float)
    outlier = pd.Series(0, index=index, dtype="int8")
    pending = pd.Series(0, index=index, dtype="int8")
    event_confirmed = pd.Series(0, index=index, dtype="int8")
    signal_updated = pd.Series(0, index=index, dtype="int8")
    target_out = pd.Series(np.nan, index=index, dtype=float)
    line = pd.Series(np.nan, index=index, dtype=float)
    mode = pd.Series("no_data", index=index, dtype="object")
    sample_age = pd.Series(pd.NA, index=index, dtype="Int64")

    state: Optional[float] = None
    target: Optional[float] = None
    last_sample_date: Optional[pd.Timestamp] = None

    previous_running = False
    have_previous_state = False
    startup_start: Optional[pd.Timestamp] = None
    startup_sample_count = 0
    event_days_left = 0

    candidate: list[tuple[pd.Timestamp, float]] = []
    candidate_side: Optional[int] = None
    candidate_baseline: Optional[float] = None

    def clear_candidate(mark_outlier: bool) -> None:
        nonlocal candidate, candidate_side, candidate_baseline
        for pt, _ in candidate:
            pending.loc[pt] = 0
            if mark_outlier:
                outlier.loc[pt] = 1
                accepted.loc[pt] = np.nan
        candidate = []
        candidate_side = None
        candidate_baseline = None

    def accept_normal(t: pd.Timestamp, value: float, gain: float) -> None:
        nonlocal target
        accepted.loc[t] = value
        signal_updated.loc[t] = 1
        if target is None:
            target = value
        else:
            target = gain * value + (1.0 - gain) * target

    for t in index:
        is_running = bool(running.loc[t])

        if not is_running:
            clear_candidate(mark_outlier=True)
            state = None
            target = None
            last_sample_date = None
            startup_start = None
            startup_sample_count = 0
            event_days_left = 0
            mode.loc[t] = "stop"
            previous_running = False
            have_previous_state = True
            continue

        if have_previous_state and not previous_running:
            # Explicit stop -> run. Do not carry the pre-stop level.
            clear_candidate(mark_outlier=True)
            state = None
            target = None
            startup_start = t
            startup_sample_count = 0
            event_days_left = 0

        raw = hal.loc[t]
        has_sample = pd.notna(raw)

        if has_sample:
            value = float(raw)
            last_sample_date = t

            startup_active = startup_start is not None
            if startup_active:
                startup_sample_count += 1
                accepted.loc[t] = value
                signal_updated.loc[t] = 1
                if state is None or target is None:
                    # First sample after startup is the new initial level.
                    state = value
                    target = value
                else:
                    target = (
                        params.startup_sample_gain * value
                        + (1.0 - params.startup_sample_gain) * target
                    )
                clear_candidate(mark_outlier=True)
            elif state is None or target is None:
                # First sample in visible running history.
                state = value
                target = value
                accepted.loc[t] = value
                signal_updated.loc[t] = 1
            else:
                # If a large sample is already pending, decide it using this sample.
                if candidate:
                    assert candidate_baseline is not None
                    assert candidate_side is not None
                    delta_from_old = value - candidate_baseline
                    side = 1 if delta_from_old > 0 else -1
                    same_side_large = (
                        abs(delta_from_old) >= params.event_delta_pp
                        and side == candidate_side
                        and (t - candidate[0][0]).days <= params.event_max_span_days
                    )

                    if same_side_large:
                        candidate.append((t, value))
                        pending.loc[t] = 1
                        if len(candidate) >= params.event_confirm_samples:
                            # Confirm using a robust target from the confirming samples.
                            new_target = float(np.median([v for _, v in candidate]))
                            for pt, pv in candidate:
                                accepted.loc[pt] = pv
                                pending.loc[pt] = 0
                                outlier.loc[pt] = 0
                            target = new_target
                            signal_updated.loc[t] = 1
                            event_confirmed.loc[t] = 1
                            event_days_left = params.event_reaction_days
                            candidate = []
                            candidate_side = None
                            candidate_baseline = None
                    else:
                        # The previous large sample was not confirmed.
                        clear_candidate(mark_outlier=True)
                        # Process the current value afresh below.
                        delta = value - state
                        if abs(delta) >= params.event_delta_pp:
                            candidate = [(t, value)]
                            candidate_side = 1 if delta > 0 else -1
                            candidate_baseline = state
                            pending.loc[t] = 1
                        else:
                            accept_normal(t, value, params.stable_sample_gain)
                else:
                    delta = value - state
                    if abs(delta) >= params.event_delta_pp:
                        candidate = [(t, value)]
                        candidate_side = 1 if delta > 0 else -1
                        candidate_baseline = state
                        pending.loc[t] = 1
                    else:
                        accept_normal(t, value, params.stable_sample_gain)

        # End startup only after both time and sample requirements are satisfied.
        if startup_start is not None:
            elapsed = (t - startup_start).days
            if elapsed >= params.startup_days and startup_sample_count >= params.startup_min_samples:
                startup_start = None

        if state is not None and target is not None:
            if startup_start is not None:
                alpha = params.startup_daily_alpha
                mode.loc[t] = "startup"
            elif event_days_left > 0:
                alpha = params.event_daily_alpha
                mode.loc[t] = "event"
            else:
                alpha = params.stable_daily_alpha
                mode.loc[t] = "stable"

            state = state + alpha * (target - state)
            state = float(np.clip(state, 0.0, 100.0))
            line.loc[t] = state
            target_out.loc[t] = target
            if last_sample_date is not None:
                sample_age.loc[t] = (t - last_sample_date).days
            if event_days_left > 0:
                event_days_left -= 1

        previous_running = is_running
        have_previous_state = True

    # Unresolved candidate remains pending; it is not part of the algorithm level.
    result = pd.DataFrame(
        {
            "water_cut_hal_daily": hal,
            "water_cut_accepted": accepted,
            "water_cut_outlier": outlier,
            "water_cut_pending": pending,
            "water_cut_event_confirmed": event_confirmed,
            "water_cut_signal_updated": signal_updated,
            "water_cut_target": target_out.round(2),
            "water_cut_algo": line.round(2),
            "water_cut_mode": mode,
            "water_cut_sample_age_days": sample_age,
            "running": running.astype("int8"),
        },
        index=index,
    )
    result.index.name = "date"
    return result
