"""Fingerprints of the input data, to tell whether a download holds the data of the paper.

The archives are alive. The NEID table grows and can be reprocessed with a newer pipeline, and
the GOES files are reissued. ``DATA_END`` in ``config`` removes the growth; a fingerprint
(SHA-256) of what the analysis reads up to that date detects the rest. If a result differs
from the paper and a fingerprint differs too, the archive has changed; if every fingerprint
agrees, the difference is in the code or in the software around it.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

import h5py
import numpy as np
import pandas as pd

from . import goes, harpsn, neid, pilot
from .config import data_dir, data_end_jd, reference_dir
from .timeutil import JD_J2000, jd_to_datetime

REFERENCE = "inputs.csv"
# Columns of the NEID table that the analysis reads, with the decimals kept in the fingerprint.
# They are read from text, so they are rounded to integers first: the last binary digit of a
# parsed number can depend on the version of the reader.
NEID_DECIMALS = {"obsjd": 8, "exptime": 3, "ccfrvmod": 9, "dvrms": 9, "extsnr": 4}
FLARE_COLUMNS = ("jd_start", "jd_peak", "jd_end", "peak_flux", "fluence", "satellite", "x_norm", "y_norm", "lon", "lat", "car_lon")


def _sha(parts) -> str:
    sha = hashlib.sha256()
    for part in parts:
        sha.update(part)
    return sha.hexdigest()


def _binary(values) -> bytes:
    """Bytes of an array of numbers that were read from a binary file (exact on any machine)."""
    return np.ascontiguousarray(np.asarray(values, dtype="<f8")).tobytes()


def _rounded(values, decimals: int) -> bytes:
    """Bytes of an array of numbers read from text, as integers of ``decimals`` decimals (missing: lowest integer)."""
    scaled = np.round(np.asarray(values, dtype=float) * 10.0**decimals)
    whole = np.where(np.isfinite(scaled), scaled, np.iinfo(np.int64).min).astype("<i8")
    return np.ascontiguousarray(whole).tobytes()


def flare_list() -> dict:
    """The merged list of M and X flares up to ``DATA_END``: times, fluxes and positions."""
    flares = goes.load_flares()
    flares = flares[flares["goes_class"].str[0].isin(["M", "X"])]  # the classes that the analysis uses
    parts = [_binary(flares[column]) for column in FLARE_COLUMNS if column in flares]
    parts.append("\n".join(flares["goes_class"]).encode("ascii"))
    return {"input": "GOES list of M and X flares", "rows": len(flares), "sha256": _sha(parts)}


def neid_table() -> dict:
    """The NEID velocity table up to ``DATA_END``: the columns that the analysis reads."""
    table = neid.read_solar_table()
    parts = [_rounded(table[column], decimals) for column, decimals in NEID_DECIMALS.items()]
    return {"input": "NEID velocity table", "rows": len(table), "sha256": _sha(parts)}


def harpsn_series() -> dict:
    """The HARPS-N release, a fixed file: its bytes."""
    path = harpsn.series_path()
    sha = hashlib.sha256()
    rows = -1  # the header
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            sha.update(block)
            rows += block.count(b"\n")
    return {"input": "HARPS-N series", "rows": rows, "sha256": sha.hexdigest()}


def one_minute_fluxes() -> list[dict]:
    """Each yearly file of one-minute X-ray fluxes that the analysis reads, up to ``DATA_END``.

    They are the years, by satellite, of the M and X flares of the NEID era.
    """
    sample = pilot.major_flare_sample(goes.load_flares(), neid.read_solar_table()["obsjd"].to_numpy())
    needed = set(zip(sample["satellite"].astype(int), jd_to_datetime(sample["jd_peak"]).year))
    out = []
    end = data_end_jd()
    for path in sorted((data_dir() / "goes").glob("sci_xrsf-l2-avg1m_g*_y*_v*.nc")):
        satellite, year = re.search(r"_g(\d\d)_y(\d{4})_", path.name).groups()
        if (int(satellite), int(year)) not in needed:
            continue
        with h5py.File(path, "r") as handle:
            jd = JD_J2000 + handle["time"][:] / 86400.0
            flux = handle["xrsb_flux"][:].astype(float)
        keep = jd < end
        out.append(
            {"input": f"GOES-{satellite} one-minute fluxes of {year}", "rows": int(keep.sum()), "sha256": _sha([_binary(jd[keep]), _binary(flux[keep])])}
        )
    return out


def fingerprints() -> pd.DataFrame:
    """Fingerprint of every input on disk: name, rows used and SHA-256 of their content."""
    rows = [flare_list(), neid_table()]
    if harpsn.series_path().exists():
        rows.append(harpsn_series())
    rows += one_minute_fluxes()
    return pd.DataFrame(rows)


def reference() -> pd.DataFrame:
    """The fingerprints of the data used in the paper."""
    return pd.read_csv(reference_dir() / REFERENCE)


def check() -> pd.DataFrame:
    """Compare the inputs on disk with those of the paper.

    One row per input of the paper, with ``status``: "identical", "different" or "missing".
    Inputs on disk that the paper did not use (other years of one-minute fluxes) are left out.
    """
    here = fingerprints().set_index("input")
    rows = []
    for row in reference().itertuples():
        if row.input not in here.index:
            status, found = "missing", np.nan
        else:
            found = int(here.at[row.input, "rows"])
            status = "identical" if here.at[row.input, "sha256"] == row.sha256 else "different"
        rows.append({"input": row.input, "rows_paper": row.rows, "rows_here": found, "status": status})
    return pd.DataFrame(rows)


def freeze(path: Path | None = None) -> Path:
    """Write the fingerprints of the data on disk as the reference. Run by the author when the sample of the paper was closed."""
    path = Path(path or reference_dir() / REFERENCE)
    path.parent.mkdir(parents=True, exist_ok=True)
    fingerprints().to_csv(path, index=False, lineterminator="\n")
    return path
