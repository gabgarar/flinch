"""The same measurement with two instruments: NEID and HARPS-N.

The velocity change of each flare, paired with its controls, is measured with one code for
both instruments. They observe at different longitudes, so their flares are different: the
second instrument is an independent repetition of the measurement, not a second look at the
same events.
"""
from __future__ import annotations

import inspect
from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import epoch, goes, harpsn, neid, pilot, quality, robust
from .timeutil import MINUTE

# Class bands of the summary: label, lowest peak flux and (exclusive) highest, in W m^-2.
BANDS = (
    ("M and X", 1.0e-5, np.inf),
    ("M", 1.0e-5, 1.0e-4),
    ("M1-M4", 1.0e-5, 5.0e-5),
    ("M5-M9", 5.0e-5, 1.0e-4),
    ("X", 1.0e-4, np.inf),
)
PROFILE_EDGES_MIN = np.arange(-60.0, 90.1, 10.0)
ISOLATION_MIN = 45.0  # the margin that the controls keep from any M or X flare
ISOLATED = "no other M or X flare in the 45 min before"
PROFILE_SUBSETS = ("M and X", "X")
EARLY_WINDOW_MIN = (-60.0, -50.0)  # where the X-class flares of NEID show an excess


@dataclass(frozen=True)
class Instrument:
    """Sampling of an instrument: cadence and the fewest points accepted before and during a flare."""

    name: str
    cadence_s: float
    min_pre: int
    min_signal: int


NEID = Instrument("NEID", 83.0, robust.MIN_PRE, robust.MIN_SIGNAL)
HARPSN = Instrument("HARPS-N", harpsn.CADENCE_S, 3, 1)


def raw_table(instrument: Instrument) -> pd.DataFrame:
    """Velocities of the instrument as published."""
    if instrument.name == "NEID":
        return neid.read_solar_table()
    return harpsn.read_series(harpsn.download_series())


def _preparer(instrument: Instrument):
    return quality.prepare if instrument.name == "NEID" else harpsn.prepare


def prepare(instrument: Instrument, raw: pd.DataFrame, **choices) -> pd.DataFrame:
    """Quality cuts and daily trend of the instrument; ``choices`` replace the defaults of its cuts."""
    return _preparer(instrument)(raw, **choices)


def prepared_table(instrument: Instrument) -> pd.DataFrame:
    """Velocities of the instrument after its quality cuts and daily trend."""
    return prepare(instrument, raw_table(instrument))


def measure(instrument: Instrument, prepared: pd.DataFrame, all_flares: pd.DataFrame, seed: int = 0) -> dict:
    """Flares with complete windows, their controls on other days and the paired changes.

    ``flares`` gains ``delta`` (signal window minus baseline) and ``d`` (``delta`` minus the
    mean of its controls; NaN with fewer than three). ``controls`` gains ``delta``.
    """
    good = prepared[prepared["good"]]
    series = epoch.Series(good["jd"], good["res"])
    sample = pilot.major_flare_sample(all_flares, prepared["obsjd"].to_numpy())
    if "jd_impulsive" not in sample:
        sample = sample.assign(jd_impulsive=np.nan)  # only the default window is used here

    def delta(events):
        return robust.window_delta(events, series, "rise", instrument.cadence_s, instrument.min_pre, instrument.min_signal)

    flares = sample[np.isfinite(delta(sample))].reset_index(drop=True)
    controls = epoch.draw_controls(flares, sample["jd_peak"].to_numpy(), seed=seed)
    controls["jd_impulsive"] = np.nan
    controls["delta"] = delta(controls)
    flares["delta"] = delta(flares)
    flares["d"] = robust.paired(flares["delta"].to_numpy(), controls, controls["delta"].to_numpy())
    return {
        "flares": flares,
        "controls": controls[np.isfinite(controls["delta"])].reset_index(drop=True),
        "series": series,
        "sample": sample,
    }


