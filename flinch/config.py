"""Locations of data and results."""
from __future__ import annotations

import datetime as dt
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
# Last day of data, exclusive (UTC). The NEID table grows every clear day and the GOES lists are
# reissued with a later end, so without a limit the sample of the paper would change with the
# date of the download. Flares and observations from this day on are ignored. The last NEID
# observation in the table downloaded for the paper is of 12 November 2026.
DATA_END = "2026-11-13"


def data_end_jd() -> float:
    """Julian date (UTC) from which flares and observations are ignored.

    ``DATA_END`` by default. The environment variable ``FLINCH_DATA_END`` replaces it with
    another date (``2027-06-01``) or lifts the limit (``none``), to extend the study; the
    numbers of the paper are then no longer reproduced.
    """
    text = os.environ.get("FLINCH_DATA_END", DATA_END).strip()
    if text.lower() in ("", "none"):
        return float("inf")
    since_1970 = dt.datetime.fromisoformat(text) - dt.datetime(1970, 1, 1)
    return since_1970.total_seconds() / 86400.0 + 2440587.5


def reference_dir() -> Path:
    """Tables that fix what the paper used: the spectra fetched and the fingerprints of the inputs."""
    return Path(__file__).resolve().parent / "reference"


def data_dir() -> Path:
    """Directory for downloaded data: ``$FLINCH_DATA`` if set, otherwise ``<repo>/data``.

    The flare lists and the velocity table are a few tens of MB. Spectra are much heavier:
    point ``FLINCH_DATA`` to a folder outside any cloud-synchronised directory before
    downloading them.
    """
    path = Path(os.environ.get("FLINCH_DATA", REPO_ROOT / "data"))
    path.mkdir(parents=True, exist_ok=True)
    return path


def figures_dir() -> Path:
    """Directory of the figures, inside the documentation site."""
    path = REPO_ROOT / "docs" / "web" / "img"
    path.mkdir(parents=True, exist_ok=True)
    return path


def results_dir() -> Path:
    """Directory for small derived tables that are kept under version control."""
    path = REPO_ROOT / "results"
    path.mkdir(parents=True, exist_ok=True)
    return path
