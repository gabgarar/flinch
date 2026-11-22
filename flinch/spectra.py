"""Activity indices, cross-correlation functions and line windows from NEID solar spectra.

A level-2 file is 113 MB and the archive does not serve byte ranges, so every spectrum has to
be downloaded whole. Only a compact extract (about 0.2 MB) is kept; the file itself is deleted.
"""
from __future__ import annotations

import hashlib
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

from . import neid
from ._http import download
from .config import data_dir

FILE_URL = "https://neid.ipac.caltech.edu/get_file.php"
# Wavelength windows kept from the stitched spectrum (vacuum wavelengths in Angstrom, observer frame).
LINE_WINDOWS = {
    "CaII_HK": (3928.0, 3976.0),  # Ca II K 3934.78 and H 3969.59
    "Hbeta": (4856.0, 4869.0),  # 4862.68
    "MgI_b": (5165.0, 5187.0),  # b4 5168.9, b2 5174.13, b1 5185.05
    "HeI_D3_NaI_D": (5870.0, 5902.0),  # He I D3 5877.25, Na I D2 5891.58 and D1 5897.56
    "Halpha": (6556.0, 6573.0),  # 6564.61
    "CaII_8542": (8538.0, 8551.0),  # 8544.44
}
HEADER_KEYS = ("OBSJD", "EXPTIME", "SUNAGL", "AIRMASS")
CCF_KEYS = ("CCFRVMOD", "DVRMSMOD", "CCFSTART", "CCFSTEP")


def list_files(jd_from: float, jd_to: float) -> pd.DataFrame:
    """Level-2 solar files with an exposure starting in [jd_from, jd_to)."""
    adql = (
        f"select obsjd, l2filename, l2filepath from {neid.SOLAR_TABLE} "
        f"where obsjd >= {jd_from:.6f} and obsjd < {jd_to:.6f} order by obsjd"
    )
    return neid.query(adql, "l2filepath")


def extract(path: Path) -> dict[str, np.ndarray]:
    """Compact extract of a level-2 file, as a dictionary of arrays ready for ``numpy.savez``.

    Keys: the header values in ``HEADER_KEYS`` and ``CCF_KEYS`` (lower case); ``activity_names``,
    ``activity_values`` and ``activity_errors`` (the indices computed by the NEID pipeline);
    ``ccf`` (sum over orders of the cross-correlation function, on the velocity grid
    ``ccfstart + ccfstep * i`` km/s); and for each window in ``LINE_WINDOWS`` the arrays
    ``<name>_wave``, ``<name>_flux`` and ``<name>_var``.
    """
    from astropy.io import fits  # optional dependency ("analysis" extra)

    out: dict[str, np.ndarray] = {}
    with fits.open(path, memmap=True) as hdus:
        primary = hdus[0].header
        for key in HEADER_KEYS:
            out[key.lower()] = np.float64(primary.get(key, np.nan))
        ccf_header = hdus["CCFS"].header
        for key in CCF_KEYS:
            out[key.lower()] = np.float64(ccf_header.get(key, np.nan))
        out["ccf"] = np.nansum(np.asarray(hdus["CCFS"].data, dtype=float), axis=0)
        activity = hdus["ACTIVITY"].data
        out["activity_names"] = np.array([str(name).strip() for name in activity["INDEX"]])
        out["activity_values"] = np.asarray(activity["VALUE"], dtype=float)
        out["activity_errors"] = np.asarray(activity["UNCERTAINTY"], dtype=float)
        wave = np.asarray(hdus["SCIWAVESTITCH"].data, dtype=float)
        flux = hdus["SCIFLUXSTITCH"].data
        variance = hdus["SCIVARSTITCH"].data
        for name, (low, high) in LINE_WINDOWS.items():
            first, last = np.searchsorted(wave, [low, high])
            out[f"{name}_wave"] = wave[first:last]
            out[f"{name}_flux"] = np.asarray(flux[first:last], dtype=np.float32)
            out[f"{name}_var"] = np.asarray(variance[first:last], dtype=np.float32)
    return out


def digest(arrays) -> str:
    """Fingerprint of an extract: SHA-256 of everything that is copied from the level-2 file.

    Two extracts of the same file have the same fingerprint on any machine, so it tells whether
    the archive still serves the spectrum that was used. ``ccf`` is left out: it is a sum over
    orders computed here, and its last digits can depend on the numerical library.
    """
    sha = hashlib.sha256()
    for key in sorted(arrays.keys() if hasattr(arrays, "keys") else arrays.files):
        if key == "ccf":
            continue
        value = np.asarray(arrays[key])
        if value.dtype.kind in "US":
            content = "\n".join(str(item) for item in value.ravel()).encode("utf-8")
        else:
            content = np.ascontiguousarray(value.astype(value.dtype.newbyteorder("<"))).tobytes()
        sha.update(f"{key}:{value.dtype.kind}{value.dtype.itemsize}:{value.shape}:".encode("ascii"))
        sha.update(content)
    return sha.hexdigest()