def injection_efficiency(instrument: Instrument, raw: pd.DataFrame, controls: pd.DataFrame, amplitude_ms: float = 0.10, seed: int = 0) -> float:
    """Fraction of an injected box that the whole chain gives back.

    The box is added to the published velocities in the signal window of one control epoch per
    day, and the quality cuts, the daily trend and the windows are run again.
    """
    day = np.floor(controls["jd_peak"] - 0.5)
    isolated = controls.groupby(day).sample(1, random_state=seed).reset_index(drop=True)
    injected = prepare(instrument, pilot.inject(raw, isolated, amplitude_ms))
    kept = injected[injected["good"]]
    series = epoch.Series(kept["jd"], kept["res"])
    recovered = robust.window_delta(isolated, series, "rise", instrument.cadence_s, instrument.min_pre, instrument.min_signal)
    return float(np.nanmean(recovered - isolated["delta"].to_numpy())) / amplitude_ms


def in_band(events: pd.DataFrame, low: float, high: float) -> np.ndarray:
    flux = events["peak_flux"].to_numpy(dtype=float)
    return (flux >= low) & (flux < high)


def band_table(instrument: Instrument, flares: pd.DataFrame, controls: pd.DataFrame, seed: int = 0) -> pd.DataFrame:
    """Mean paired change, change per X1 flare and rotation term of each class band.

    Errors come from the bootstrap over observing days. ``limit_95`` is the absolute value of
    the mean plus 1.645 errors: the size that the mean response would exceed with a
    probability of 5 %. The scatter of the changes of flares and controls is given to compare.
    """
    rows = []
    for label, low, high in BANDS:
        chosen = in_band(flares, low, high) & np.isfinite(flares["d"].to_numpy())
        subset = flares[chosen].reset_index(drop=True)
        row = robust.analyse(subset, subset["d"].to_numpy(), label, seed)
        control_delta = controls.loc[in_band(controls, low, high), "delta"]
        rows.append(
            {
                "instrument": instrument.name,
                "band": label,
                "flares": row["flares"],
                "days": row["days"],
                "mean": row["mean"],
                "mean_err": row["mean_err"],
                "limit_95": abs(row["mean"]) + 1.645 * row["mean_err"],
                "per_X1": row["per_X1"],
                "per_X1_err": row["per_X1_err"],
                "rotation": row["rotation"],
                "rotation_err": row["rotation_err"],
                "flare_std": float(subset["delta"].std(ddof=1)) if len(subset) > 1 else np.nan,
                "control_std": float(control_delta.std(ddof=1)) if len(control_delta) > 1 else np.nan,
                "controls": len(control_delta),
            }
        )
    return pd.DataFrame(rows)


def combine(tables: list[pd.DataFrame]) -> pd.DataFrame:
    """Both instruments together: each quantity weighted by the inverse of its variance."""
    rows = []
    for label, _, _ in BANDS:
        parts = [table[table["band"] == label].iloc[0] for table in tables]
        row = {"instrument": "Both", "band": label, "flares": int(sum(p["flares"] for p in parts)), "days": int(sum(p["days"] for p in parts))}
        for name in ("mean", "per_X1", "rotation"):
            value = np.array([p[name] for p in parts], dtype=float)
            error = np.array([p[f"{name}_err"] for p in parts], dtype=float)
            usable = np.isfinite(value) & np.isfinite(error) & (error > 0)
            weight = 1.0 / error[usable] ** 2
            row[name] = float(np.sum(weight * value[usable]) / np.sum(weight)) if usable.any() else np.nan
            row[f"{name}_err"] = float(1.0 / np.sqrt(np.sum(weight))) if usable.any() else np.nan
        row["limit_95"] = abs(row["mean"]) + 1.645 * row["mean_err"]
        rows.append(row)
    return pd.DataFrame(rows)


