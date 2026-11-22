"""Unit tests of what keeps the results reproducible: the last day of data, the fingerprints
of the inputs and of the spectra, the comparison of tables and the check of the paper's numbers."""
import io

import numpy as np
import pandas as pd
import pytest

from flinch import _http, config, goes, inputs, neid, numbers, reproduce, spectra, verify
from flinch.timeutil import MINUTE


def test_the_last_day_of_data_is_fixed_and_can_be_changed(monkeypatch):
    monkeypatch.delenv("FLINCH_DATA_END", raising=False)
    assert config.data_end_jd() == 2461357.5  # 13 November 2026, 00:00 UTC
    monkeypatch.setenv("FLINCH_DATA_END", "2027-01-01")
    assert config.data_end_jd() == 2461406.5
    monkeypatch.setenv("FLINCH_DATA_END", "none")
    assert config.data_end_jd() == float("inf")


def test_flares_and_observations_after_the_last_day_are_ignored(archive, monkeypatch):
    every_flare, every_spectrum = len(goes.load_flares()), len(neid.read_solar_table())
    assert every_spectrum == len(archive["table"])  # the default limit is far after the synthetic archive
    monkeypatch.setenv("FLINCH_DATA_END", "2023-03-17")  # day 20 of the 40 of the archive
    end = config.data_end_jd()
    flares, table = goes.load_flares(), neid.read_solar_table()
    assert 0 < len(flares) < every_flare and flares["jd_peak"].max() < end
    assert len(table) == every_spectrum // 2 and table["obsjd"].max() < end
    monkeypatch.setenv("FLINCH_DATA_END", "none")
    assert len(goes.load_flares()) == every_flare and len(neid.read_solar_table()) == every_spectrum


def test_results_and_figures_can_be_sent_elsewhere(tmp_path, monkeypatch):
    monkeypatch.setenv("FLINCH_RESULTS", str(tmp_path / "tables"))
    monkeypatch.setenv("FLINCH_FIGURES", str(tmp_path / "figures"))
    assert config.results_dir() == tmp_path / "tables" and config.results_dir().is_dir()
    assert config.figures_dir() == tmp_path / "figures" and config.figures_dir().is_dir()


class _Response(io.BytesIO):
    def __init__(self, body: bytes, announced: int):
        super().__init__(body)
        self.headers = {"Content-Length": str(announced)}


def test_a_download_cut_short_is_an_error_and_leaves_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(_http, "open_url", lambda url, *args, **kwargs: _Response(b"12345", 10))
    with pytest.raises(ConnectionError, match="incomplete"):
        _http.download("https://example.org/file", tmp_path / "file")
    assert not list(tmp_path.iterdir())
    monkeypatch.setattr(_http, "open_url", lambda url, *args, **kwargs: _Response(b"12345", 5))
    assert _http.download("https://example.org/file", tmp_path / "file").read_bytes() == b"12345"


def _extract() -> dict:
    return {
        "obsjd": np.float64(2460000.7),
        "ccf": np.arange(5.0),
        "activity_names": np.array(["CaIIHK", "NaI_tellcorr"]),
        "activity_values": np.array([0.2, np.nan]),
        "Halpha_flux": np.arange(4, dtype=np.float32),
    }


def test_the_fingerprint_of_an_extract_follows_what_comes_from_the_file(tmp_path):
    reference = spectra.digest(_extract())
    assert len(reference) == 64
    np.savez_compressed(tmp_path / "extract.npz", **_extract())
    with np.load(tmp_path / "extract.npz") as saved:
        assert spectra.digest(saved) == reference  # the same through a file
    other_sum = _extract() | {"ccf": np.arange(5.0) + 1.0e-12}
    assert spectra.digest(other_sum) == reference  # the sum computed here is left out
    for key, value in (("Halpha_flux", np.arange(4, dtype=np.float32) + 1), ("obsjd", np.float64(2460000.8)), ("activity_names", np.array(["CaIIHK", "NaI"]))):
        assert spectra.digest(_extract() | {key: value}) != reference, key


