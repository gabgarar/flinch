"""Solar flare lists from the GOES-R X-ray sensors (science-quality flare summaries, NOAA/NCEI)."""
from __future__ import annotations

import re
from pathlib import Path

import h5py
import numpy as np
import pandas as pd

from ._http import download, fetch_text
from .config import data_dir, data_end_jd
from .timeutil import JD_J2000, MINUTE, jd_to_datetime

ARCHIVE = "https://data.ngdc.noaa.gov/platforms/solar-space-observing-satellites/goes"
# GOES-16 covers 2017-02 to 2025-04; GOES-18 from 2022-06 onwards. The first one is the primary list.
SATELLITES = (16, 18)
_CLASS_BASE = {"A": 1e-8, "B": 1e-7, "C": 1e-6, "M": 1e-5, "X": 1e-4}
# Products: "flsum" (start, peak and end of each flare) and "flloc" (its position on the disc).
PRODUCTS = ("flsum", "flloc")


def class_to_flux(goes_class: str) -> float:
    """GOES class ("M5.2") to peak flux in the 1-8 Angstrom band, in W m^-2."""
    return _CLASS_BASE[goes_class[0].upper()] * float(goes_class[1:])


def flux_to_class(flux: float) -> str:
    """Peak flux in W m^-2 to GOES class."""
    for letter in "XMCB":
        if flux >= _CLASS_BASE[letter]:
            return f"{letter}{flux / _CLASS_BASE[letter]:.1f}"
    return f"A{flux / _CLASS_BASE['A']:.1f}"


def product_directory(satellite: int, product: str) -> str:
    return f"{ARCHIVE}/goes{satellite}/l2/data/xrsf-l2-{product}_science/"


def find_product_url(satellite: int, product: str) -> str:
    """URL of the mission-long file of a product (the file name carries its end date)."""
    directory = product_directory(satellite, product)
    pattern = rf'href="(sci_xrsf-l2-{product}_g\d\d_s\d{{8}}_e\d{{8}}_v[\d-]+\.nc)"'
    names = re.findall(pattern, fetch_text(directory))
    if not names:
        raise RuntimeError(f"no mission-long {product} file found in {directory}")
    return directory + sorted(names)[-1]


def download_product(
    satellite: int, product: str, directory: Path | None = None, overwrite: bool = False
) -> Path:
    """Download the mission-long file of ``product`` for ``satellite``; returns the local path."""
    directory = Path(directory or data_dir() / "goes")
    url = find_product_url(satellite, product)
    return download(url, directory / url.rsplit("/", 1)[-1], overwrite=overwrite)


def read_flloc(path: Path) -> pd.DataFrame:
    """Read a flare location file: one row per ``flare_id`` with its position on the disc.

    ``x_norm`` and ``y_norm`` are helioprojective coordinates in units of the solar radius
    (x positive towards the west limb, the receding one). ``r_norm`` is the distance to the disc
    centre. Positions come from the quadrant diode of the X-ray sensor and are unreliable for
    weak flares; entries without a position are NaN. ``car_lon`` is the Carrington longitude,
    which stays fixed for a region as the Sun rotates.
    """
    with h5py.File(path, "r") as handle:
        xy = handle["flloc_xy"][:].astype(float)
        radius = handle["solar_radius"][:].astype(float)
        hg = handle["flloc_hg"][:].astype(float)
        carrington = handle["flloc_car"][:].astype(float)
        flare_id = handle["flare_id"][:]
    xy[xy < -9000.0] = np.nan
    hg[hg < -9000.0] = np.nan
    carrington[carrington < -9000.0] = np.nan
    table = pd.DataFrame(
        {
            "flare_id": flare_id,
            "x_norm": xy[:, 0] / radius,
            "y_norm": xy[:, 1] / radius,
            "lon": hg[:, 0],
            "lat": hg[:, 1],
            "car_lon": carrington[:, 0],
        }
    )
    table["r_norm"] = np.hypot(table["x_norm"], table["y_norm"])
    return table.drop_duplicates("flare_id")


