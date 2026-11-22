"""Integration: the fixed list of spectra, the numbers of the text and the whole reproduction
on the synthetic archive.

The synthetic archive is not the data of the paper, so the reproduction has to say so: every
step that can run does run, the new tables differ from those of the repository, and the
numbers of the paper are not found.
"""
import re
import shutil

import numpy as np
import pandas as pd
import pytest

import helpers
from flinch import campaign, numbers, reproduce, spectra
from flinch.__main__ import main


def test_the_spectra_of_the_paper_are_fetched_as_listed_and_checked(archive, fake_neid, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(campaign, "reference_dir", lambda: tmp_path / "reference")
    monkeypatch.setattr(campaign.time, "sleep", lambda seconds: None)
    root = archive["root"] / "data" / "spectra"

    # 1. A campaign as the author ran it; what it fetched becomes the list of the paper.
    campaign.run(hours=1.0, max_files=30, step=3, workers=2)
    campaign.freeze_paper_spectra()
    listed = campaign.paper_files()
    assert len(listed) == 30 and list(listed.columns) == ["name", "file", "obsjd", "swversion", "sha256"]
    assert (listed["swversion"] == "v1.5.3").all() and listed["sha256"].str.len().eq(64).all()
    assert set(listed["name"]) <= set(campaign.paper_windows()["name"])

    # 2. From an empty folder exactly those files come back, each identical to the one listed.
    shutil.rmtree(root)
    fake_neid.clear()
    checked = campaign.fetch_paper_spectra(workers=2)
    assert (checked["status"] == "identical").all()
    assert sorted(fake_neid) == sorted(listed["file"])
    assert pd.read_csv(root / "events.csv").equals(campaign.paper_windows())
    assert len(pd.read_csv(root / "check.csv")) == 30
    assert reproduce.spectra_complete()

    # 3. Run again: nothing is downloaded, everything is checked.
    fake_neid.clear()
    assert (campaign.fetch_paper_spectra(workers=2)["status"] == "identical").all() and fake_neid == []

    # 4. A sample: only that many files, the same ones for the same seed.
    shutil.rmtree(root)
    fake_neid.clear()
    assert main(["paper-spectra", "--sample", "4", "--workers", "2"]) == 0
    assert len(fake_neid) == 4 and "identical: 4" in capsys.readouterr().out
    assert not reproduce.spectra_complete()
    first = sorted(fake_neid)
    shutil.rmtree(root)
    fake_neid.clear()
    campaign.fetch_paper_spectra(sample=4, workers=2)
    assert sorted(fake_neid) == first

    # 5. The archive changes: one spectrum is another, one is gone, one download keeps failing.
    shutil.rmtree(root)
    changed, gone, broken = listed["file"].iloc[2], "neidL2_999999.fits", listed["file"].iloc[7]
    edited = listed.copy()
    edited.loc[2, "sha256"] = "0" * 64
    edited.loc[len(edited)] = {"name": listed["name"].iloc[0], "file": gone, "obsjd": listed["obsjd"].iloc[0] + 1.0e-5, "swversion": "v1.5.3", "sha256": "1" * 64}
    edited.to_csv(tmp_path / "reference" / "spectra_files.csv", index=False)
    good_download = spectra.download

    def flaky(url, destination, overwrite=False):
        if broken in url:
            raise ConnectionError("connection dropped")
        return good_download(url, destination, overwrite)

    monkeypatch.setattr(spectra, "download", flaky)
    status = campaign.fetch_paper_spectra(workers=2, rounds=2).set_index("file")["status"]
    assert status[changed] == "different" and status[gone] == "not in the archive" and status[broken] == "failed"
    assert (status.drop([changed, gone, broken]) == "identical").all()
    assert main(["paper-spectra", "--workers", "2"]) == 1  # a failed download: run again
    monkeypatch.setattr(spectra, "download", good_download)
    assert main(["paper-spectra", "--workers", "2"]) == 2  # complete, but not the spectra of the paper
    assert "different: " in capsys.readouterr().out


def test_the_numbers_of_the_text_on_the_synthetic_archive(archive):
    helpers.write_harpsn(archive["root"] / "data", archive["flares"])
    table = numbers.run()
    assert list(table.columns) == ["group", "quantity", "value"] and not table.duplicated(["group", "quantity"]).any()
    value = table.set_index(["group", "quantity"])["value"]
    flares = archive["flares"]
    assert value[("NEID", "velocities")] == len(archive["table"])
    assert value[("NEID", "days_with_data")] == 40 and value[("NEID", "days_dropped_percent")] == 0.0
    assert value[("NEID", "scatter_of_one_velocity_ms")] == pytest.approx(0.6, rel=0.15)
    assert value[("NEID", "flares_in_era")] == len(flares) == value[("flares", "flares")]
    assert value[("NEID", "flares_with_complete_windows")] == len(flares)  # every flare is observed in full
    assert value[("NEID", "flares_at_peak")] == len(flares)
    assert value[("NEID", "flares_at_peak_on_dropped_days_percent")] == 0.0
    assert value[("NEID", "injection_efficiency")] == pytest.approx(1.0, abs=0.1)
    assert value[("NEID", "strongest_flare_class")] == pytest.approx(1.5)
    for instrument in ("NEID", "HARPS-N"):
        probabilities = value[[(instrument, f"ks_p_{label}") for _, label in numbers.KS_COLUMNS]]
        assert ((probabilities > 0.5) & (probabilities <= 1.0)).all()  # the flares measured are all of them
    assert value[("flares", "flares_x")] == (flares["peak_flux"] >= 1.0e-4).sum()
    assert value[("flares", "median_duration_min")] == pytest.approx(30.0)
    assert value[("flares", "flares_without_end")] == 0
    assert value[("both", "flares_in_both")] == value[("HARPS-N", "flares_with_complete_windows")] > 0
    assert np.isnan(value[("flares", "strongest_class_2017-09-06")])  # no such day in the synthetic list


def test_reproduce_runs_every_step_and_reports_what_differs(archive, tmp_path):
    helpers.write_harpsn(archive["root"] / "data", archive["flares"])
    out = tmp_path / "reproduction"
    assert reproduce.run(download=False, out=out) == 1  # synthetic data: not the paper
    report = (out / "report.txt").read_text(encoding="utf-8")
    for command in reproduce.VELOCITY_STEPS:
        line = next(line for line in report.splitlines() if line.strip().startswith(command + " "))
        assert " done " in line, line
    for name in reproduce.VELOCITY_TABLES:
        assert (out / "results" / name).exists(), name
    assert re.search(r"NEID velocity table\s+different", report)  # the inputs are not those of the paper
    assert re.search(r"velocity_by_instrument\.csv\s+DIFFERENT", report)
    assert "spectral analysis not repeated" in report and re.search(r"spectral_response\.csv\s+not recomputed", report)
    assert "NOT IN AGREEMENT  Table 1" in report and "Not fully reproduced" in report
    assert (out / "logs" / "replication.txt").read_text(encoding="utf-8").strip()
    assert (out / "results" / "paper_check.csv").exists() and (out / "site_figures" / "pilot_profiles.png").exists()
    # The new tables are those of the synthetic archive, written apart from the tables of the repository.
    new = pd.read_csv(out / "results" / "velocity_by_instrument.csv").set_index(["instrument", "band"])
    assert new.loc[("NEID", "M and X"), "flares"] == len(archive["flares"])
