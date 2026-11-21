"""Figures of the paper: vector graphics in the style of a journal, at their printed size.

The figures of the documentation (``plots``) are drawn for a web page. These are drawn for a
two-column journal page: white background, no text above the axes (it belongs in the caption),
a serif face of 8 pt, thin lines, ticks pointing in on the four sides, and PDF output at the
width of a column (88 mm) or of the page (180 mm) of Astronomy & Astrophysics.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.ticker import NullLocator  # noqa: E402

COLUMN_MM = 88.0
PAGE_MM = 180.0
# Two colours checked together for colour-vision deficiencies; the two samples also differ in
# the kind of mark (points with error bars against a band, circles against triangles), so the
# figures read in grey.
FLARES = "#1f5fa8"
CONTROLS = "#c8501e"
GUIDE = "0.45"  # reference lines
BAND = "0.87"  # scatter bands
EARTH_SIGNAL_MS = 0.09  # reflex velocity of the Sun due to the Earth
INSTRUMENT_MARKS = {"NEID": (FLARES, "o"), "HARPS-N": (CONTROLS, "^")}

# The quantities of the figure of one flare: four columns by three rows.
EVENT_QUANTITIES = (
    ("Ha06_1_tellcorr", r"H$\alpha$ core", "ppt"),
    ("Hbeta_core", r"H$\beta$ core", "ppt"),
    ("CaIIHK", "Ca II H and K", "ppt"),
    ("CaIRT2_tellcorr", "Ca II 8542 Å", "ppt"),
    ("HeI_1_tellcorr", r"He I D$_3$", "ppt"),
    ("NaI_tellcorr", "Na I D", "ppt"),
    ("Ha16_1_tellcorr", r"H$\alpha$, 1.6 Å band", "ppt"),
    ("CaI_1_tellcorr", "Ca I 6573 Å (reference)", "ppt"),
    ("ccf_depth", "Depth of the mean line", "ppm"),
    ("ccf_fwhm_kms", "Width of the mean line", "ppm"),
    ("ccf_bis_ms", "Bisector span", r"m s$^{-1}$"),
    ("rv_ms", "Radial velocity", r"m s$^{-1}$"),
)
# The panels of the figure of the stacked response of the spectra.
CURVE_PANELS = (
    ("CaIIHK", "Ca II H and K (ppt)"),
    ("Ha06_1_tellcorr", r"H$\alpha$ core (ppt)"),
    ("CaI_1_tellcorr", "Ca I 6573 Å, reference (ppt)"),
    ("rv_ms", r"Radial velocity (m s$^{-1}$)"),
)


def style() -> dict:
    return {
        "font.family": "STIXGeneral",
        "mathtext.fontset": "stix",
        "font.size": 8.0,
        "axes.labelsize": 8.0,
        "axes.titlesize": 7.5,
        "axes.titleweight": "normal",
        "axes.titlelocation": "left",
        "axes.titlepad": 2.5,
        "xtick.labelsize": 7.5,
        "ytick.labelsize": 7.5,
        "legend.fontsize": 7.5,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "savefig.facecolor": "white",
        "axes.edgecolor": "black",
        "axes.labelcolor": "black",
        "axes.linewidth": 0.6,
        "axes.grid": False,
        "xtick.direction": "in",
        "ytick.direction": "in",
        "xtick.top": True,
        "ytick.right": True,
        "xtick.minor.visible": True,
        "ytick.minor.visible": True,
        "xtick.major.size": 3.0,
        "ytick.major.size": 3.0,
        "xtick.minor.size": 1.6,
        "ytick.minor.size": 1.6,
        "xtick.major.width": 0.6,
        "ytick.major.width": 0.6,
        "xtick.minor.width": 0.5,
        "ytick.minor.width": 0.5,
        "lines.linewidth": 0.8,
        "lines.markersize": 2.6,
        "errorbar.capsize": 0.0,
        "legend.frameon": False,
        "legend.handlelength": 1.8,
        "legend.borderaxespad": 0.3,
        "pdf.fonttype": 42,
        "savefig.dpi": 300,
    }


def _inches(width_mm: float, height_mm: float) -> tuple[float, float]:
    return width_mm / 25.4, height_mm / 25.4


def _save(fig, path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path)
    plt.close(fig)
    return path


def _round_up(value: float, step: float) -> float:
    return float(np.ceil(value / step - 1.0e-9) * step)


def binned_means(x, y, edges) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Centre, mean and standard error of y in bins of x (bins with fewer than three values are left out).

    The centre is the geometric mean of the edges when they are positive (a logarithmic axis)
    and their midpoint otherwise.
    """
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    centres, means, errors = [], [], []
    for low, high in zip(edges[:-1], edges[1:]):
        chosen = y[(x >= low) & (x < high)]
        if len(chosen) >= 3:
            centres.append(np.sqrt(low * high) if low > 0 else 0.5 * (low + high))
            means.append(chosen.mean())
            errors.append(chosen.std(ddof=1) / np.sqrt(len(chosen)))
    return np.array(centres), np.array(means), np.array(errors)