def stacked_profiles(instrument: Instrument, flares: pd.DataFrame, controls: pd.DataFrame, series: epoch.Series) -> pd.DataFrame:
    """Mean velocity around the peak, in bins of 10 min, for flares and controls of each subset."""
    centres = 0.5 * (PROFILE_EDGES_MIN[:-1] + PROFILE_EDGES_MIN[1:])
    rows = []
    for subset in PROFILE_SUBSETS:
        low, high = next((lo, hi) for label, lo, hi in BANDS if label == subset)
        for sample, events in (("flares", flares), ("controls", controls)):
            chosen = events[in_band(events, low, high)]
            matrix = epoch.profiles(chosen, series, PROFILE_EDGES_MIN)
            count = np.sum(np.isfinite(matrix), axis=0)
            with np.errstate(invalid="ignore"):
                mean = np.nanmean(matrix, axis=0)
                sem = np.nanstd(matrix, axis=0, ddof=1) / np.sqrt(np.maximum(count, 1))
            rows.append(
                pd.DataFrame(
                    {"instrument": instrument.name, "subset": subset, "sample": sample, "events": len(chosen), "minutes": centres, "mean": mean, "sem": sem, "n": count}
                )
            )
    return pd.concat(rows, ignore_index=True)


def early_window(instrument: Instrument, flares: pd.DataFrame, series: epoch.Series, window_min=EARLY_WINDOW_MIN) -> pd.DataFrame:
    """Mean residual velocity of each class band in a window before the peak (at least two points per flare)."""
    peak = flares["jd_peak"].to_numpy()
    count, value = series.window(peak + window_min[0] * MINUTE, peak + window_min[1] * MINUTE - 1.0e-9)
    value = np.where(count >= 2, value, np.nan)
    rows = []
    for label, low, high in BANDS:
        chosen = value[in_band(flares, low, high) & np.isfinite(value)]
        rows.append(
            {
                "instrument": instrument.name,
                "band": label,
                "flares": len(chosen),
                "mean": float(chosen.mean()) if len(chosen) else np.nan,
                "sem": float(chosen.std(ddof=1) / np.sqrt(len(chosen))) if len(chosen) > 1 else np.nan,
                "positive": int((chosen > 0).sum()),
            }
        )
    return pd.DataFrame(rows)


def not_preceded(flares: pd.DataFrame, major_peaks_jd, margin_min: float = ISOLATION_MIN) -> np.ndarray:
    """True for the flares with no other M or X flare peaking in the ``margin_min`` minutes before their start."""
    peaks = np.sort(np.asarray(major_peaks_jd, dtype=float))
    start = flares["jd_start"].to_numpy(dtype=float)
    return np.searchsorted(peaks, start - 1.0e-9) == np.searchsorted(peaks, start - margin_min * MINUTE)


