"""Check every number of the paper against the tables in ``results/``.

The numbers of the paper are written down here, as printed, with the place where they appear.
Each is compared with the value in the tables at the precision of the paper: a number passes
when the paper gives a correct rounding of it. Run the analysis first and then this check,
and the paper is verified against what the code produces today.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from . import campaign, robust
from .config import results_dir

# Table 1: label of the paper, band of the table, statistic, and for NEID, HARPS-N and both the
# number of flares, the value and its error; last, the 95 % limit of both.
TABLE_1 = (
    ("Mean change, all M and X flares", "M and X", "mean", (139, -0.035, 0.035), (115, -0.021, 0.039), (254, -0.029, 0.026), 0.07),
    ("Mean change, M class", "M", "mean", (128, -0.032, 0.039), (108, -0.015, 0.042), (236, -0.025, 0.028), 0.07),
    ("Mean change, X class", "X", "mean", (11, -0.060, 0.088), (7, -0.104, 0.127), (18, -0.074, 0.072), 0.19),
    ("Shift of an X1 flare, S", "M and X", "per_X1", (139, -0.010, 0.061), (115, -0.005, 0.040), (254, -0.006, 0.033), 0.06),
    ("Rotation term, R", "M and X", "rotation", (139, -0.106, 0.082), (115, 0.022, 0.043), (254, -0.006, 0.038), 0.07),
)
# Table A.1: label of the paper, row of ``robustness.csv``, flares, and value and error of the
# mean change, of S and of R.
TABLE_A1 = (
    ("Default", 0, 139, (-0.035, 0.035), (-0.010, 0.061), (-0.106, 0.082)),
    ("Daily trend: polynomial of degree 1", 1, 137, (-0.022, 0.036), (-0.015, 0.060), (-0.045, 0.080)),
    ("Daily trend: polynomial of degree 3", 2, 139, (-0.001, 0.033), (0.016, 0.049), (-0.079, 0.083)),
    ("Window: 3 min either side of the steepest X-ray rise", 3, 120, (-0.009, 0.042), (-0.019, 0.061), (-0.108, 0.135)),
    ("Window: first 10 min from the start", 4, 134, (-0.040, 0.035), (0.006, 0.045), (-0.004, 0.080)),
    ("Window: 5 min either side of the X-ray peak", 5, 126, (-0.021, 0.042), (-0.111, 0.085), (-0.134, 0.154)),
    ("Background: straight line fitted on both sides of the flare", 6, 93, (-0.008, 0.040), (-0.032, 0.070), (-0.002, 0.113)),
    ("Errors: resampling active regions instead of days", 8, 139, (-0.035, 0.035), (-0.010, 0.061), (-0.106, 0.082)),
)
# Table 2: index of ``spectral_indices.csv`` and, for the X class, for M5 to M9 and for the
# controls, the mean and its error; then the decimals printed.
TABLE_2 = (
    ("Ca II H and K", (5.3, 1.7), (2.2, 0.4), (0.0, 0.2), 1),
    ("H alpha core", (3.3, 1.1), (2.0, 0.2), (-0.1, 0.2), 1),
    ("Radial velocity (m/s)", (-0.11, 0.21), (-0.10, 0.11), (0.07, 0.27), 2),
)
# Table B.1: window, distance from the disc centre, and response and error of Ca II H and K, of
# H alpha and of the velocity.
TABLE_B1 = (
    ("20260118_1809_X1.9", 0.36, (17.0, 1.7), (10.9, 0.7), (-1.4, 0.9)),
    ("20260630_2049_X1.1", 0.39, (4.7, 0.9), (3.6, 0.7), (0.0, 0.8)),
    ("20250617_2148_X1.2", 0.36, (4.0, 0.9), (3.0, 0.7), (0.5, 0.9)),
    ("20240509_1744_X1.1", 0.53, (5.0, 0.9), (2.8, 0.7), (0.3, 0.9)),
    ("20230109_1849_X1.9", 0.97, (4.3, 0.8), (2.2, 0.7), (0.0, 0.9)),
    ("20220330_1737_X1.3", 0.58, (2.9, 0.8), (2.0, 0.7), (-0.4, 0.9)),
    ("20231214_1702_X2.8", 0.76, (4.0, 1.5), (1.6, 0.6), (-0.4, 0.8)),
    ("20240601_1835_X1.0", 0.50, (3.0, 0.9), (1.4, 0.7), (0.2, 0.8)),
    ("20240531_2203_X1.1", 0.64, (1.8, 0.8), (1.1, 0.7), (0.3, 0.9)),
    ("20230805_2220_X1.6", 0.95, (1.5, 0.8), (0.7, 0.7), (0.1, 0.8)),
    ("20240514_1651_X8.6", 1.00, (1.1, 1.0), (0.6, 0.9), (-0.3, 1.1)),
    ("20250223_1927_X1.9", 0.96, (-0.2, 0.9), (-0.5, 0.7), (-0.1, 0.9)),
    ("20240517_2108_M7.2", 0.92, (2.2, 0.9), (3.3, 0.8), (-0.2, 1.0)),
    ("20250615_1807_M8.4", 0.38, (4.0, 1.1), (2.7, 0.9), (-0.3, 0.9)),
    ("20260621_1929_M6.8", 0.81, (1.7, 1.3), (2.4, 0.7), (-0.1, 0.9)),
    ("20251206_2038_M8.1", 0.34, (2.6, 1.2), (2.1, 0.7), (-0.3, 0.9)),
    ("20230509_2051_M5.0", 0.62, (2.0, 1.0), (1.9, 0.7), (0.3, 1.1)),
    ("20240529_1841_M5.7", 0.49, (1.7, 0.8), (1.5, 0.7), (0.1, 0.8)),
    ("20220331_1834_M9.6", 0.75, (1.4, 1.1), (1.3, 0.8), (-0.3, 0.8)),
    ("20240318_1918_M6.7", 0.94, (1.9, 1.1), (1.0, 0.7), (-0.4, 0.9)),
    ("20230806_1840_M5.5", 0.98, (2.3, 1.0), (0.8, 0.7), (0.5, 0.9)),
    ("20260424_1814_M6.4", 1.01, (0.0, 1.0), (0.4, 0.7), (0.5, 1.0)),
    ("20240411_1705_M5.4", 1.00, (0.5, 1.3), (-0.1, 0.7), (-0.2, 0.9)),
)
DISC_RADIUS = 0.9  # flares within this distance of the centre are "on the disc"


def _text(value: float, decimals: int) -> str:
    text = f"{value:.{decimals}f}"
    return text[1:] if text.startswith("-") and float(text) == 0.0 else text  # no "-0.00"


class Checks:
    """A growing list of comparisons between the paper and the tables."""

    def __init__(self) -> None:
        self.rows: list[dict] = []

    def add(self, where: str, what: str, paper, here, decimals: int = 0) -> None:
        """One or several numbers (a value and its error): ``paper`` as printed, ``here`` from the tables."""
        paper = np.atleast_1d(np.asarray(paper, dtype=float))
        here = np.atleast_1d(np.asarray(here, dtype=float))
        ok = bool(np.all(np.isfinite(here)) and np.all(np.abs(here - paper) <= 0.5 * 10.0**-decimals + 1.0e-9))
        self.rows.append(
            {
                "where": where,
                "what": what,
                "paper": " +/- ".join(_text(value, decimals) for value in paper),
                "here": " +/- ".join("missing" if not np.isfinite(value) else _text(value, decimals + 2) for value in here),
                "ok": ok,
            }
        )

    def table(self) -> pd.DataFrame:
        return pd.DataFrame(self.rows)


def _read(directory: Path, name: str) -> pd.DataFrame | None:
    path = directory / name
    return pd.read_csv(path) if path.exists() else None


def _missing(checks: Checks, where: str, name: str) -> None:
    checks.rows.append({"where": where, "what": f"results/{name}", "paper": "", "here": "table missing", "ok": False})


def velocity_checks(checks: Checks, directory: Path) -> None:
    """Table 1, the text of Sect. 4.1 and 4.2, and the appendices on robustness and on the early window."""
    table = _read(directory, "velocity_by_instrument.csv")
    if table is None:
        return _missing(checks, "Table 1", "velocity_by_instrument.csv")
    cell = table.set_index(["instrument", "band"])
    for label, band, statistic, *instruments, limit in TABLE_1:
        for name, (flares, value, error) in zip(("NEID", "HARPS-N", "Both"), instruments):
            row = cell.loc[(name, band)]
            checks.add("Table 1", f"{label}: flares, {name}", flares, row["flares"])
            checks.add("Table 1", f"{label}: value, {name}", (value, error), (row[statistic], row[f"{statistic}_err"]), 3)
        both = cell.loc[("Both", band)]
        checks.add("Table 1", f"{label}: 95 % limit", limit, abs(both[statistic]) + 1.645 * both[f"{statistic}_err"], 2)
    both = cell.loc[("Both", "M and X")]
    for name, flares, controls in (("NEID", 0.40, 0.40), ("HARPS-N", 0.40, 0.41)):
        row = cell.loc[(name, "M and X")]
        checks.add("Sect. 4.1", f"scatter of the changes of the flares, {name} (m/s)", flares, row["flare_std"], 2)
        checks.add("Sect. 4.1", f"scatter of the changes of the controls, {name} (m/s)", controls, row["control_std"], 2)
    limit = (abs(both["rotation"]) + 1.645 * both["rotation_err"]) / robust.V_LIMB_FROM_EARTH_MS
    checks.add("Eq. 8", "limit on K dF/F per X1 flare, in units of 1e-5", 3.7, limit * 1.0e5, 1)
    checks.add("Sect. 4.2", "probability of detecting 10 cm/s with both instruments (%)", 99, 100.0 * robust.detection_probability(0.10, float(both["mean_err"])))

    variants = _read(directory, "cleaning_variants.csv")
    if variants is None:
        _missing(checks, "Sect. 3.1", "cleaning_variants.csv")
    else:
        row = variants[(variants["instrument"] == "HARPS-N") & (variants["variant"] == "quality flag above 0.9") & (variants["band"] == "M and X")].iloc[0]
        checks.add("Sect. 3.1", "HARPS-N with the quality flag above 0.9: flares", 126, row["flares"])
        checks.add("Sect. 3.1", "HARPS-N with the quality flag above 0.9: mean change", (-0.005, 0.038), (row["mean"], row["mean_err"]), 3)

    other = _read(directory, "robustness.csv")
    if other is None:
        _missing(checks, "Table A.1", "robustness.csv")
    else:
        for label, index, flares, mean, shift, rotation in TABLE_A1:
            row = other.iloc[index]
            checks.add("Table A.1", f"{label}: flares", flares, row["flares"])
            for name, statistic, (value, error) in (("mean change", "mean", mean), ("S", "per_X1", shift), ("R", "rotation", rotation)):
                checks.add("Table A.1", f"{label}: {name}", (value, error), (row[statistic], row[f"{statistic}_err"]), 3)
        checks.add("Table A.1", "days resampled by default", 111, other.iloc[0]["days"])
        checks.add("Table A.1", "active regions resampled instead", 81, other.iloc[8]["days"])

    injections = _read(directory, "injections.csv")
    if injections is None:
        _missing(checks, "Appendix A", "injections.csv")
    else:
        for row, recovered, probability in zip(injections.itertuples(), (4.9, 9.8, 19.5, 48.8), (40, 88, 100, 100)):
            checks.add("Appendix A", f"shift of {100 * row.injected_ms:.0f} cm/s added to NEID, measured back (cm/s)", recovered, 100.0 * row.recovered_ms, 1)
            checks.add("Appendix A", f"shift of {100 * row.injected_ms:.0f} cm/s, probability of detection with NEID (%)", probability, 100.0 * row.detection_probability)

    early = _read(directory, "early_window.csv")
    if early is None:
        _missing(checks, "Appendix C", "early_window.csv")
    else:
        row = early.set_index(["instrument", "band"])
        for name, band, flares, value in (("NEID", "X", 19, (0.43, 0.10)), ("NEID", "M", 183, (0.00, 0.03)), ("HARPS-N", "X", 10, (-0.12, 0.11))):
            chosen = row.loc[(name, band)]
            checks.add("Appendix C", f"velocity 60 to 50 min before the peak, {band} class, {name}: flares", flares, chosen["flares"])
            checks.add("Appendix C", f"velocity 60 to 50 min before the peak, {band} class, {name} (m/s)", value, (chosen["mean"], chosen["sem"]), 2)
        checks.add("Appendix C", "X-class flares of NEID above the trend in that window", 17, row.loc[("NEID", "X"), "positive"])


def text_checks(checks: Checks, directory: Path) -> None:
    """The counts and descriptive numbers of Sects. 2, 3 and 5 (``text_numbers.csv`` and ``flare_sample.csv``)."""
    numbers = _read(directory, "text_numbers.csv")
    if numbers is None:
        return _missing(checks, "Sects. 2, 3 and 5", "text_numbers.csv")
    value = numbers.set_index(["group", "quantity"])["value"]
    for where, what, paper, key, decimals in (
        ("Sect. 2.2", "NEID solar spectra in the archive", 366180, ("NEID", "velocities"), 0),
        ("Sect. 2.2", "HARPS-N velocities in the release", 109466, ("HARPS-N", "velocities"), 0),
        ("Sect. 2.2", "flares in both samples", 1, ("both", "flares_in_both"), 0),
        ("Sect. 2.1", "class of the flare of 6 September 2017 (X)", 14.6, ("flares", "strongest_class_2017-09-06"), 1),
        ("Sect. 2.1", "class of the flare of 10 September 2017 (X)", 12.9, ("flares", "strongest_class_2017-09-10"), 1),
        ("Sect. 3.1", "NEID velocities kept", 233857, ("NEID", "velocities_kept"), 0),
        ("Sect. 3.1", "NEID days kept", 1238, ("NEID", "days_kept"), 0),
        ("Sect. 3.1", "HARPS-N velocities kept", 93593, ("HARPS-N", "velocities_kept"), 0),
        ("Sect. 3.1", "HARPS-N days kept", 1671, ("HARPS-N", "days_kept"), 0),
        ("Sect. 3.1", "scatter of one NEID velocity (m/s)", 0.81, ("NEID", "scatter_of_one_velocity_ms"), 2),
        ("Sect. 3.1", "scatter of one HARPS-N velocity (m/s)", 0.44, ("HARPS-N", "scatter_of_one_velocity_ms"), 2),
        ("Sect. 3.1", "NEID days dropped by the cuts (%)", 23, ("NEID", "days_dropped_percent"), 0),
        ("Sect. 3.1", "flares observed by NEID that fall on dropped days (%)", 19, ("NEID", "flares_at_peak_on_dropped_days_percent"), 0),
        ("Sect. 3.2", "M and X flares in the NEID era", 2122, ("NEID", "flares_in_era"), 0),
        ("Sect. 3.2", "of them, with NEID observing at the peak", 279, ("NEID", "flares_at_peak"), 0),
        ("Sect. 3.2", "of them, with both windows complete", 140, ("NEID", "flares_with_complete_windows"), 0),
        ("Sect. 3.2", "M and X flares in the HARPS-N era", 1750, ("HARPS-N", "flares_in_era"), 0),
        ("Sect. 3.2", "of them, with both windows complete", 122, ("HARPS-N", "flares_with_complete_windows"), 0),
        ("Sect. 3.3", "NEID flares with at least three controls", 139, ("NEID", "flares_with_controls"), 0),
        ("Sect. 3.3", "HARPS-N flares with at least three controls", 115, ("HARPS-N", "flares_with_controls"), 0),
        ("Sect. 4.2", "part of an added shift recovered, NEID (%)", 98, ("NEID", "injection_efficiency"), 0),
        ("Sect. 4.2", "part of an added shift recovered, HARPS-N (%)", 98, ("HARPS-N", "injection_efficiency"), 0),
        ("Appendix A", "shift of 10 cm/s added to HARPS-N, measured back (cm/s)", 9.8, ("HARPS-N", "injection_efficiency"), 1),
        ("Sect. 5.2", "M and X flares per year", 358, ("flares", "flares_per_year"), 0),
        ("Sect. 5.2", "X flares per year", 18, ("flares", "flares_x_per_year"), 0),
        ("Sect. 5.2", "median length of a flare (min)", 19, ("flares", "median_duration_min"), 0),
        ("Sect. 5.2", "time spent in M and X flares (%)", 1.6, ("flares", "time_in_flare_percent"), 1),
        ("Sect. 5.2", "time spent in X flares (%)", 0.1, ("flares", "time_in_x_flare_percent"), 1),
        ("Sect. 5.2", "year with most flares", 2024, ("flares", "busiest_year"), 0),
        ("Sect. 5.2", "flares of that year", 934, ("flares", "busiest_year_flares"), 0),
        ("Sect. 5.2", "time spent in M and X flares that year (%)", 3.8, ("flares", "busiest_year_time_in_flare_percent"), 1),
        ("Sect. 5.2", "time spent in X flares that year (%)", 0.3, ("flares", "busiest_year_time_in_x_flare_percent"), 1),
        ("Sect. 5.2", "change of the flare of Pietrow et al. (2024) with HARPS-N (m/s)", -0.01, ("HARPS-N", "flare_20170906_1202_d"), 2),
    ):
        here = value.get(key, np.nan)
        if key[1] == "injection_efficiency":
            here = here * (10.0 if "cm/s" in what else 100.0)
        checks.add(where, what, paper, here, decimals)
    # The fair-sample tests: class, position east-west and distance from the centre, both instruments.
    tests = [value.get((name, f"ks_p_{label}"), np.nan) for name in ("NEID", "HARPS-N") for label in ("class", "position_x", "distance_from_centre")]
    checks.add("Sect. 3.2", "lowest probability of the Kolmogorov-Smirnov tests", 0.08, np.min(tests), 2)
    checks.add("Sect. 3.2", "highest probability of the Kolmogorov-Smirnov tests", 0.96, np.max(tests), 2)
    strongest = max(value.get(("NEID", "strongest_flare_class"), np.nan), value.get(("HARPS-N", "strongest_flare_class"), np.nan))
    checks.add("Sect. 5.3", "strongest flare of the sample (X class), below X15", 14.6, strongest, 1)

    table = _read(directory, "velocity_by_instrument.csv")
    if table is not None:
        cell = table.set_index(["instrument", "band"])
        checks.add("Abstract", "measurements with both instruments", 254, cell.loc[("Both", "M and X"), "flares"])
        checks.add("Abstract", "different flares", 253, cell.loc[("Both", "M and X"), "flares"] - value.get(("both", "flares_in_both"), np.nan))
        checks.add("Sect. 5.2", "error of one flare with HARPS-N: scatter of its controls (m/s)", 0.41, cell.loc[("HARPS-N", "M and X"), "control_std"], 2)

    sample = _read(directory, "flare_sample.csv")
    if sample is None:
        _missing(checks, "Sect. 3.2", "flare_sample.csv")
    else:
        checks.add("Sect. 3.2", "rows of the flare sample (results/flare_sample.csv)", 2122, len(sample))
        checks.add("Sect. 3.2", "flares observed at the peak in that table", 279, int(sample["at_peak"].sum()))


def spectra_checks(checks: Checks, directory: Path) -> None:
    """Sect. 2.3, Table 2 and Table B.1: the windows fetched and the response of the spectra."""
    windows = campaign.paper_windows()
    flares = windows[windows["kind"] == "flares"]
    checks.add("Sect. 2.3", "flares with spectra", 31, len(flares))
    checks.add("Sect. 2.3", "of them, of class X", 20, int((flares["goes_class"].str[0] == "X").sum()))
    checks.add("Sect. 2.3", "of them, between M5 and M9", 11, int((flares["goes_class"].str[0] == "M").sum()))

    response = _read(directory, "spectral_response.csv")
    indices = _read(directory, "spectral_indices.csv")
    if response is None or indices is None:
        return _missing(checks, "Tables 2 and B.1", "spectral_response.csv or spectral_indices.csv")
    usable = response[response["usable"]]
    good_flares, good_controls = usable[usable["kind"] == "flare"], usable[usable["kind"] == "control"]
    checks.add("Sect. 3.6", "flares with usable spectra", 23, len(good_flares))
    checks.add("Sect. 3.6", "control windows with usable spectra", 9, len(good_controls))
    on_disc = good_flares[good_flares["r_norm"] < DISC_RADIUS]
    checks.add("Table 2", "X-class flares on the disc", 8, int((on_disc["band"] == "X").sum()))
    checks.add("Table 2", "flares between M5 and M9 on the disc", 6, int((on_disc["band"] == "M5-M9").sum()))
    brighter = (on_disc["CaIIHK"] > 0) & (on_disc["Ha06_1_tellcorr"] > 0)
    checks.add("Sect. 4.3", "flares on the disc that brighten in both lines, of 14", 14, int(brighter.sum()))
    row = indices.set_index(["band", "index"])
    for label, x_class, m_class, controls, decimals in TABLE_2:
        for band, (value, error) in (("X", x_class), ("M5-M9", m_class)):
            chosen = row.loc[(band, label)]
            checks.add("Table 2", f"{label}, {band} class", (value, error), (chosen["disc_mean"], chosen["disc_mean_err"]), decimals)
        chosen = row.loc[("X", label)]
        checks.add("Table 2", f"{label}, controls", controls, (chosen["control_mean"], chosen["control_std"] / np.sqrt(chosen["controls"])), decimals)
    by_name = good_flares.set_index("name")
    for name, radius, calcium, hydrogen, velocity in TABLE_B1:
        if name not in by_name.index:
            checks.add("Table B.1", f"{name}: listed in the paper, usable in the table", 1, 0)
            continue
        chosen = by_name.loc[name]
        checks.add("Table B.1", f"{name}: distance from the disc centre", radius, chosen["r_norm"], 2)
        for label, column, (value, error) in (("Ca II H and K", "CaIIHK", calcium), ("H alpha", "Ha06_1_tellcorr", hydrogen), ("velocity", "rv_ms", velocity)):
            checks.add("Table B.1", f"{name}: {label}", (value, error), (chosen[column], chosen[f"{column}_total_err"]), 1)
    checks.add("Table B.1", "flares listed in the paper", len(TABLE_B1), len(good_flares))


def run(directory: Path | None = None) -> pd.DataFrame:
    """Every check: where the number is in the paper, what it is, the paper, the tables, and whether they agree."""
    directory = Path(directory or results_dir())
    checks = Checks()
    velocity_checks(checks, directory)
    text_checks(checks, directory)
    spectra_checks(checks, directory)
    return checks.table()