def _flares_and_controls(ax, flares: pd.DataFrame, controls: pd.DataFrame) -> None:
    """Flares as points with error bars, controls as a line with a band of one standard error."""
    ax.fill_between(
        controls["minutes"], controls["mean"] - controls["sem"], controls["mean"] + controls["sem"],
        color=CONTROLS, alpha=0.25, linewidth=0, zorder=2,
    )
    ax.plot(controls["minutes"], controls["mean"], color=CONTROLS, linewidth=0.9, zorder=3,
            label=f"Controls ({int(controls['events'].max())})" if len(controls) else None)
    ax.errorbar(
        flares["minutes"], flares["mean"], yerr=flares["sem"], color=FLARES, marker="o", linewidth=0.6, elinewidth=0.7,
        zorder=4, label=f"Flares ({int(flares['events'].max())})" if len(flares) else None,
    )


def profiles(table: pd.DataFrame, path: Path, subset: str = "M and X") -> Path:
    """Mean velocity around the X-ray peak, flares against controls: one panel per instrument, one column wide.

    ``table`` is the output of ``replication.stacked_profiles`` for every instrument. The panels
    share the vertical scale; the dotted lines at plus and minus 9 cm/s (the reflex velocity
    due to the Earth) give its size.
    """
    table = table[table["subset"] == subset]
    instruments = list(dict.fromkeys(table["instrument"]))
    height = 16.0 + 34.0 * len(instruments)
    with plt.rc_context(style()):
        fig, axes = plt.subplots(len(instruments), 1, figsize=_inches(COLUMN_MM, height), sharex=True, sharey=True)
        axes = np.atleast_1d(axes)
        extent = 0.0
        for ax, instrument in zip(axes, instruments):
            chosen = table[table["instrument"] == instrument]
            flares = chosen[chosen["sample"] == "flares"]
            ax.axhline(0.0, color=GUIDE, linewidth=0.5, zorder=1)
            for level in (-EARTH_SIGNAL_MS, EARTH_SIGNAL_MS):
                ax.axhline(level, color=GUIDE, linewidth=0.6, linestyle=(0, (1, 2)), zorder=1)
            ax.axvline(0.0, color=GUIDE, linewidth=0.6, linestyle=(0, (4, 2)), zorder=1)
            _flares_and_controls(ax, flares, chosen[chosen["sample"] == "controls"])
            edge = np.abs(np.concatenate([flares["mean"] + flares["sem"], flares["mean"] - flares["sem"]]))
            extent = max(extent, float(np.nanmax(edge)))
            ax.text(0.025, 0.93, str(instrument), transform=ax.transAxes, va="top", ha="left")
            ax.legend(loc="lower left", ncol=2, columnspacing=1.2, handletextpad=0.5)
        limit = _round_up(max(1.35 * extent, 0.2), 0.1)
        axes[0].set_ylim(-limit, limit)
        axes[0].text(88.0, EARTH_SIGNAL_MS, r"$\pm$9 cm s$^{-1}$", va="bottom", ha="right", fontsize=7.0, color="0.25")
        axes[-1].set_xlabel("Time from the X-ray peak (min)")
        axes[-1].set_xlim(-60.0, 90.0)
        axes[-1].set_xticks(np.arange(-60, 91, 30))
        fig.supylabel(r"Velocity change (m s$^{-1}$)", fontsize=8.0, x=0.02)
        fig.subplots_adjust(left=0.155, right=0.985, top=1.0 - 1.5 / height, bottom=9.5 / height, hspace=0.07)
        return _save(fig, path)


