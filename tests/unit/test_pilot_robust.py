"""Unit tests of the pieces of the pilot and of the robustness analysis."""
import numpy as np
import pandas as pd
import pytest

from flinch import epoch, pilot, robust
from flinch.timeutil import MINUTE

T0 = 2460000.25


def events(n=4, start=T0 + 0.1):
    starts = start + np.arange(n) * 1.0
    return pd.DataFrame(
        {
            "jd_start": starts,
            "jd_peak": starts + 10 * MINUTE,
            "jd_impulsive": starts + 6 * MINUTE,
            "peak_flux": [2e-5, 1e-4, 2e-4, 5e-5][:n],
            "goes_class": ["M2.0", "X1.0", "X2.0", "M5.0"][:n],
            "x_norm": [0.5, -0.5, 0.0, 0.9][:n],
            "y_norm": [0.0, 0.0, 1.0, 0.9][:n],
            "r_norm": [0.5, 0.5, 1.0, 1.27][:n],
        }
    )


def series_with_box(table, amplitude=1.0, days=6):
    """Zero residuals sampled every 83 s for some days, plus a box in the default signal window of each event."""
    jd = np.concatenate([T0 + d + np.arange(0.0, 6 * 3600.0, 83.0) / 86400.0 for d in range(days)])
    values = np.zeros(len(jd))
    for row in table.itertuples():
        values[(jd >= row.jd_start) & (jd <= row.jd_peak + 2 * MINUTE)] = amplitude
    return jd, values


def test_weights():
    table = events()
    assert pilot.flux_weight(table) == pytest.approx([0.2, 1.0, 2.0, 0.5])
    rotation = pilot.rotation_weight(table)
    assert rotation[:3] == pytest.approx([0.1, -0.5, 0.0])
    assert np.isnan(rotation[3])  # outside the disc


def test_rotation_fraction_follows_differential_rotation():
    fraction = robust.rotation_fraction(events())
    assert fraction[0] == pytest.approx(0.5) and fraction[1] == pytest.approx(-0.5)
    assert fraction[2] == pytest.approx(0.0)
    assert np.isnan(fraction[3])
    pole = pd.DataFrame({"x_norm": [0.1], "y_norm": [1.0], "r_norm": [1.0]})
    assert robust.rotation_fraction(pole)[0] == pytest.approx(0.1 * (1 - 0.120 - 0.166))


def test_signal_windows():
    table = events(1)
    start, peak, impulsive = table.loc[0, ["jd_start", "jd_peak", "jd_impulsive"]]
    assert robust.signal_window(table, "rise") == (pytest.approx([start]), pytest.approx([peak + 2 * MINUTE]))
    low, high = robust.signal_window(table, "impulsive")
    assert (low[0], high[0]) == (pytest.approx(impulsive - 3 * MINUTE), pytest.approx(impulsive + 3 * MINUTE))
    low, high = robust.signal_window(table, "start")
    assert high[0] - low[0] == pytest.approx(10 * MINUTE)
    low, high = robust.signal_window(table, "peak")
    assert (low[0], high[0]) == (pytest.approx(peak - 5 * MINUTE), pytest.approx(peak + 5 * MINUTE))
    with pytest.raises(ValueError):
        robust.signal_window(table, "nonsense")


def test_window_delta_and_local_delta_recover_a_box():
    table = events()
    jd, values = series_with_box(table, amplitude=1.5)
    delta = robust.window_delta(table, epoch.Series(jd, values), "rise")
    assert delta == pytest.approx([1.5, 1.5, 1.5, 1.5])
    # an event with no data around it is not measured
    far = table.assign(jd_start=table["jd_start"] + 50.0, jd_peak=table["jd_peak"] + 50.0)
    assert np.isnan(robust.window_delta(far, epoch.Series(jd, values), "rise")).all()
    # a linear trend on top does not bias the locally fitted background
    trend = values - 645.0 + 30.0 * (jd - T0)
    assert robust.local_delta(table, jd, trend) == pytest.approx([1.5] * 4, abs=1e-6)


def test_same_day_controls_avoid_major_flares():
    table = events(2)
    major = [table.loc[0, "jd_peak"], table.loc[1, "jd_peak"], table.loc[0, "jd_peak"] + 2.0 / 24.0]
    controls = robust.same_day_controls(table, major)
    assert len(controls) == 7  # four shifts per flare, minus the one that lands on a flare
    first = controls[controls["parent"] == 0]
    assert sorted(np.round((first["jd_peak"] - table.loc[0, "jd_peak"]) * 24.0)) == [-3.0, -2.0, 3.0]
    assert np.allclose(controls["jd_impulsive"] - controls["jd_start"], 6 * MINUTE)


def test_paired_subtracts_the_mean_of_enough_controls():
    controls = pd.DataFrame({"parent": [0, 0, 0, 1, 1, 2, 2, 2]})
    control_delta = np.array([0.1, 0.2, 0.3, 0.5, 0.5, np.nan, 0.0, 0.0])
    out = robust.paired(np.array([1.0, 1.0, 1.0]), controls, control_delta)
    assert out[0] == pytest.approx(0.8)
    assert np.isnan(out[1]) and np.isnan(out[2])  # fewer than three valid controls


