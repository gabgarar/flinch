"""Integration against the real downloads and the real archives.

``needs_data`` tests run only when ``python -m flinch download`` has been run (into ``data/``,
or into the folder that ``FLINCH_DATA`` names); they check that the committed tables are reproduced. ``network`` tests are excluded by default
(run them with ``pytest -m network``): they check that the archives still answer as the code expects.
"""
import os
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from flinch import config, goes, neid, pilot

DATA = Path(os.environ.get("FLINCH_DATA", config.REPO_ROOT / "data"))
HAVE_DATA = (DATA / "neid" / "neid_solar_l2.csv.gz").exists() and any((DATA / "goes").glob("sci_xrsf-l2-flsum_g16_*.nc"))
needs_data = pytest.mark.skipif(not HAVE_DATA, reason="real data not downloaded: python -m flinch download")


@pytest.mark.needs_data
@needs_data
def test_real_flare_list_has_the_known_flares():
    flares = goes.load_flares()
    assert len(flares) > 20000
    biggest = flares[(flares["peak"] > "2024-05-14") & (flares["peak"] < "2024-05-15")].sort_values("peak_flux").iloc[-1]
    assert biggest["goes_class"].startswith("X8") and f"{biggest['peak']:%H:%M}" == "16:51"
    assert biggest["r_norm"] == pytest.approx(1.0, abs=0.05)  # at the west limb
    assert biggest["x_norm"] > 0.8
    major = flares[flares["goes_class"].str[0].isin(["M", "X"])]
    assert (major["r_norm"] < 1.05).mean() > 0.95


@pytest.mark.needs_data
@needs_data
def test_real_velocity_table_is_as_documented():
    table = neid.read_solar_table()
    assert len(table) == 366180 and table["obsjd"].is_monotonic_increasing  # fixed by the last day of data
    assert table["rv_ms"].median() == pytest.approx(-645.0, abs=5.0)
    assert np.median(table["exptime"]) == pytest.approx(55.0, abs=0.1)
    assert (table["rejected"] == 0).all()


@pytest.mark.needs_data
@needs_data
def test_pilot_reproduces_the_committed_summary():
    committed_path = config.REPO_ROOT / "results" / "pilot_summary.csv"
    if not committed_path.exists():
        pytest.skip("no committed summary")
    committed = pd.read_csv(committed_path).set_index("band")
    summary = pilot.run()["summary"].set_index("band")
    assert (summary["n_flares"] == committed["n_flares"]).all()
    assert np.allclose(summary["difference"], committed["difference"], atol=1e-6)
    assert np.allclose(summary["error"], committed["error"], atol=1e-6)
    assert abs(summary.loc["all", "difference"]) < 3 * summary.loc["all", "error"]  # the published null result


@pytest.mark.network
def test_neid_archive_answers_with_the_expected_columns():
    columns = ", ".join(neid.COLUMNS)
    table = neid.query(f"select top 2 {columns} from {neid.SOLAR_TABLE}", "obsjd")
    assert len(table) == 2 and set(neid.COLUMNS) <= set(table.columns)


@pytest.mark.network
def test_goes_archive_lists_the_mission_long_files():
    for product in goes.PRODUCTS:
        url = goes.find_product_url(18, product)
        assert url.endswith(".nc") and f"xrsf-l2-{product}_science" in url