def events(table: pd.DataFrame, path: Path) -> Path:
    """Velocity change of each flare against its class and its position across the disc, one page wide.

    ``table`` is the event table of ``replication.run``: the flares of every instrument with
    their paired change ``d``, and the controls with their change ``delta``, whose scatter is
    drawn as a band. The squares are the means of all the flares in bins.
    """
    flares = table[(table["sample"] == "flare") & np.isfinite(table["d"])]
    sigma = float(table.loc[table["sample"] == "control", "delta"].std(ddof=1))
    flux, delta = flares["peak_flux"].to_numpy(), flares["d"].to_numpy()
    on_disc = (flares["r_norm"] < 1.05).to_numpy()
    position = flares["x_norm"].to_numpy()
    with plt.rc_context(style()):
        fig, (left, right) = plt.subplots(1, 2, figsize=_inches(PAGE_MM, 60.0), sharey=True)
        for ax in (left, right):
            ax.axhspan(-sigma, sigma, color=BAND, linewidth=0, zorder=1, label="Scatter of the controls")
            ax.axhline(0.0, color=GUIDE, linewidth=0.5, zorder=2)
        for instrument in dict.fromkeys(flares["instrument"]):
            colour, marker = INSTRUMENT_MARKS.get(instrument, ("0.3", "D"))
            chosen = (flares["instrument"] == instrument).to_numpy()
            mark = {"s": 8.0, "facecolor": "none", "edgecolor": colour, "linewidth": 0.6, "marker": marker, "zorder": 3}
            left.scatter(flux[chosen], delta[chosen], label=f"{instrument} ({int(chosen.sum())})", **mark)
            right.scatter(position[chosen & on_disc], delta[chosen & on_disc], **mark)
        top = max(1.0e-3, 1.3 * float(np.nanmax(flux)))
        x, mean, error = binned_means(flux, delta, np.array([1e-5, 2e-5, 5e-5, 1e-4, top]))
        left.errorbar(x, mean, yerr=error, fmt="s", color="black", markersize=3.4, elinewidth=0.9, zorder=5, label="Mean in each bin")
        left.set_xscale("log")
        left.set_xlim(8.5e-6, top)
        ticks = [(1e-5, "M1"), (2e-5, "M2"), (5e-5, "M5"), (1e-4, "X1"), (2e-4, "X2"), (5e-4, "X5"), (1e-3, "X10")]
        left.set_xticks([value for value, _ in ticks if value < top])
        left.set_xticklabels([label for value, label in ticks if value < top])
        left.xaxis.set_minor_locator(NullLocator())
        left.set_xlabel("GOES class")
        left.set_ylabel(r"Velocity change (m s$^{-1}$)")

        x, mean, error = binned_means(position[on_disc], delta[on_disc], np.linspace(-1.0, 1.0, 6))
        right.errorbar(x, mean, yerr=error, fmt="s", color="black", markersize=3.4, elinewidth=0.9, zorder=5)
        right.set_xlim(-1.1, 1.1)
        right.set_xticks([-1.0, -0.5, 0.0, 0.5, 1.0])
        right.set_xlabel(r"Position across the disc, $x/R_\odot$")
        limit = _round_up(max(1.2, float(np.nanpercentile(np.abs(delta), 99)) * 1.15), 0.2)
        left.set_ylim(-limit, limit)
        right.text(0.02, 0.04, "east limb, approaching", transform=right.transAxes, ha="left", va="bottom", fontsize=7.0, color="0.25")
        right.text(0.98, 0.04, "west limb, receding", transform=right.transAxes, ha="right", va="bottom", fontsize=7.0, color="0.25")
        handles, labels = left.get_legend_handles_labels()
        order = [i for i, name in enumerate(labels) if not name.startswith(("Mean", "Scatter"))]
        order += [i for i, name in enumerate(labels) if name.startswith("Mean")] + [i for i, name in enumerate(labels) if name.startswith("Scatter")]
        fig.legend([handles[i] for i in order], [labels[i] for i in order], loc="upper center", ncol=len(order), columnspacing=2.2,
                   bbox_to_anchor=(0.53, 1.0))
        fig.subplots_adjust(left=0.07, right=0.99, top=0.903, bottom=0.165, wspace=0.04)
        return _save(fig, path)


