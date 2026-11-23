"""Robustness of the velocity result: estimators, background models, controls and sensitivity.

Every configuration is analysed in the same paired way: the velocity change of each flare
minus the mean change of its own controls. Errors come from a bootstrap that resamples whole
observing days, because flares of the same day share the sky, the instrument and the Sun.
"""
from __future__ import annotations

from math import erf, sqrt

import numpy as np
import pandas as pd

from . import epoch, goes, neid, pilot, quality
from .timeutil import MINUTE

V_EQUATOR_MS = 1983.0  # equatorial rotation velocity of the photosphere (Snodgrass & Ulrich 1990), sidereal
# The same as seen from the Earth, which moves around the Sun in the sense of the rotation: the
# line-of-sight velocity of the limb is smaller by the orbital angular velocity times the solar radius.
V_LIMB_FROM_EARTH_MS = 1845.0
MIN_PRE, MIN_SIGNAL, MIN_CONTROLS = 10, 3, 3
PRE = (-40.0, -5.0)  # baseline window, minutes from the flare start


def rotation_fraction(events: pd.DataFrame) -> np.ndarray:
    """Line-of-sight rotation velocity at the flare position, as a fraction of the equatorial one.

    West (receding) positive. Uses the differential rotation law with the sine of the latitude
    approximated by the height on the disc; NaN outside the disc.
    """
    x = events["x_norm"].where(events["r_norm"] < 1.05).to_numpy(dtype=float)
    y2 = np.clip(events["y_norm"].to_numpy(dtype=float), -1.0, 1.0) ** 2
    return x * (1.0 - 0.120 * y2 - 0.166 * y2**2)


def signal_window(events: pd.DataFrame, estimator: str) -> tuple[np.ndarray, np.ndarray]:
    """Limits (Julian dates) of the window in which the velocity change is measured."""
    start, peak = epoch.event_times(events)
    impulsive = events["jd_impulsive"].to_numpy(dtype=float)
    if estimator == "rise":  # the default of the pilot
        return start, peak + 2.0 * MINUTE
    if estimator == "impulsive":
        return impulsive - 3.0 * MINUTE, impulsive + 3.0 * MINUTE
    if estimator == "start":
        return start, start + 10.0 * MINUTE
    if estimator == "peak":
        return peak - 5.0 * MINUTE, peak + 5.0 * MINUTE
    raise ValueError(estimator)


def window_delta(
    events: pd.DataFrame,
    series: epoch.Series,
    estimator: str,
    cadence_s: float = 83.0,
    min_pre: int = MIN_PRE,
    min_signal: int = MIN_SIGNAL,
) -> np.ndarray:
    """Mean in the signal window minus mean in the pre-flare window (NaN when under-sampled).

    A window counts when it holds at least 70 % of the points expected at the cadence
    ``cadence_s`` of the instrument, and never fewer than ``min_pre`` or ``min_signal``.
    """
    start, _ = epoch.event_times(events)
    low, high = signal_window(events, estimator)
    n_pre, pre = series.window(start + PRE[0] * MINUTE, start + PRE[1] * MINUTE)
    n_signal, signal = series.window(low, high)
    expected = 0.7 * (high - low) * 86400.0 / cadence_s
    ok = (n_pre >= max(min_pre, 0.7 * (PRE[1] - PRE[0]) * 60.0 / cadence_s)) & (n_signal >= np.maximum(min_signal, expected))
    return np.where(ok, signal - pre, np.nan)