def test_amplitude_and_day_bootstrap():
    rng = np.random.default_rng(0)
    flux = rng.uniform(0.2, 2.0, 400)
    d = 0.3 * flux + rng.normal(0.0, 0.5, 400)
    assert robust.amplitude(d, flux) == pytest.approx(0.3, abs=0.06)
    values = {"d": d, "flux": flux, "rot": np.zeros(400)}
    statistics = {"mean": robust.STATISTICS["mean"], "per_X1": robust.STATISTICS["per_X1"]}
    independent = robust.day_bootstrap(values, np.arange(400), statistics, draws=300)
    assert independent["mean"][0] == pytest.approx(d.mean())
    assert independent["mean"][1] == pytest.approx(d.std() / 20.0, rel=0.25)
    # the same numbers in four big clusters: far fewer independent pieces, a larger error
    clustered = robust.day_bootstrap({k: np.sort(v) if k == "d" else v for k, v in values.items()}, np.arange(400) // 100, statistics, draws=300)
    assert clustered["mean"][1] > 3 * independent["mean"][1]


def test_analyse_handles_a_sample_that_is_too_small():
    table = events(1)
    row = robust.analyse(table, np.array([0.2]), "one flare")
    assert row["flares"] == 1 and np.isnan(row["mean"]) and np.isnan(row["rotation_err"])


def test_permutation_and_detection_probability():
    rng = np.random.default_rng(1)
    rot = rng.uniform(-1, 1, 200)
    flux = np.ones(200)
    signal = 0.5 * rot + rng.normal(0.0, 0.2, 200)
    assert robust.permutation_p(signal, flux, rot, draws=500) < 0.01
    assert robust.permutation_p(rng.normal(0.0, 0.2, 200), flux, rot, draws=500) > 0.01
    assert robust.detection_probability(1.645, 1.0) == pytest.approx(0.5)
    assert robust.detection_probability(0.0, 1.0) == pytest.approx(0.05, abs=1e-3)
    assert robust.detection_probability(5.0, 1.0) > 0.999


def test_the_fraction_recovered_by_two_instruments_is_weighted_by_their_errors():
    assert robust.recovered_fraction([0.9, 0.9], [1.0, 3.0]) == pytest.approx(0.9)
    # an instrument with half the error weighs four times as much
    assert robust.recovered_fraction([1.0, 0.5], [1.0, 2.0]) == pytest.approx(0.9)


def test_inject_adds_the_box_only_inside_the_signal_window():
    table = events(2)
    jd = T0 + 0.1 + np.arange(-3600.0, 3600.0, 83.0) / 86400.0
    raw = pd.DataFrame({"obsjd": jd - 27.5 / 86400.0, "rv_ms": 0.0})
    out = pilot.inject(raw, table.iloc[[0]], 2.0)
    inside = (jd >= table.loc[0, "jd_start"]) & (jd <= table.loc[0, "jd_peak"] + 2 * MINUTE)
    assert np.allclose(out.loc[inside, "rv_ms"], 2.0) and np.allclose(out.loc[~inside, "rv_ms"], 0.0)
    assert raw["rv_ms"].abs().sum() == 0.0  # the input is not modified


def test_summarize_matched_null_and_profiles():
    rng = np.random.default_rng(2)
    flares = events().assign(delta=[0.2, 0.4, 0.6, 0.0])
    controls = pd.DataFrame(
        {
            "parent": np.repeat(np.arange(4), 5),
            "goes_class": np.repeat(flares["goes_class"].to_numpy(), 5),
            "peak_flux": np.repeat(flares["peak_flux"].to_numpy(), 5),
            "delta": rng.normal(0.0, 0.1, 20),
        }
    )
    summary = pilot.summarize(flares, controls).set_index("band")
    assert summary.loc["all", "n_flares"] == 4 and summary.loc["all", "n_controls"] == 20
    assert summary.loc["X", "flare_mean"] == pytest.approx(0.5)
    assert summary.loc["all", "difference"] == pytest.approx(0.3 - controls["delta"].mean())
    null = pilot.matched_null(controls, lambda e: float(e["delta"].mean()), draws=50, seed=3)
    again = pilot.matched_null(controls, lambda e: float(e["delta"].mean()), draws=50, seed=3)
    assert len(null) == 50 and np.array_equal(null, again)
    jd, values = series_with_box(flares, amplitude=1.0)
    profile = pilot.stacked_profile(flares, epoch.Series(jd, values), "all", "flares")
    assert len(profile) == len(pilot.PROFILE_EDGES_MIN) - 1
    during = profile[(profile["minutes"] > -10) & (profile["minutes"] < 0)]
    assert during["mean"].to_numpy() == pytest.approx(1.0)
    assert profile.loc[profile["minutes"] > 20, "mean"].abs().max() == pytest.approx(0.0)


def test_major_flare_sample_keeps_m_and_x_inside_the_observations():
    flares = pd.DataFrame({"jd_peak": [1.0, 5.0, 6.0, 20.0], "goes_class": ["M1.0", "C9.0", "X2.0", "X1.0"]})
    sample = pilot.major_flare_sample(flares, np.array([2.0, 10.0]))
    assert list(sample["goes_class"]) == ["X2.0"]