def read_flsum(path: Path, satellite: int | None = None) -> pd.DataFrame:
    """Read a flare summary file into one row per flare.

    The file stores one record per event marker (start, peak, end) sharing a ``flare_id``.
    Times are Julian dates (UTC); fluxes are in W m^-2 (1-8 Angstrom), fluences in J m^-2.
    """
    path = Path(path)
    with h5py.File(path, "r") as handle:
        records = pd.DataFrame(
            {
                "jd": JD_J2000 + handle["time"][:] / 86400.0,
                "status": handle["status"].asstr()[:],
                "goes_class": handle["flare_class"].asstr()[:],
                "flux": handle["xrsb_flux"][:].astype(float),
                "fluence": handle["integrated_flux"][:].astype(float),
                "flare_id": handle["flare_id"][:],
            }
        )
    if satellite is None:
        match = re.search(r"_g(\d\d)_", path.name)
        satellite = int(match.group(1)) if match else 0

    def marker(status: str) -> pd.DataFrame:
        return records[records["status"] == status].drop_duplicates("flare_id").set_index("flare_id")

    peaks, starts, ends = marker("EVENT_PEAK"), marker("EVENT_START"), marker("EVENT_END")
    peaks = peaks[peaks["goes_class"] != ""]
    flares = pd.DataFrame(
        {
            "jd_start": starts["jd"].reindex(peaks.index),
            "jd_peak": peaks["jd"],
            "jd_end": ends["jd"].reindex(peaks.index),
            "goes_class": peaks["goes_class"],
            "peak_flux": peaks["flux"],
            "fluence": ends["fluence"].reindex(peaks.index),
        }
    )
    flares["satellite"] = satellite
    return flares.reset_index().sort_values("jd_peak", ignore_index=True)


def merge_flare_lists(primary: pd.DataFrame, secondary: pd.DataFrame, tolerance_min: float = 3.0) -> pd.DataFrame:
    """The primary list plus the flares of the secondary with no counterpart in the primary.

    Two entries are the same flare when their peaks are closer than ``tolerance_min`` minutes,
    or when the secondary peak falls between the start and the end of a primary flare (the two
    satellites can place the peak of a long, flat flare several minutes apart).
    """
    if primary.empty or secondary.empty:
        return pd.concat([primary, secondary], ignore_index=True).sort_values("jd_peak", ignore_index=True)
    peaks = np.sort(primary["jd_peak"].to_numpy())
    candidates = secondary["jd_peak"].to_numpy()
    index = np.searchsorted(peaks, candidates)
    before = np.abs(candidates - peaks[np.clip(index - 1, 0, len(peaks) - 1)])
    after = np.abs(peaks[np.clip(index, 0, len(peaks) - 1)] - candidates)
    isolated = np.minimum(before, after) > tolerance_min * MINUTE
    if {"jd_start", "jd_end"} <= set(primary.columns):
        windows = primary.dropna(subset=["jd_start", "jd_end"]).sort_values("jd_start")
        if not windows.empty:
            starts, ends = windows["jd_start"].to_numpy(), windows["jd_end"].to_numpy()
            last_started = np.searchsorted(starts, candidates, side="right") - 1
            inside = (last_started >= 0) & (candidates <= ends[np.clip(last_started, 0, len(ends) - 1)])
            isolated &= ~inside
    merged = pd.concat([primary, secondary[isolated]], ignore_index=True)
    return merged.sort_values("jd_peak", ignore_index=True)


def load_flares(directory: Path | None = None, satellites: tuple[int, ...] = SATELLITES) -> pd.DataFrame:
    """Merged flare list from the downloaded summaries (run ``python -m flinch download`` first)."""
    directory = Path(directory or data_dir() / "goes")
    merged = None
    for satellite in satellites:
        files = sorted(directory.glob(f"sci_xrsf-l2-flsum_g{satellite}_*.nc"))
        if not files:
            raise FileNotFoundError(
                f"no GOES-{satellite} flare summary in {directory}; run `python -m flinch download`"
            )
        flares = read_flsum(files[-1])
        locations = sorted(directory.glob(f"sci_xrsf-l2-flloc_g{satellite}_*.nc"))
        if locations:
            flares = flares.merge(read_flloc(locations[-1]), on="flare_id", how="left")
        merged = flares if merged is None else merge_flare_lists(merged, flares)
    # The lists are reissued with a later end date: keep the same flares whatever the download.
    merged = merged[merged["jd_peak"] < data_end_jd()].reset_index(drop=True)
    merged["peak"] = jd_to_datetime(merged["jd_peak"])
    return merged


