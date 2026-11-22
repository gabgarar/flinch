import shutil

import numpy as np
import pandas as pd
import pytest

import helpers


@pytest.fixture
def archive(tmp_path, monkeypatch):
    """A synthetic data directory without any flare signal; results and figures go to the temporary folder."""
    table, flares = helpers.build_archive(tmp_path / "data")
    _redirect(tmp_path, monkeypatch)
    return {"root": tmp_path, "table": table, "flares": flares}


@pytest.fixture
def archive_with_signal(tmp_path, monkeypatch):
    """The same, with 1.5 m/s added to the velocity during every flare."""
    table, flares = helpers.build_archive(tmp_path / "data", signal_ms=1.5)
    _redirect(tmp_path, monkeypatch)
    return {"root": tmp_path, "table": table, "flares": flares}


def _redirect(tmp_path, monkeypatch):
    import flinch.__main__ as cli
    import flinch.campaign as campaign

    monkeypatch.setenv("FLINCH_DATA", str(tmp_path / "data"))
    for module in (cli, campaign):
        monkeypatch.setattr(module, "results_dir", lambda: _made(tmp_path / "results"))
    monkeypatch.setattr(cli, "figures_dir", lambda: _made(tmp_path / "figures"))


def _made(path):
    path.mkdir(parents=True, exist_ok=True)
    return path


@pytest.fixture
def fake_neid(archive, tmp_path, monkeypatch):
    """Serve synthetic spectra for every exposure of the synthetic velocity table, made on demand."""
    remote = tmp_path / "remote"
    remote.mkdir()
    table = archive["table"]
    flare_starts = archive["flares"]["jd_start"].to_numpy()
    served = []

    def list_files(jd_from, jd_to):
        rows = table[(table["obsjd"] >= jd_from) & (table["obsjd"] < jd_to)]
        return pd.DataFrame({"obsjd": rows["obsjd"], "l2filename": rows["l2filename"], "l2filepath": "sci/" + rows["l2filename"]})

    def download(url, destination, overwrite=False):
        name = url.split("filehand=sci/")[1].split("&")[0]
        obsjd = float(table.loc[table["l2filename"] == name, "obsjd"].iloc[0])
        after_a_flare = np.any((obsjd + 27.5 / 86400.0 > flare_starts) & (obsjd < flare_starts + 60 * helpers.MINUTE))
        helpers.write_l2(remote / name, obsjd, halpha=0.21 if after_a_flare else 0.20)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(remote / name, destination)
        served.append(name)
        return destination

    from flinch import campaign, spectra

    monkeypatch.setattr(spectra, "list_files", list_files)
    monkeypatch.setattr(spectra, "download", download)
    monkeypatch.setattr(campaign, "keep_awake", lambda enable: None)
    return served