def local_delta(events: pd.DataFrame, jd: np.ndarray, rv: np.ndarray, order: int = 1) -> np.ndarray:
    """Velocity change against a background fitted locally on both sides of each event.

    A polynomial is fitted to the velocities from 60 to 10 minutes before the start and from 30
    to 90 minutes after the peak, leaving out the interval that the flare may affect; the
    change is the mean of velocity minus fit from the start to 2 minutes after the peak.
    """
    start, peak = epoch.event_times(events)
    out = np.full(len(events), np.nan)
    for k, (t0, t1) in enumerate(zip(start, peak)):
        before = (jd >= t0 - 60.0 * MINUTE) & (jd <= t0 - 10.0 * MINUTE)
        after = (jd >= t1 + 30.0 * MINUTE) & (jd <= t1 + 90.0 * MINUTE)
        during = (jd >= t0) & (jd <= t1 + 2.0 * MINUTE)
        if before.sum() >= 20 and after.sum() >= 20 and during.sum() >= MIN_SIGNAL:
            side = before | after
            hours = (jd - t0) * 24.0
            fit = np.polyfit(hours[side], rv[side], order)
            out[k] = float(np.mean(rv[during] - np.polyval(fit, hours[during])))
    return out


def same_day_controls(flares: pd.DataFrame, major_peaks_jd, margin_min: float = 45.0) -> pd.DataFrame:
    """Controls on the day of each flare, 2 and 3 hours earlier and later, free of major flares."""
    start, peak = epoch.event_times(flares)
    major = np.sort(np.asarray(major_peaks_jd, dtype=float))
    rows = []
    for shift_h in (-3.0, -2.0, 2.0, 3.0):
        shift = shift_h / 24.0
        quiet = np.searchsorted(major, peak + shift + margin_min * MINUTE, side="right") == np.searchsorted(
            major, start + shift - margin_min * MINUTE, side="left"
        )
        block = flares.loc[quiet, ["peak_flux", "x_norm", "y_norm", "r_norm", "goes_class"]].copy()
        block["parent"] = np.flatnonzero(quiet)
        block["jd_start"] = start[quiet] + shift
        block["jd_peak"] = peak[quiet] + shift
        block["jd_impulsive"] = flares["jd_impulsive"].to_numpy()[quiet] + shift
        rows.append(block)
    return pd.concat(rows, ignore_index=True)


def paired(flare_delta: np.ndarray, controls: pd.DataFrame, control_delta: np.ndarray) -> np.ndarray:
    """Change of each flare minus the mean change of its controls (NaN with fewer than three)."""
    table = pd.DataFrame({"parent": controls["parent"].to_numpy(), "delta": control_delta}).dropna()
    grouped = table.groupby("parent")["delta"].agg(["mean", "size"])
    reference = grouped["mean"].where(grouped["size"] >= MIN_CONTROLS).reindex(np.arange(len(flare_delta))).to_numpy()
    return flare_delta - reference


def region_groups(flares: pd.DataFrame, lon_deg: float = 10.0, lat_deg: float = 8.0, days: float = 14.0) -> np.ndarray:
    """Label of the active region of each flare, from positions alone.

    Two flares belong to the same region when they are within ``days`` of each other and within
    ``lon_deg`` in Carrington longitude and ``lat_deg`` in latitude; flares without heliographic
    coordinates (at the limb) are grouped with the flares of their day. Groups are closed under
    these links, so a region followed across the disc stays one group.
    """
    jd = flares["jd_peak"].to_numpy(dtype=float)
    lon = flares["car_lon"].to_numpy(dtype=float)
    lat = flares["lat"].to_numpy(dtype=float)
    day = np.floor(jd - 0.5)
    label = np.arange(len(flares))

    def find(i):
        while label[i] != i:
            label[i] = label[label[i]]
            i = label[i]
        return i

    for i in range(len(flares)):
        for j in range(i + 1, len(flares)):
            located = np.isfinite(lon[i]) and np.isfinite(lon[j]) and np.isfinite(lat[i]) and np.isfinite(lat[j])
            if located:
                apart = abs(lon[i] - lon[j]) % 360.0
                same = abs(jd[i] - jd[j]) < days and min(apart, 360.0 - apart) < lon_deg and abs(lat[i] - lat[j]) < lat_deg
            else:
                same = day[i] == day[j]
            if same:
                label[find(i)] = find(j)
    return np.array([find(i) for i in range(len(flares))])


