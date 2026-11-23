"""Unit tests of the second instrument (HARPS-N series) and of the two-instrument summary."""
import numpy as np
import pandas as pd
import pytest

import helpers
from flinch import _http, harpsn, replication
from flinch.timeutil import MINUTE


def test_read_series_takes_the_time_from_the_file_name(archive):
    table = helpers.write_harpsn(archive["root"] / "data", archive["flares"])
    series = harpsn.read_series()
    assert len(series) == len(table)
    assert series["obsjd"].to_numpy() == pytest.approx(np.sort(table["obsjd_true"].to_numpy()), abs=1.0e-7)  # not the barycentric date
    assert (series["jd"] - series["obsjd"]).to_numpy() == pytest.approx(150.0 / 86400.0)
    assert series["rv_ms"].mean() == pytest.approx(1000.0 * table["rv"].mean())


def test_download_is_skipped_when_the_series_is_on_disk(archive, monkeypatch):
    helpers.write_harpsn(archive["root"] / "data", archive["flares"])
    monkeypatch.setattr(_http, "download", lambda *a, **k: pytest.fail("the network must not be used"))
    assert harpsn.download_series() == harpsn.series_path()


def test_prepare_removes_the_daily_trend_and_the_flagged_exposures(archive):
    helpers.write_harpsn(archive["root"] / "data", archive["flares"])
    raw = harpsn.read_series()
    raw.loc[5:9, "obs_quality"] = 0.5  # clouds
    raw.loc[20, "rv_ms"] += 30.0  # an outlier
    prepared = harpsn.prepare(raw)
    assert not prepared.loc[5:9, "good"].any() and not prepared.loc[20, "good"]
    good = prepared[prepared["good"]]
    assert abs(good["res"].mean()) < 0.02 and good["res"].std() == pytest.approx(0.4, rel=0.1)
    assert good.groupby("day")["res"].mean().abs().max() < 0.2  # no trend left in any day


def test_days_with_few_or_noisy_exposures_are_dropped(archive):
    helpers.write_harpsn(archive["root"] / "data", archive["flares"])
    raw = harpsn.read_series()
    first_day = np.floor(raw["jd"] - 0.5) == np.floor(raw["jd"].iloc[0] - 0.5)
    assert not harpsn.prepare(raw, min_points=first_day.sum() + 1)["good"].any()
    noisy = raw.copy()
    noisy.loc[first_day, "rv_ms"] += np.random.default_rng(0).normal(0.0, 5.0, first_day.sum())
    prepared = harpsn.prepare(noisy)
    assert not prepared.loc[first_day.to_numpy(), "good"].any() and prepared.loc[~first_day.to_numpy(), "good"].mean() > 0.95


def test_combine_weights_by_the_inverse_variance():
    def table(mean, error, flares):
        rows = [{"instrument": "x", "band": label, "flares": flares, "days": flares, "mean": mean, "mean_err": error,
                 "per_X1": mean, "per_X1_err": error, "rotation": np.nan, "rotation_err": np.nan} for label, _, _ in replication.BANDS]
        return pd.DataFrame(rows)

    both = replication.combine([table(0.10, 0.05, 100), table(-0.20, 0.10, 50)])
    row = both.iloc[0]
    assert row["instrument"] == "Both" and row["flares"] == 150
    assert row["mean"] == pytest.approx((0.10 / 0.05**2 - 0.20 / 0.10**2) / (1 / 0.05**2 + 1 / 0.10**2))
    assert row["mean_err"] == pytest.approx(1.0 / np.sqrt(1 / 0.05**2 + 1 / 0.10**2))
    assert row["limit_95"] == pytest.approx(abs(row["mean"]) + 1.645 * row["mean_err"])
    assert np.isnan(row["rotation"])  # nothing to combine


def test_early_window_needs_two_points_per_flare():
    from flinch import epoch

    cadence = 324.0 / 86400.0
    jd = 2460000.5 + np.arange(40) * cadence
    series = epoch.Series(jd, np.full(40, 0.3))
    # The window of the first flare starts a minute before an exposure and holds two; that of the second holds one.
    flares = pd.DataFrame({"jd_peak": [jd[20] + 59 * MINUTE, jd[0] + 51 * MINUTE], "peak_flux": [2.0e-4, 2.0e-4]})
    table = replication.early_window(replication.HARPSN, flares, series).set_index("band")
    assert table.loc["X", "flares"] == 1 and table.loc["X", "mean"] == pytest.approx(0.3)  # the second has one point only
    assert table.loc["M1-M4", "flares"] == 0


def test_flares_that_start_soon_after_the_peak_of_another_one_are_told_apart():
    start = 2460000.5 + np.array([0.0, 0.5, 1.0])
    flares = pd.DataFrame({"jd_start": start})
    # A flare peaks 30 min before the first, 50 min before the second, and the third has only its own peak after its start.
    peaks = [start[0] - 30 * MINUTE, start[1] - 50 * MINUTE, start[2] + 5 * MINUTE]
    assert replication.not_preceded(flares, peaks).tolist() == [False, True, True]
    assert replication.not_preceded(flares, peaks, margin_min=60.0).tolist() == [False, False, True]