def light_curves(table: pd.DataFrame, path: Path, panels=CURVE_PANELS) -> Path:
    """Mean change of chromospheric indices and of the velocity through the flares, against the controls; one page wide.

    ``table`` is the output of ``chromosphere.light_curves``: one row per group ("disc flares",
    "controls"), quantity and time bin, with the mean over the events and its standard error.
    """
    with plt.rc_context(style()):
        fig, axes = plt.subplots(1, len(panels), figsize=_inches(PAGE_MM, 56.0), sharex=True)
        axes = np.atleast_1d(axes)
        for ax, (column, label) in zip(axes, panels):
            chosen = table[table["quantity"] == column]
            ax.axhline(0.0, color=GUIDE, linewidth=0.5, zorder=1)
            ax.axvline(0.0, color=GUIDE, linewidth=0.6, linestyle=(0, (4, 2)), zorder=1)
            _flares_and_controls(ax, chosen[chosen["group"] == "disc flares"], chosen[chosen["group"] == "controls"])
            ax.set_title(label)
            ax.set_xlabel("Time from the X-ray peak (min)")
            ax.margins(y=0.14)
        low, high = axes[0].get_ylim()
        axes[0].set_ylim(low, high + 0.2 * (high - low))  # room for the legend above the curves
        axes[0].legend(loc="upper left", ncol=2, columnspacing=1.2, handletextpad=0.5)
        fig.subplots_adjust(left=0.04, right=0.995, top=0.915, bottom=0.175, wspace=0.22)
        return _save(fig, path)


def event(changes: pd.DataFrame, path: Path, quantities=EVENT_QUANTITIES, columns: int = 4) -> Path:
    """Change of the spectral quantities through one flare, as small panels on a common time axis, one page wide."""
    rows = int(np.ceil(len(quantities) / columns))
    time = changes["min_peak"].to_numpy()
    start_min = float((changes["min_peak"] - changes["min_start"]).iloc[0])  # start of the flare, minutes from the peak
    height = 12.0 + 33.0 * rows
    with plt.rc_context(style()):
        fig, axes = plt.subplots(rows, columns, figsize=_inches(PAGE_MM, height), sharex=True)
        axes = np.atleast_1d(axes).ravel()
        for ax, (column, label, unit) in zip(axes, quantities):
            sigma = float(changes[f"{column}_sigma"].iloc[0])
            if np.isfinite(sigma):
                ax.axhspan(-sigma, sigma, color=BAND, linewidth=0, zorder=1)
            ax.axhline(0.0, color=GUIDE, linewidth=0.5, zorder=2)
            ax.axvline(start_min, color=GUIDE, linewidth=0.6, linestyle=(0, (4, 2)), zorder=2)
            ax.axvline(0.0, color=GUIDE, linewidth=0.6, zorder=2)
            ax.plot(time, changes[column], color=FLARES, marker="o", linewidth=0.6, zorder=3)
            ax.set_title(f"{label} ({unit})")
            ax.margins(y=0.12)
        for ax in axes[len(quantities):]:
            ax.set_visible(False)
        for ax in axes[max(0, len(quantities) - columns): len(quantities)]:
            ax.set_xlabel("Time from the X-ray peak (min)")
            ax.tick_params(labelbottom=True)
        axes[0].set_xlim(float(np.nanmin(time)) - 2.0, max(float(np.nanmax(time)), 0.0) + 2.0)
        low, high = axes[0].get_ylim()
        span = high - low
        axes[0].set_ylim(low, high + 0.16 * span)
        axes[0].text(start_min, high + 0.14 * span, " start", fontsize=7.0, color="0.25", va="top", ha="left")
        axes[0].text(0.0, high + 0.14 * span, "peak ", fontsize=7.0, color="0.25", va="top", ha="right")
        fig.subplots_adjust(left=0.05, right=0.99, top=1.0 - 4.5 / height, bottom=10.5 / height, wspace=0.24, hspace=0.3)
        return _save(fig, path)