def cleaning_variants(instrument: Instrument) -> list[tuple[str, dict]]:
    """Other values for the cuts that drop whole days and, for HARPS-N, for its quality flag.

    The largest scatter of a day (1, 2 and 3 m/s instead of 1.5), the fewest good points of a
    day (half and twice the default) and, for HARPS-N, the 0.9 that its release recommends
    for the quality flag instead of 0.99.
    """
    points = inspect.signature(_preparer(instrument)).parameters["min_points"].default
    variants: list[tuple[str, dict]] = [("default", {})]
    variants += [(f"day scatter below {limit:g} m/s", {"max_day_sigma": limit}) for limit in (1.0, 2.0, 3.0)]
    variants += [(f"at least {number} points per day", {"min_points": number}) for number in (points // 2, points * 2)]
    if instrument.name == "HARPS-N":
        variants.append(("quality flag above 0.9", {"min_quality": 0.9}))
    return variants


def cleaning_table(seed: int = 0) -> pd.DataFrame:
    """The velocity change of each instrument under other cleaning thresholds (see ``cleaning_variants``).

    With the default cleaning there is one more row, ``ISOLATED``: the same flares without
    those that start less than ``ISOLATION_MIN`` minutes after the peak of another M or X
    flare, whose window before the start is not free of flares.
    """
    all_flares = goes.load_flares()
    rows = []
    for instrument in (NEID, HARPSN):
        raw = raw_table(instrument)
        for label, choices in cleaning_variants(instrument):
            prepared = prepare(instrument, raw, **choices)
            good = prepared[prepared["good"]]
            out = measure(instrument, prepared, all_flares, seed)
            subsets = [(label, out["flares"])]
            if not choices:
                alone = not_preceded(out["flares"], out["sample"]["jd_peak"])
                subsets.append((ISOLATED, out["flares"][alone].reset_index(drop=True)))
            for variant, flares in subsets:
                table = band_table(instrument, flares, out["controls"], seed).set_index("band")
                for band in ("M and X", "X"):
                    row = table.loc[band]
                    rows.append(
                        {
                            "instrument": instrument.name,
                            "variant": variant,
                            "band": band,
                            "good": len(good),
                            "days": int(good["day"].nunique()),
                            "flares": int(row["flares"]),
                            "mean": row["mean"],
                            "mean_err": row["mean_err"],
                            "rotation": row["rotation"],
                            "rotation_err": row["rotation_err"],
                        }
                    )
    return pd.DataFrame(rows)


def run(seed: int = 0) -> dict:
    """The velocity response measured with NEID and with HARPS-N, and both combined."""
    all_flares = goes.load_flares()
    tables, profiles, early, events, numbers = [], [], [], [], {}
    for instrument in (NEID, HARPSN):
        raw = raw_table(instrument)
        prepared = prepare(instrument, raw)
        out = measure(instrument, prepared, all_flares, seed)
        flares, controls = out["flares"], out["controls"]
        tables.append(band_table(instrument, flares, controls, seed))
        profiles.append(stacked_profiles(instrument, flares, controls, out["series"]))
        # Every flare with data in the early window, whether or not its other windows are complete.
        early.append(early_window(instrument, out["sample"], out["series"]))
        events.append(flares.assign(instrument=instrument.name, sample="flare"))
        events.append(controls.assign(instrument=instrument.name, sample="control"))
        good = prepared[prepared["good"]]
        numbers[instrument.name] = {
            "observations": len(prepared),
            "good": len(good),
            "days": int(good["day"].nunique()),
            "point_sigma_ms": quality.robust_sigma(good["res"].to_numpy()),
            "first": float(prepared["obsjd"].min()),
            "last": float(prepared["obsjd"].max()),
            "flares_in_era": len(out["sample"]),
            "flares_measured": len(flares),
            "injection_efficiency": injection_efficiency(instrument, raw, controls, seed=seed),
            "flares_paired": int(np.isfinite(flares["d"]).sum()),
            "controls": len(controls),
        }
    shared = pd.merge_asof(
        events[0][["jd_peak"]].sort_values("jd_peak"), events[2][["jd_peak"]].assign(other=1).sort_values("jd_peak"),
        on="jd_peak", tolerance=1.0 * MINUTE, direction="nearest",
    )
    numbers["flares_in_both"] = int(shared["other"].notna().sum())
    columns = ["instrument", "sample", "jd_start", "jd_peak", "goes_class", "peak_flux", "x_norm", "y_norm", "r_norm", "delta", "d"]
    table = pd.concat([*tables, combine(tables)], ignore_index=True)
    both = table[(table["instrument"] == "Both") & (table["band"] == "M and X")].iloc[0]
    numbers["optical_contrast_limit_per_X1"] = float((abs(both["rotation"]) + 1.645 * both["rotation_err"]) / robust.V_LIMB_FROM_EARTH_MS)
    # A shift common to all flares is measured back as the weighted mean of what each instrument recovers.
    alone = table[(table["band"] == "M and X") & (table["instrument"] != "Both")]
    recovered = robust.recovered_fraction([numbers[name]["injection_efficiency"] for name in alone["instrument"]], alone["mean_err"])
    numbers["detection_probability_10cm"] = robust.detection_probability(recovered * 0.10, float(both["mean_err"]))
    return {
        "table": table,
        "profiles": pd.concat(profiles, ignore_index=True),
        "early_window": pd.concat(early, ignore_index=True),
        "events": pd.concat(events, ignore_index=True).reindex(columns=columns),
        "numbers": numbers,
    }