def day_bootstrap(values: dict[str, np.ndarray], days: np.ndarray, statistics: dict, draws: int = 4000, seed: int = 0) -> dict:
    """Value and standard error of each statistic, resampling observing days with replacement."""
    rng = np.random.default_rng(seed)
    unique, inverse = np.unique(days, return_inverse=True)
    members = [np.flatnonzero(inverse == k) for k in range(len(unique))]
    out = {name: [function(values)] for name, function in statistics.items()}
    for _ in range(draws):
        rows = np.concatenate([members[k] for k in rng.integers(len(unique), size=len(unique))])
        resampled = {key: array[rows] for key, array in values.items()}
        for name, function in statistics.items():
            out[name].append(function(resampled))
    return {name: (results[0], float(np.nanstd(results[1:], ddof=1))) for name, results in out.items()}


def amplitude(delta: np.ndarray, weight: np.ndarray) -> float:
    keep = np.isfinite(delta) & np.isfinite(weight)
    norm = np.sum(weight[keep] ** 2)
    return float(np.sum(weight[keep] * delta[keep]) / norm) if norm > 0 else np.nan


STATISTICS = {
    "mean": lambda v: float(np.nanmean(v["d"])),
    "per_X1": lambda v: amplitude(v["d"], v["flux"]),
    "rotation": lambda v: amplitude(v["d"], v["flux"] * v["rot"]),
}


def analyse(flares: pd.DataFrame, d: np.ndarray, label: str, seed: int = 0, by_region: bool = False) -> dict:
    """One row of the robustness table for the paired changes ``d``.

    The bootstrap resamples observing days, or active regions with ``by_region`` (the column
    ``days`` then counts regions).
    """
    keep = np.isfinite(d)
    if keep.sum() < 2:  # nothing to resample (for instance, a sample without X-class flares)
        row = {"configuration": label, "flares": int(keep.sum()), "days": int(keep.sum())}
        for name in STATISTICS:
            row[name], row[f"{name}_err"] = np.nan, np.nan
        return row
    values = {"d": d[keep], "flux": pilot.flux_weight(flares)[keep], "rot": rotation_fraction(flares)[keep]}
    days = np.floor(flares["jd_peak"].to_numpy()[keep] - 0.5)
    if by_region:
        days = region_groups(flares)[keep]
    result = day_bootstrap(values, days, STATISTICS, seed=seed)
    row = {"configuration": label, "flares": int(keep.sum()), "days": int(len(np.unique(days)))}
    for name, (value, error) in result.items():
        row[name], row[f"{name}_err"] = value, error
    return row


def permutation_p(d: np.ndarray, flux: np.ndarray, rot: np.ndarray, draws: int = 10000, seed: int = 0) -> float:
    """Two-sided probability of a rotation term this large when positions are shuffled among flares."""
    rng = np.random.default_rng(seed)
    keep = np.isfinite(d) & np.isfinite(rot)
    d, flux, rot = d[keep], flux[keep], rot[keep]
    observed = abs(amplitude(d, flux * rot))
    shuffled = np.array([abs(amplitude(d, flux * rng.permutation(rot))) for _ in range(draws)])
    return float(np.mean(shuffled >= observed))


def detection_probability(signal: float, error: float) -> float:
    """Probability that a signal is detected at 95 % confidence (one-sided) given its error.

    ``signal`` is the shift as the method measures it back, that is, the true shift times the
    fraction recovered.
    """
    return 0.5 * (1.0 + erf((signal / error - 1.645) / sqrt(2.0)))


def recovered_fraction(fractions, errors) -> float:
    """Fraction of a common shift measured back by instruments combined with the inverse square of their errors."""
    weights = 1.0 / np.asarray(errors, dtype=float) ** 2
    return float(np.sum(weights * np.asarray(fractions, dtype=float)) / np.sum(weights))