def method_example(example: dict, path: Path) -> Path:
    """How the velocity change of a flare is measured: one real flare and one of its control days, one page wide.

    ``example`` holds, for the day of the flare and for a control day (keys "flare" and
    "control"), the X-ray flux and the velocities against minutes from the X-ray peak, and the
    limits of the two windows: ``xray_min``, ``xray_flux``, ``min``, ``velocity``, ``before``
    and ``during`` (pairs of minutes), ``start_min`` and ``title``.
    """
    with plt.rc_context(style()):
        fig, axes = plt.subplots(2, 2, figsize=_inches(PAGE_MM, 74.0), sharex=True, sharey="row", height_ratios=(1.0, 1.5))
        for column, key in enumerate(("flare", "control")):
            day = example[key]
            top, bottom = axes[0, column], axes[1, column]
            for ax in (top, bottom):
                ax.axvspan(*day["before"], color=BAND, linewidth=0, zorder=1)
                ax.axvspan(*day["during"], color=FLARES, alpha=0.14, linewidth=0, zorder=1)
            top.plot(day["xray_min"], day["xray_flux"], color="black", linewidth=0.9, zorder=3)
            top.set_yscale("log")
            top.set_title(day["title"])
            time, velocity = np.asarray(day["min"], dtype=float), np.asarray(day["velocity"], dtype=float)
            bottom.axhline(0.0, color=GUIDE, linewidth=0.5, zorder=2)
            bottom.plot(time, velocity, linestyle="none", marker="o", markersize=2.2, color="0.45", zorder=3)
            means = {}
            for name, colour in (("before", "black"), ("during", FLARES)):
                low, high = day[name]
                inside = (time >= low) & (time <= high)
                means[name] = float(np.nanmean(velocity[inside]))
                bottom.plot([low, high], [means[name]] * 2, color=colour, linewidth=1.8, solid_capstyle="butt", zorder=4)
            change = means["during"] - means["before"]
            bottom.text(0.98, 0.06, rf"$\Delta v = {change:+.2f}$ m s$^{{-1}}$", transform=bottom.transAxes, ha="right", va="bottom")
            bottom.set_xlabel("Time from the X-ray peak (min)")
        axes[0, 0].set_ylabel(r"X-ray flux (W m$^{-2}$)")
        axes[1, 0].set_ylabel(r"Velocity (m s$^{-1}$)")
        axes[0, 0].set_ylim(3.0e-7, 5.0e-4)
        limit = _round_up(float(np.nanpercentile(np.abs(np.concatenate([example["flare"]["velocity"], example["control"]["velocity"]])), 99.5)) * 1.1, 0.5)
        axes[1, 0].set_ylim(-limit, limit)
        before, during = example["flare"]["before"], example["flare"]["during"]
        axes[1, 0].text(0.5 * sum(before), 0.93 * limit, "before", ha="center", va="top", fontsize=7.5)
        axes[1, 0].text(0.5 * sum(during), 0.93 * limit, "during", ha="center", va="top", fontsize=7.5, color=FLARES)
        fig.subplots_adjust(left=0.07, right=0.99, top=0.938, bottom=0.136, wspace=0.04, hspace=0.08)
        return _save(fig, path)


