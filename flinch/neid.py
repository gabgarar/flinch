"""Sun-as-a-star radial velocities from the public NEID solar archive (TAP service, no login)."""
from __future__ import annotations

import datetime as dt
import io
from pathlib import Path

import pandas as pd

from ._http import fetch_text
from .config import data_dir, data_end_jd
from .timeutil import year_start_jd

TAP_SYNC = "https://neid.ipac.caltech.edu/TAP/sync"
SOLAR_TABLE = "neidsolarl2"
FIRST_YEAR = 2020  # first solar spectra: December 2020
# obsjd: Julian date (UTC) of the observation; ccfrvmod: radial velocity in km/s; dvrms: its
# photon-limited uncertainty in km/s. ccfjdsum is in a different time frame (about 7 minutes
# earlier than obsjd) and must not be compared with flare times recorded at the Earth.
COLUMNS = (
    "obsjd", "exptime", "ccfrvmod", "dvrms", "extsnr", "sunagl", "airmass",
    "rejected", "flagged", "swversion", "l2filename",
)


def parse_csv(text: str, expected_column: str) -> pd.DataFrame:
    """Parse a CSV answer of the archive; raise if it is an error message instead of a table."""
    header = [name.strip().strip('"').lower() for name in text.split("\n", 1)[0].split(",")]
    if expected_column.lower() not in header:
        raise RuntimeError(f"unexpected answer from the NEID archive: {text[:300]!r}")
    return pd.read_csv(io.StringIO(text), low_memory=False)


def query(adql: str, expected_column: str) -> pd.DataFrame:
    """Run an ADQL query on the NEID archive and return the result as a table."""
    return parse_csv(fetch_text(TAP_SYNC, {"query": adql, "format": "csv"}), expected_column)


def download_solar_table(
    destination: Path | None = None, last_year: int | None = None, overwrite: bool = False
) -> Path:
    """Download the table of all solar observations (one query per year); returns the local path."""
    destination = Path(destination or data_dir() / "neid" / "neid_solar_l2.csv.gz")
    if destination.exists() and not overwrite:
        return destination
    last_year = last_year or dt.datetime.now(dt.timezone.utc).year
    end = data_end_jd()  # the table grows every clear day: nothing is asked beyond the last day of data
    columns = ", ".join(COLUMNS)
    chunks = []
    for year in range(FIRST_YEAR, last_year + 1):
        first, last = year_start_jd(year), min(year_start_jd(year + 1), end)
        if first >= last:
            break
        adql = f"select {columns} from {SOLAR_TABLE} where obsjd >= {first} and obsjd < {last} order by obsjd"
        chunks.append(query(adql, "obsjd"))
    table = pd.concat([chunk for chunk in chunks if not chunk.empty], ignore_index=True)
    destination.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(destination, index=False)
    return destination


def read_solar_table(path: Path | None = None) -> pd.DataFrame:
    """Read the downloaded table, sorted in time, with the velocity also in m/s (``rv_ms``)."""
    path = Path(path or data_dir() / "neid" / "neid_solar_l2.csv.gz")
    if not path.exists():
        raise FileNotFoundError(f"{path} not found; run `python -m flinch download`")
    table = pd.read_csv(path, low_memory=False)
    table = table[table["obsjd"] < data_end_jd()].sort_values("obsjd", ignore_index=True)
    table["rv_ms"] = table["ccfrvmod"] * 1000.0
    table["rv_err_ms"] = table["dvrms"] * 1000.0
    return table