def _retry(action, attempts: int = 8, wait_s: float = 1.5):
    """Run ``action``, retrying while Windows reports the file in use (antivirus, indexer, sync)."""
    for attempt in range(attempts):
        try:
            return action()
        except PermissionError:
            if attempt == attempts - 1:
                raise
            time.sleep(wait_s)


def fetch_one(filepath: str, filename: str, directory: Path, scratch: Path) -> Path:
    """Download one level-2 file, save its extract in ``directory`` and delete the file."""
    destination = directory / (Path(filename).stem + ".npz")
    if destination.exists():
        return destination
    raw = _retry(lambda: download(f"{FILE_URL}?filehand={filepath}&solar", scratch / filename, overwrite=True), attempts=3)
    try:
        arrays = extract(raw)
        partial = destination.with_name(destination.stem + ".part.npz")  # savez needs the .npz suffix
        np.savez_compressed(partial, **arrays)
        _retry(lambda: partial.replace(destination))
    finally:
        _retry(lambda: raw.unlink(missing_ok=True))
    return destination


def fetch_window(jd_from: float, jd_to: float, name: str, workers: int = 3, step: int = 1) -> Path:
    """Fetch the extracts of every solar spectrum in a time window; returns their directory.

    Extracts go to ``<data>/spectra/<name>/``. Files already extracted are skipped, so an
    interrupted run can simply be repeated. A file that fails is reported and left for a rerun.
    With ``step`` = n only every n-th spectrum is fetched: a quick first pass at lower cadence,
    which a later run with a smaller step completes.
    """
    directory = data_dir() / "spectra" / name
    directory.mkdir(parents=True, exist_ok=True)
    files = list_files(jd_from, jd_to).iloc[::step]
    scratch = Path(tempfile.gettempdir()) / "flinch_spectra"
    scratch.mkdir(parents=True, exist_ok=True)

    def task(row) -> str | None:
        try:
            fetch_one(row.l2filepath, row.l2filename, directory, scratch)
            return None
        except Exception as exc:  # noqa: BLE001  (reported; the rest of the window goes on)
            return f"{row.l2filename}: {type(exc).__name__}: {exc}"

    with ThreadPoolExecutor(max_workers=workers) as pool:
        failures = [message for message in pool.map(task, files.itertuples()) if message]
    done = len(list(directory.glob("neidL2_*.npz")))
    print(f"{name}: {done} of {len(files)} spectra extracted in {directory}", flush=True)
    for message in failures:
        print(f"  failed  {message}", flush=True)
    return directory


def load_window(directory: Path) -> tuple[pd.DataFrame, dict[str, np.ndarray]]:
    """Read the extracts of a window.

    Returns a table with one row per spectrum (time, velocity, every activity index and its
    error as ``<index>_err``) and a dictionary with the stacked arrays: ``ccf`` and, for each
    line window, ``<name>_wave``, ``<name>_flux`` and ``<name>_var`` (spectra along the first axis,
    truncated to the shortest window, whose length can differ by a pixel between spectra).
    """
    rows, arrays = [], {}
    for path in sorted(Path(directory).glob("neidL2_*.npz")):
        with np.load(path, allow_pickle=False) as data:
            row = {"file": path.stem, "obsjd": float(data["obsjd"])}
            row["jd"] = row["obsjd"] + 0.5 * float(data["exptime"]) / 86400.0
            row["rv_ms"] = float(data["ccfrvmod"]) * 1000.0
            row["sunagl"] = float(data["sunagl"])
            for index, value, error in zip(data["activity_names"], data["activity_values"], data["activity_errors"]):
                row[str(index)] = float(value)
                row[f"{index}_err"] = float(error)
            rows.append(row)
            for key in data.files:
                if key == "ccf" or key.endswith(("_wave", "_flux", "_var")):
                    arrays.setdefault(key, []).append(np.asarray(data[key], dtype=float))
    stacked = {}
    for key, values in arrays.items():
        length = min(len(v) for v in values)
        stacked[key] = np.vstack([v[:length] for v in values])
    return pd.DataFrame(rows), stacked