def example_data(event_peak: str = "2022-03-30", before_min: float = 62.0, after_min: float = 32.0) -> dict:
    """Real data for ``method_example``: a flare observed by NEID and its nearest control day."""
    from . import epoch, goes, neid, quality, replication
    from .timeutil import MINUTE, jd_to_datetime

    prepared = quality.prepare(neid.read_solar_table())
    out = replication.measure(replication.NEID, prepared, goes.load_flares())
    flares, controls = out["flares"], out["controls"]
    days = np.array([f"{jd_to_datetime(jd):%Y-%m-%d}" for jd in flares["jd_peak"]])
    strongest = flares[days == event_peak]["peak_flux"].idxmax()
    flare = flares.loc[strongest]
    own = controls[controls["parent"] == strongest]
    control = own.loc[own["shift_days"].abs().idxmin()]
    good = prepared[prepared["good"]]
    jd, residual = good["jd"].to_numpy(), good["res"].to_numpy()
    rise = float((flare["jd_peak"] - flare["jd_start"]) / MINUTE)
    windows = {"before": (-rise + robust_pre()[0], -rise + robust_pre()[1]), "during": (-rise, epoch.Windows().signal_after_peak)}
    result = {}
    for key, peak, title in (
        ("flare", flare["jd_peak"], f"Day of the flare: {jd_to_datetime(flare['jd_peak']):%d %B %Y}, class {flare['goes_class']}"),
        ("control", control["jd_peak"], f"Control: the same hour {abs(int(control['shift_days']))} day{'s' if abs(control['shift_days']) > 1 else ''} "
                                         f"{'later' if control['shift_days'] > 0 else 'earlier'}, without flare"),
    ):
        xray_jd, xray_flux = goes.load_avg1m(int(flare["satellite"]), jd_to_datetime(peak).year)
        chosen = (xray_jd > peak - before_min * MINUTE) & (xray_jd < peak + after_min * MINUTE)
        inside = (jd > peak - before_min * MINUTE) & (jd < peak + after_min * MINUTE)
        result[key] = {
            "title": title, "start_min": -rise, **windows,
            "xray_min": (xray_jd[chosen] - peak) / MINUTE, "xray_flux": xray_flux[chosen],
            "min": (jd[inside] - peak) / MINUTE, "velocity": residual[inside],
        }
    return result


def robust_pre() -> tuple[float, float]:
    """The baseline window, in minutes from the start of the flare."""
    from . import robust

    return robust.PRE


def make_all(directory: Path, event_name: str | None = None) -> list[Path]:
    """Write the figures of the paper from the tables in ``results/`` (see ``flinch replication``) and the spectra on disk.

    With ``event_name`` the figure of that single flare is written as well.
    """
    from . import chromosphere, neid, quality, response
    from .config import data_dir, results_dir

    directory = Path(directory)
    results = results_dir()
    stacked = pd.read_csv(results / "replication_profiles.csv")
    written = [
        method_example(example_data(), directory / "method.pdf"),
        profiles(stacked, directory / "profiles.pdf"),
        profiles(stacked, directory / "profiles_x.pdf", subset="X"),
        events(pd.read_csv(results / "replication_events.csv"), directory / "events.pdf"),
    ]
    curves = chromosphere.light_curves(min_class="X1.0")
    groups = set(curves["group"]) if "group" in curves else set()
    if {"disc flares", "controls"} <= groups:
        written.append(light_curves(curves, directory / "light_curves.pdf"))
    else:
        print("light_curves.pdf skipped: it needs the spectra of the X flares and of their controls "
              "(python -m flinch campaign, see Reproduce)")
    if event_name:
        manifest = pd.read_csv(data_dir() / "spectra" / "events.csv").set_index("name")
        row = manifest.loc[event_name]
        keep = quality.stable_obsjd(neid.read_solar_table())
        table = response.event_table(data_dir() / "spectra" / event_name, row["jd_start"], row["jd_peak"], keep_obsjd=keep)
        written.append(event(response.changes(table), directory / f"event_{event_name}.pdf"))
    return written