def test_a_file_without_stitched_spectrum_is_reported_as_such(tmp_path):
    from astropy.io import fits

    import helpers

    path = tmp_path / "neidL2_x.fits"
    helpers.write_l2(path, 2460000.7)
    with fits.open(path) as hdus:
        kept = [hdu for hdu in hdus if hdu.name not in ("SCIWAVESTITCH", "SCIFLUXSTITCH", "SCIVARSTITCH")]
        empty = [fits.ImageHDU(name=name) for name in ("SCIFLUXSTITCH", "SCIVARSTITCH", "SCIWAVESTITCH")]
        fits.HDUList([hdu.copy() for hdu in kept] + empty).writeto(tmp_path / "neidL2_y.fits")
    with pytest.raises(ValueError, match="no stitched spectrum"):
        spectra.extract(tmp_path / "neidL2_y.fits")
    (tmp_path / "neidL2_y.fits").unlink()  # the file is closed: it can be deleted, also on Windows


def test_tables_are_compared_as_text_and_then_as_numbers(tmp_path):
    table = pd.DataFrame({"band": ["M", "X"], "mean": [-0.0345752, 0.5], "flares": [128, 11], "err": [0.03, np.nan]})
    table.to_csv(tmp_path / "old.csv", index=False)
    table.to_csv(tmp_path / "same.csv", index=False)
    assert reproduce.compare_tables(tmp_path / "old.csv", tmp_path / "same.csv") == ("identical", "")
    (tmp_path / "crlf.csv").write_bytes((tmp_path / "old.csv").read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
    assert reproduce.compare_tables(tmp_path / "old.csv", tmp_path / "crlf.csv")[0] == "identical"  # line ends do not count
    table.assign(mean=table["mean"] * (1.0 + 1.0e-13)).to_csv(tmp_path / "close.csv", index=False)
    assert reproduce.compare_tables(tmp_path / "old.csv", tmp_path / "close.csv")[0] == "same numbers"
    table.assign(mean=[-0.0345752, 0.51]).to_csv(tmp_path / "other.csv", index=False)
    verdict, detail = reproduce.compare_tables(tmp_path / "old.csv", tmp_path / "other.csv")
    assert verdict == "DIFFERENT" and detail.startswith("mean (by up to 0.01")
    table.assign(band=["M", "M5-M9"]).to_csv(tmp_path / "label.csv", index=False)
    assert reproduce.compare_tables(tmp_path / "old.csv", tmp_path / "label.csv") == ("DIFFERENT", "band")
    table.assign(err=[np.nan, np.nan]).to_csv(tmp_path / "gap.csv", index=False)
    assert "values missing" in reproduce.compare_tables(tmp_path / "old.csv", tmp_path / "gap.csv")[1]
    table.iloc[:1].to_csv(tmp_path / "short.csv", index=False)
    assert reproduce.compare_tables(tmp_path / "old.csv", tmp_path / "short.csv") == ("DIFFERENT", "2 rows in the repository, 1 now")
    assert reproduce.compare_tables(tmp_path / "old.csv", tmp_path / "absent.csv")[0] == "missing"


def test_a_number_of_the_paper_passes_only_if_it_is_a_correct_rounding():
    checks = verify.Checks()
    checks.add("Appendix C", "excess", (0.44, 0.11), (0.4345, 0.1048), 2)  # rounded twice: wrong
    checks.add("Appendix C", "excess", (0.43, 0.10), (0.4345, 0.1048), 2)
    checks.add("Table 1", "mean change", (-0.035, 0.035), (-0.03457, 0.03488), 3)
    checks.add("Table 1", "flares", 139, 139)
    checks.add("Table 1", "flares", 139, 140)
    checks.add("Table 2", "response", 0.0, -0.021, 1)
    checks.add("Table 2", "response", 5.3, np.nan, 1)
    table = checks.table()
    assert list(table["ok"]) == [False, True, True, True, False, True, False]
    assert table.loc[1, "paper"] == "0.43 +/- 0.10" and table.loc[1, "here"] == "0.4345 +/- 0.1048"
    assert table.loc[5, "paper"] == "0.0" and table.loc[6, "here"] == "missing"


def test_the_tables_of_the_repository_support_every_number_of_the_paper():
    table = verify.run(config.REPO_ROOT / "results")
    assert len(table) > 200
    assert table["ok"].all(), table[~table["ok"]].to_string()
    assert {"Table 1", "Table 2", "Table A.1", "Table B.1", "Appendix C", "Sect. 5.2"} <= set(table["where"])


def test_a_missing_table_fails_the_check_instead_of_passing_unseen(tmp_path):
    table = verify.run(tmp_path)  # an empty folder
    missing = table[table["here"] == "table missing"]
    assert len(missing) >= 3 and not missing["ok"].any()


def test_the_fingerprints_of_the_inputs_notice_a_changed_archive(archive, tmp_path, monkeypatch):
    monkeypatch.setattr(inputs, "reference_dir", lambda: tmp_path / "reference")
    inputs.freeze()
    listed = inputs.reference().set_index("input")
    assert listed.loc["NEID velocity table", "rows"] == len(archive["table"])
    assert listed.loc["GOES list of M and X flares", "rows"] == len(archive["flares"])
    assert "GOES-16 one-minute fluxes of 2023" in listed.index and "GOES-18 one-minute fluxes of 2023" not in listed.index
    assert (inputs.check()["status"] == "identical").all()

    # The archive reprocesses one velocity by 1 mm/s: the table is another, the rest is not.
    path = archive["root"] / "data" / "neid" / "neid_solar_l2.csv.gz"
    table = pd.read_csv(path)
    table.loc[100, "ccfrvmod"] += 1.0e-6
    table.to_csv(path, index=False)
    status = inputs.check().set_index("input")["status"]
    assert status["NEID velocity table"] == "different"
    assert (status.drop("NEID velocity table") == "identical").all()

    # New observations after the last day of data change nothing.
    table.loc[100, "ccfrvmod"] -= 1.0e-6
    later = table.tail(3).assign(obsjd=config.data_end_jd() + np.arange(3.0))
    pd.concat([table, later], ignore_index=True).to_csv(path, index=False)
    assert inputs.check().set_index("input").loc["NEID velocity table", "status"] == "identical"

    next((archive["root"] / "data" / "goes").glob("sci_xrsf-l2-avg1m_g16_*")).unlink()
    assert inputs.check().set_index("input").loc["GOES-16 one-minute fluxes of 2023", "status"] == "missing"


def test_flare_rate_and_time_in_flare():
    first = 2460000.5
    sample = pd.DataFrame(
        {
            "jd_start": first + np.array([10.0, 20.0, 30.0, 400.0]),
            "jd_peak": first + np.array([10.0, 20.0, 30.0, 400.0]) + 10.0 * MINUTE,
            "jd_end": first + np.array([10.0, 20.0, np.nan, 400.0]) + np.array([30.0, 20.0, 0.0, 60.0]) * MINUTE,
            "peak_flux": [2.0e-5, 1.5e-4, 3.0e-5, 5.0e-5],
        }
    )
    out = numbers.flare_statistics(sample, first, first + 730.5)
    assert out["flares"] == 4 and out["flares_x"] == 1 and out["flares_without_end"] == 1
    assert out["span_years"] == pytest.approx(2.0) and out["flares_per_year"] == pytest.approx(2.0)
    # the flare without an end counts up to its peak: 30 + 20 + 10 + 60 minutes
    assert out["time_in_flare_percent"] == pytest.approx(100.0 * 120.0 * MINUTE / 730.5)
    assert out["time_in_x_flare_percent"] == pytest.approx(100.0 * 20.0 * MINUTE / 730.5)
    assert out["median_duration_min"] == pytest.approx(25.0)
    assert out["busiest_year"] == 2023 and out["busiest_year_flares"] == 3 and out["busiest_year_flares_x"] == 1
    assert out["busiest_year_time_in_flare_percent"] == pytest.approx(100.0 * 60.0 * MINUTE / 365.0)


def test_kolmogorov_smirnov_probability():
    rng = np.random.default_rng(0)
    everything = rng.normal(size=2000)
    assert numbers.ks_p(everything[::10], everything) > 0.2  # a fair sample
    assert numbers.ks_p(np.sort(everything)[-200:], everything) < 1.0e-6  # only the largest
    assert numbers.ks_p([0.1, np.nan, 0.5, 0.3], [0.2, 0.4, np.nan]) > 0.1  # missing positions are left out