def run(seed: int = 0) -> dict:
    raw = neid.read_solar_table()
    all_flares = goes.load_flares()
    sample = pilot.major_flare_sample(all_flares, raw["obsjd"].to_numpy())
    sample = goes.add_impulsive_time(sample)
    major = sample["jd_peak"].to_numpy()

    prepared = {order: quality.prepare(raw, order=order) for order in (1, 2, 3)}

    def series_of(order):
        good = prepared[order][prepared[order]["good"]]
        return epoch.Series(good["jd"], good["res"])

    base = series_of(2)
    # The sample is fixed by the default estimator, so that every row compares the same flares
    # wherever its own windows allow.
    flares = sample[np.isfinite(window_delta(sample, base, "rise"))].reset_index(drop=True)
    other_day = epoch.draw_controls(flares, major, seed=seed)
    other_day["jd_impulsive"] = flares["jd_impulsive"].to_numpy()[other_day["parent"]] + other_day["shift_days"]
    same_day = same_day_controls(flares, major)

    rows = []
    default = paired(window_delta(flares, base, "rise"), other_day, window_delta(other_day, base, "rise"))
    rows.append(analyse(flares, default, "Default: day polynomial of degree 2, start to peak + 2 min, controls on other days", seed))
    for order in (1, 3):
        s = series_of(order)
        d = paired(window_delta(flares, s, "rise"), other_day, window_delta(other_day, s, "rise"))
        rows.append(analyse(flares, d, f"Day polynomial of degree {order}", seed))
    for estimator, text in (
        ("impulsive", "Window: 3 min either side of the steepest X-ray rise"),
        ("start", "Window: first 10 min from the start"),
        ("peak", "Window: 5 min either side of the X-ray peak"),
    ):
        d = paired(window_delta(flares, base, estimator), other_day, window_delta(other_day, base, estimator))
        rows.append(analyse(flares, d, text, seed))
    good = prepared[2][prepared[2]["good"]]
    jd, rv = good["jd"].to_numpy(), good["rv_ms"].to_numpy()
    d = paired(local_delta(flares, jd, rv), other_day, local_delta(other_day, jd, rv))
    rows.append(analyse(flares, d, "Background: straight line fitted locally on both sides", seed))
    d = paired(window_delta(flares, base, "rise"), same_day, window_delta(same_day, base, "rise"))
    rows.append(analyse(flares, d, "Controls: same day, 2 and 3 hours away", seed))
    rows.append(analyse(flares, default, "Default, bootstrap over active regions instead of days", seed, by_region=True))
    x_class = (flares["peak_flux"] >= 1.0e-4).to_numpy()
    rows.append(analyse(flares[x_class].reset_index(drop=True), default[x_class], "Default, X-class flares only", seed))
    table = pd.DataFrame(rows)

    flux, rot = pilot.flux_weight(flares), rotation_fraction(flares)
    p_rotation = permutation_p(default, flux, rot, seed=seed)

    # Injection and recovery through the whole chain, at one control epoch per day.
    control_day = np.floor(other_day["jd_peak"] - 0.5)
    measured = np.isfinite(window_delta(other_day, base, "rise"))
    isolated = other_day[measured].groupby(control_day[measured]).sample(1, random_state=seed)
    reference = window_delta(isolated, base, "rise")
    mean_error = float(table.loc[0, "mean_err"])
    injections = []
    for amplitude_ms in (0.05, 0.10, 0.20, 0.50):
        injected = quality.prepare(pilot.inject(raw, isolated, amplitude_ms))
        kept = injected[injected["good"]]
        recovered = window_delta(isolated, epoch.Series(kept["jd"], kept["res"]), "rise") - reference
        efficiency = float(np.nanmean(recovered)) / amplitude_ms
        injections.append(
            {
                "injected_ms": amplitude_ms,
                "recovered_ms": float(np.nanmean(recovered)),
                "efficiency": efficiency,
                "detection_probability": detection_probability(efficiency * amplitude_ms, mean_error),
            }
        )
    return {
        "table": table,
        "injections": pd.DataFrame(injections),
        "numbers": {
            "flares": len(flares),
            "flares_per_day_max": int(pd.Series(np.floor(flares["jd_peak"] - 0.5)).value_counts().max()),
            "rotation_permutation_p": p_rotation,
            "optical_contrast_limit_per_X1": (abs(table.loc[0, "rotation"]) + 1.645 * table.loc[0, "rotation_err"]) / V_LIMB_FROM_EARTH_MS,
        },
    }