def avg1m_url(satellite: int, year: int) -> str:
    """URL of the yearly file of one-minute X-ray fluxes (the version is read from the listing)."""
    directory = f"{ARCHIVE}/goes{satellite}/l2/data/xrsf-l2-avg1m_science/"
    names = re.findall(rf'href="(sci_xrsf-l2-avg1m_g{satellite}_y{year}_v[\d-]+\.nc)"', fetch_text(directory))
    if not names:
        raise RuntimeError(f"no one-minute file of GOES-{satellite} for {year}")
    return directory + sorted(names)[-1]


def load_avg1m(satellite: int, year: int, directory: Path | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Julian dates and 1-8 Angstrom fluxes (W m^-2) at one-minute cadence; downloaded if missing."""
    directory = Path(directory or data_dir() / "goes")
    files = sorted(directory.glob(f"sci_xrsf-l2-avg1m_g{satellite}_y{year}_*.nc"))
    path = files[-1] if files else download(avg1m_url(satellite, year), directory / avg1m_url(satellite, year).rsplit("/", 1)[-1])
    with h5py.File(path, "r") as handle:
        jd = JD_J2000 + handle["time"][:] / 86400.0
        flux = handle["xrsb_flux"][:].astype(float)
    flux[~(flux > 0.0)] = np.nan  # fill values and gaps
    return jd, flux


def download_avg1m(flares: pd.DataFrame, directory: Path | None = None) -> list[tuple[int, int]]:
    """Download the yearly one-minute files that ``add_impulsive_time`` needs for these flares.

    Returns the (satellite, year) pairs. A year that the archive does not hold is skipped, as
    ``add_impulsive_time`` does.
    """
    years = jd_to_datetime(flares["jd_peak"]).year
    pairs = sorted({(int(satellite), int(year)) for satellite, year in zip(flares["satellite"], years)})
    done = []
    for satellite, year in pairs:
        try:
            load_avg1m(satellite, year, directory)
            done.append((satellite, year))
        except RuntimeError:  # no file for that year
            continue
    return done


def add_impulsive_time(flares: pd.DataFrame, directory: Path | None = None) -> pd.DataFrame:
    """Add ``jd_impulsive``: the time of the steepest rise of the X-ray flux of each flare.

    The time derivative of the soft X-ray flux follows the energy deposition by accelerated
    particles (the Neupert effect), so its maximum marks the impulsive phase better than the
    X-ray peak, which comes minutes later. It is searched between the start and the peak with a
    centred difference over two minutes; flares without one-minute data keep NaN.
    """
    out = flares.copy()
    out["jd_impulsive"] = np.nan
    start = out["jd_start"].fillna(out["jd_peak"] - 10.0 * MINUTE)
    years = jd_to_datetime(out["jd_peak"]).year
    for (satellite, year), rows in out.groupby([out["satellite"], years]):
        try:
            jd, flux = load_avg1m(int(satellite), int(year), directory)
        except Exception:  # noqa: BLE001  (a missing year leaves NaN)
            continue
        slope = np.full(len(flux), np.nan)
        slope[1:-1] = (flux[2:] - flux[:-2]) / 2.0
        for index in rows.index:
            first, last = np.searchsorted(jd, [start[index] - 0.5 * MINUTE, out.at[index, "jd_peak"] + 0.5 * MINUTE])
            if last - first >= 2 and np.any(np.isfinite(slope[first:last])):
                out.at[index, "jd_impulsive"] = jd[first + int(np.nanargmax(slope[first:last]))] + 0.5 * MINUTE
    return out
