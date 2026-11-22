"""Integration: from a fake NEID archive of spectra to the joint chromospheric analysis.

Synthetic level-2 files are served by a fake archive for the strongest flare of the synthetic
sample and for its control day. The H alpha index is 5 % higher after the start of the flare
and constant in the control; the chain has to fetch, extract, filter and measure that.
"""
import shutil

import numpy as np
import pandas as pd
import pytest

import helpers
from flinch import campaign, chromosphere, spectra
from flinch.timeutil import MINUTE


def test_campaign_fetches_flares_then_controls_and_the_analysis_measures_them(archive, fake_neid, capsys):
    root = archive["root"] / "data" / "spectra"
    strongest = campaign.select_events().iloc[0]
    name = campaign.event_name(strongest)

    # 1. Flare campaign with a budget that covers the strongest flare and a few spectra of the next.
    campaign.run(hours=1.0, max_files=45, step=3, workers=2)
    extracts = sorted((root / name).glob("neidL2_*.npz"))
    assert 30 <= len(extracts) <= 45
    assert len(fake_neid) == 45  # the budget is used up, not exceeded
    assert len(set(fake_neid)) == len(fake_neid)  # nothing downloaded twice
    assert not list((archive["root"] / "data").rglob("*.fits"))  # the raw files are not kept in the data folder
    manifest = pd.read_csv(root / "events.csv")
    assert manifest.loc[0, "name"] == name and manifest.loc[0, "kind"] == "flares"

    # 2. Running it again with the same budget fetches the next flare, not the same spectra.
    before = len(fake_neid)
    campaign.run(hours=1.0, max_files=45, step=3, workers=2)
    assert len(sorted((root / name).glob("neidL2_*.npz"))) == len(extracts)
    assert len(fake_neid) > before

    # 3. Control campaign: the same window on a flare-free day, for the flares that have spectra.
    campaign.run(hours=1.0, max_files=200, step=3, workers=2, kind="controls")
    controls = [p.name for p in root.iterdir() if "control" in p.name]
    assert any(c.startswith(name) for c in controls)
    assert "controls" in set(pd.read_csv(root / "events.csv")["kind"])
    capsys.readouterr()

    # 4. Stacked light curves: the step appears at the start of the flare and not in the control.
    curves = chromosphere.light_curves(min_class="M1.0")
    halpha = curves[curves["quantity"] == "Ha06_1_tellcorr"].set_index(["group", "minutes"])["mean"]
    assert halpha.xs("disc flares").loc[5.0:].dropna().to_numpy() == pytest.approx(50.0, abs=0.01)
    assert halpha.xs("disc flares").loc[:-25.0].dropna().abs().max() < 0.01
    assert halpha.xs("controls").dropna().abs().max() < 0.01

    # 5. Joint analysis: the flare shows the 5 % step (50 parts per thousand); its control shows nothing.
    out = chromosphere.run()
    events = out["events"].set_index("name")
    flare = events.loc[name]
    assert flare["usable"] and flare["kind"] == "flare"
    assert flare["Ha06_1_tellcorr"] == pytest.approx(50.0, abs=0.01)
    assert flare["Ha06_1_tellcorr_err"] < 1.0  # noiseless spectra: the step is far above its error
    assert abs(flare["CaI_1_tellcorr"]) < 1e-6 and abs(flare["rv_ms"]) < 1e-6
    control = events[events.index.str.startswith(name + "_control")].iloc[0]
    assert control["kind"] == "control" and control["usable"]
    assert abs(control["Ha06_1_tellcorr"]) < 1e-6
    assert out["numbers"]["flares_usable"] >= 1 and out["numbers"]["controls_usable"] >= 1
    halpha = out["indices"].set_index("index").loc["H alpha core"]
    assert halpha["disc_mean"] == pytest.approx(50.0, abs=0.01) and halpha["control_mean"] == pytest.approx(0.0, abs=1e-6)


def test_fetch_window_reports_failures_and_can_be_repeated(archive, fake_neid, monkeypatch, capsys):
    table = archive["table"]
    jd_from, jd_to = float(table["obsjd"].iloc[10]), float(table["obsjd"].iloc[22])
    broken = table["l2filename"].iloc[15]
    good_download = spectra.download

    def flaky(url, destination, overwrite=False):
        if broken in url:
            raise ConnectionError("connection dropped")
        return good_download(url, destination, overwrite)

    monkeypatch.setattr(spectra, "download", flaky)
    directory = spectra.fetch_window(jd_from, jd_to, "window", workers=2)
    assert len(list(directory.glob("neidL2_*.npz"))) == 11  # twelve spectra, one failed
    assert "failed" in capsys.readouterr().out
    monkeypatch.setattr(spectra, "download", good_download)
    spectra.fetch_window(jd_from, jd_to, "window", workers=2)
    assert len(list(directory.glob("neidL2_*.npz"))) == 12  # the rerun fetches only the missing one
    assert fake_neid.count(broken) == 1


def test_clear_only_campaign_leaves_out_cloudy_flares_and_cloudy_spectra(archive, fake_neid, monkeypatch, capsys):
    from flinch import quality

    root = archive["root"] / "data" / "spectra"
    events = campaign.select_events(min_class="M1.0", max_class="X1.0")
    first, second, third = (events.iloc[i] for i in range(3))
    obsjd = np.sort(archive["table"]["obsjd"].to_numpy())
    # Cloud over the whole second flare, and over three spectra shortly before the first.
    cloudy = (obsjd > second.jd_start - 40 * MINUTE) & (obsjd < second.jd_peak + 20 * MINUTE)
    cloudy[np.flatnonzero((obsjd > first.jd_start - 20 * MINUTE) & (obsjd < first.jd_start - 5 * MINUTE))[:3]] = True
    monkeypatch.setattr(quality, "stable_obsjd", lambda table: obsjd[~cloudy])

    campaign.run(
        hours=1.0, max_files=30, step=2, workers=2, min_class="M1.0", max_class="X1.0", clear_only=True,
        before_min=26.0, after_min=10.0, core_before_min=-1.0e9, core_after_min=-1.0e9,
    )
    capsys.readouterr()
    assert (root / campaign.event_name(first)).is_dir() and (root / campaign.event_name(third)).is_dir()
    assert not (root / campaign.event_name(second)).exists()  # the cloudy flare is not fetched at all
    table = archive["table"].set_index("l2filename")
    fetched = table.loc[fake_neid, "obsjd"].to_numpy()
    assert len(fetched) == 30 and not quality.matches(fetched, obsjd[cloudy]).any()  # no cloudy spectrum downloaded
    in_first = (fetched > first.jd_start - 26 * MINUTE) & (fetched < first.jd_peak + 10 * MINUTE)
    assert 12 <= in_first.sum() <= 18  # every second clear spectrum of a 46-minute window
    manifest = pd.read_csv(root / "events.csv")
    assert manifest["goes_class"].str[0].eq("M").all()

    # The joint analysis can be limited to a band of classes; nothing of class X was fetched here.
    assert len(chromosphere.run(min_class="X1.0")["events"]) == 0
    band = chromosphere.run(min_class="M1.0", max_class="X1.0")["events"]
    assert set(band["name"]) >= {campaign.event_name(first)} and band["goes_class"].str[0].eq("M").all()
