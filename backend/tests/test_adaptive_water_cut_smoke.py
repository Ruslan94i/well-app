import numpy as np
import pandas as pd

from app.services.adaptive_water_cut import build_water_cut_line


def s(values, start="2025-01-01"):
    return pd.Series(values, index=pd.date_range(start, periods=len(values), freq="D"), dtype=float)


def test_continuous_line_between_sparse_samples():
    wc = s([60, np.nan, np.nan, 62, np.nan, np.nan, 63])
    run = s([1] * len(wc)).astype(bool)
    out = build_water_cut_line(wc, run)
    assert out["water_cut_algo"].notna().all()


def test_one_large_sample_is_pending_not_line_change():
    wc = s([60, 60, 60, 80, 60, 60])
    run = s([1] * len(wc)).astype(bool)
    out = build_water_cut_line(wc, run)
    assert out.loc[wc.index[3], "water_cut_outlier"] == 1
    assert out.loc[wc.index[3], "water_cut_algo"] < 65
    assert out.loc[wc.index[3], "water_cut_signal_updated"] == 0


def test_two_large_samples_confirm_and_line_reacts_smoothly():
    wc = s([60, 60, 60, 72, 73, np.nan, np.nan, np.nan])
    run = s([1] * len(wc)).astype(bool)
    out = build_water_cut_line(wc, run)
    assert out["water_cut_event_confirmed"].sum() == 1
    assert 60 < out.loc[wc.index[4], "water_cut_algo"] < 73
    assert out["water_cut_algo"].iloc[-1] > 69


def test_restart_first_sample_sets_new_level():
    wc = s([60, np.nan, np.nan, 90, 86, 82])
    run = s([1, 0, 0, 1, 1, 1]).astype(bool)
    out = build_water_cut_line(wc, run)
    assert np.isnan(out["water_cut_algo"].iloc[1])
    assert out["water_cut_algo"].iloc[3] == 90
