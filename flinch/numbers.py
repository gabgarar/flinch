"""Numbers of the text that describe the data and the flare sample.

The tables of the other commands hold the measurements. This one holds the counts and the
descriptive figures quoted in the text: how many velocities and days each instrument has, what
the cuts remove, whether the flares measured are a fair sample of all of them, how often the
Sun flares and for how long.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import coverage, goes, quality, replication
from .timeutil import MINUTE, jd_to_datetime

X1_FLUX = 1.0e-4  # W m^-2
# Quantities compared between the flares measured and all the flares of the era of an instrument.
KS_COLUMNS = (("peak_flux", "class"), ("x_norm", "position_x"), ("y_norm", "position_y"), ("r_norm", "distance_from_centre"))
# The flare of 6 September 2017 that Pietrow et al. (2024) followed with HARPS-N (peak at 12:02 UT).
PIETROW_FLARE_JD = 2458003.0014


def ks_p(a, b) -> float:
    """Two-sample Kolmogorov-Smirnov probability that ``a`` and ``b`` come from one distribution."""
    from scipy import stats  # optional dependency ("analysis" extra)

    a, b = pd.Series(a).dropna(), pd.Series(b).dropna()
    return float(stats.ks_2samp(a, b).pvalue)


def durations(flares: pd.DataFrame) -> np.ndarray:
    """Length of each flare in days, from its start to its end in the GOES list.

    The list gives no end for a flare when another one begins before it is over (185 of the
    2122 M and X flares of the NEID era, 111 of them in 2024). Such a flare is counted up to its
    peak, since the rest of its decay belongs to the time of the next one.
    """
    end = flares["jd_end"].fillna(flares["jd_peak"])
    return (end - flares["jd_start"]).to_numpy(dtype=float)


def flare_statistics(sample: pd.DataFrame, first_jd: float, last_jd: float) -> dict:
    """Rate of M and X flares and fraction of the time spent in them, between two dates.

    Also for the calendar year with most flares, where the time is divided by the length of
    that year.
    """
    span = last_jd - first_jd
    is_x = (sample["peak_flux"] >= X1_FLUX).to_numpy()
    length = durations(sample)
    year = np.asarray(jd_to_datetime(sample["jd_peak"]).year)
    busiest = int(pd.Series(year).value_counts().idxmax())
    in_year = year == busiest
    year_days = 366.0 if busiest % 4 == 0 else 365.0
    return {
        "span_years": span / 365.25,
        "flares": len(sample),
        "flares_x": int(is_x.sum()),
        "flares_per_year": len(sample) / (span / 365.25),
        "flares_x_per_year": is_x.sum() / (span / 365.25),
        "flares_without_end": int(sample["jd_end"].isna().sum()),
        "median_duration_min": float(np.median(length) / MINUTE),
        "time_in_flare_percent": 100.0 * length.sum() / span,
        "time_in_x_flare_percent": 100.0 * length[is_x].sum() / span,
        "busiest_year": busiest,
        "busiest_year_flares": int(in_year.sum()),
        "busiest_year_flares_x": int((in_year & is_x).sum()),
        "busiest_year_time_in_flare_percent": 100.0 * length[in_year].sum() / year_days,
        "busiest_year_time_in_x_flare_percent": 100.0 * length[in_year & is_x].sum() / year_days,
    }


def strongest_class(flares: pd.DataFrame, day: str) -> float:
    """Class of the strongest flare of a UT day (``"2017-09-06"``), in units of an X1 flare."""
    chosen = flares[flares["peak"].dt.strftime("%Y-%m-%d") == day]
    return float(chosen["peak_flux"].max() / X1_FLUX) if len(chosen) else np.nan


def instrument_numbers(instrument: replication.Instrument, all_flares: pd.DataFrame, seed: int = 0) -> tuple[dict, dict]:
    """Counts, effect of the cuts and representativeness of the flares of one instrument.

    Also returns the measurement itself (the output of ``replication.measure``), for the
    quantities that involve both instruments.
    """
    raw = replication.raw_table(instrument)
    prepared = replication.prepare(instrument, raw)
    out = replication.measure(instrument, prepared, all_flares, seed)
    sample, measured = out["sample"], out["flares"]
    paired = measured[np.isfinite(measured["d"])]
    good = prepared[prepared["good"]]
    days, days_kept = int(prepared["day"].nunique()), int(good["day"].nunique())
    numbers = {
        "velocities": len(raw),
        "first_jd": float(raw["obsjd"].min()),
        "last_jd": float(raw["obsjd"].max()),
        "velocities_kept": len(good),
        "days_with_data": days,
        "days_kept": days_kept,
        "days_dropped_percent": 100.0 * (1.0 - days_kept / days),
        "scatter_of_one_velocity_ms": quality.robust_sigma(good["res"].to_numpy()),
        "flares_in_era": len(sample),
        "flares_with_complete_windows": len(measured),
        "flares_with_controls": len(paired),
        "controls": len(out["controls"]),
        "injection_efficiency": replication.injection_efficiency(instrument, raw, out["controls"], seed=seed),
        "strongest_flare_class": float(paired["peak_flux"].max() / X1_FLUX),
    }
    # Flares observed at the peak (a spectrum within 2 min of it), and those of them that fall on
    # a day dropped by the cuts. Meaningful at the cadence of NEID; HARPS-N exposes for 5 min.
    covered = coverage.add_coverage(sample, np.sort(raw["obsjd"].to_numpy()))
    at_peak = covered["at_peak"].to_numpy()
    on_dropped_day = ~np.floor(sample["jd_peak"] - 0.5).astype(np.int64).isin(set(good["day"])).to_numpy()
    numbers["flares_at_peak"] = int(at_peak.sum())
    numbers["flares_at_peak_on_dropped_days_percent"] = 100.0 * (at_peak & on_dropped_day).sum() / max(at_peak.sum(), 1)
    # Are the flares measured a fair sample of all the flares of the era?
    for column, label in KS_COLUMNS:
        numbers[f"ks_p_{label}"] = ks_p(paired[column], sample[column])
    return numbers, out


def run(seed: int = 0) -> pd.DataFrame:
    """The table of numbers: one row per ``group`` (flares, NEID, HARPS-N, both) and ``quantity``."""
    all_flares = goes.load_flares()
    rows, measured = [], {}
    for instrument in (replication.NEID, replication.HARPSN):
        numbers, out = instrument_numbers(instrument, all_flares, seed)
        measured[instrument.name] = out
        rows += [{"group": instrument.name, "quantity": name, "value": value} for name, value in numbers.items()]
        if instrument.name == "NEID":
            statistics = flare_statistics(out["sample"], numbers["first_jd"], numbers["last_jd"])
            rows += [{"group": "flares", "quantity": name, "value": value} for name, value in statistics.items()]
    for day in ("2017-09-06", "2017-09-10"):
        rows.append({"group": "flares", "quantity": f"strongest_class_{day}", "value": strongest_class(all_flares, day)})

    # The flare of Pietrow et al. (2024) in the HARPS-N sample.
    harps = measured["HARPS-N"]["flares"]
    nearest = harps.iloc[int(np.argmin(np.abs(harps["jd_peak"].to_numpy() - PIETROW_FLARE_JD)))] if len(harps) else None
    if nearest is not None and abs(nearest["jd_peak"] - PIETROW_FLARE_JD) < 5.0 * MINUTE:
        rows.append({"group": "HARPS-N", "quantity": "flare_20170906_1202_class", "value": nearest["peak_flux"] / X1_FLUX})
        rows.append({"group": "HARPS-N", "quantity": "flare_20170906_1202_d", "value": nearest["d"]})

    # Flares measured by both instruments (peaks within one minute).
    neid_peaks = np.sort(measured["NEID"]["flares"]["jd_peak"].to_numpy())
    harps_peaks = harps["jd_peak"].to_numpy()
    shared = 0
    if len(neid_peaks) and len(harps_peaks):
        after = np.clip(np.searchsorted(neid_peaks, harps_peaks), 0, len(neid_peaks) - 1)
        before = np.clip(after - 1, 0, len(neid_peaks) - 1)
        gap = np.minimum(np.abs(neid_peaks[after] - harps_peaks), np.abs(neid_peaks[before] - harps_peaks))
        shared = int((gap < 1.0 * MINUTE).sum())
    rows.append({"group": "both", "quantity": "flares_in_both", "value": shared})
    return pd.DataFrame(rows)
