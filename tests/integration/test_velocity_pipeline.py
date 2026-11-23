"""Integration: the whole velocity chain on a synthetic archive, with and without a flare signal.

The archive has 40 clear days of NEID-like velocities and one flare every other day. In one
version 1.5 m/s is added to the velocity during every flare; the chain has to measure it, and
to measure nothing in the version without it.
"""
import numpy as np
import pandas as pd
import pytest

from flinch import pilot, robust
from flinch.__main__ import main

SIGNAL = 1.5


def test_pilot_measures_an_injected_signal(archive_with_signal):
    out = pilot.run()
    flares = archive_with_signal["flares"]
    assert len(out["flares"]) == len(flares)  # every flare has complete windows
    assert out["controls"].groupby("parent").size().min() >= 3
    overall = out["summary"].set_index("band").loc["all"]
    assert overall["difference"] == pytest.approx(SIGNAL, abs=4 * overall["error"])
    assert overall["difference"] / overall["error"] > 5.0  # a clear detection
    assert abs(overall["control_mean"]) < 4 * overall["control_sem"]  # the controls see nothing
    tests = out["tests"].set_index("statistic")
    assert tests.loc["mean change (m/s)", "z"] > 5.0
    assert out["numbers"]["injection_efficiency"] == pytest.approx(1.0, abs=0.1)
    assert out["numbers"]["point_sigma_ms"] == pytest.approx(0.6, rel=0.15)  # the noise put in the table
    during = out["profiles"].query("subset == 'M and X' and sample == 'flares' and -10 < minutes < 0")
    assert during["mean"].mean() == pytest.approx(SIGNAL, abs=0.4)


def test_pilot_finds_nothing_without_a_signal(archive):
    out = pilot.run()
    overall = out["summary"].set_index("band").loc["all"]
    assert abs(overall["difference"]) < 4 * overall["error"]
    tests = out["tests"].set_index("statistic")
    assert (tests["z"].abs() < 4.0).all()
    assert out["numbers"]["injection_efficiency"] == pytest.approx(1.0, abs=0.1)


def test_robustness_holds_the_signal_under_every_variant(archive_with_signal):
    out = robust.run()
    table = out["table"].set_index("configuration")
    default = table.iloc[0]
    assert default["mean"] == pytest.approx(SIGNAL, abs=4 * default["mean_err"])
    # the variants whose window lies inside the injected box measure the same amplitude
    for label in ("Day polynomial of degree 1", "Day polynomial of degree 3", "Window: first 10 min from the start",
                  "Background: straight line fitted locally on both sides",
                  "Default, bootstrap over active regions instead of days", "Default, X-class flares only"):
        # a fixed tolerance: with two synthetic regions the region bootstrap has an error that means little
        assert table.loc[label, "mean"] == pytest.approx(SIGNAL, abs=0.4), label
    assert table.loc["Window: 3 min either side of the steepest X-ray rise", "mean"] > 1.0
    # a signal of constant size is not a rotation signature: positions alternate east and west
    assert abs(default["rotation"]) < 5 * default["rotation_err"]
    assert out["numbers"]["rotation_permutation_p"] > 0.001
    injections = out["injections"]
    assert injections["efficiency"].to_numpy() == pytest.approx(1.0, abs=0.1)
    assert injections["detection_probability"].is_monotonic_increasing


def test_command_line_runs_the_pilot_and_the_robustness(archive_with_signal, capsys):
    results = archive_with_signal["root"] / "results"
    figures = archive_with_signal["root"] / "figures"
    assert main(["pilot"]) == 0
    printed = capsys.readouterr().out
    assert "Flares measured" in printed and "Injection test" in printed
    for name in ("pilot_flares.csv", "pilot_controls.csv", "pilot_summary.csv", "pilot_tests.csv", "pilot_profiles.csv"):
        assert (results / name).stat().st_size > 100, name
    for name in ("pilot_profiles.png", "pilot_events.png"):
        assert (figures / name).read_bytes()[:4] == b"\x89PNG", name
    summary = pd.read_csv(results / "pilot_summary.csv").set_index("band")
    assert summary.loc["all", "difference"] > 1.0
    assert main(["robustness"]) == 0
    table = pd.read_csv(results / "robustness.csv")
    assert len(table) == 10 and np.isfinite(table["mean"]).sum() >= 9
    assert len(pd.read_csv(results / "injections.csv")) == 4


def test_two_instruments_measure_the_same_injected_signal(archive_with_signal, monkeypatch, capsys):
    """The NEID-like archive and a HARPS-N-like series carry 1.5 m/s during every flare: both give it back."""
    import helpers
    from flinch import _http, replication
    from flinch.__main__ import main

    helpers.write_harpsn(archive_with_signal["root"] / "data", archive_with_signal["flares"], signal_ms=1.5)
    monkeypatch.setattr(_http, "download", lambda *a, **k: pytest.fail("the network must not be used"))
    out = replication.run()
    table = out["table"].set_index(["instrument", "band"])
    for instrument in ("NEID", "HARPS-N", "Both"):
        row = table.loc[(instrument, "M and X")]
        assert row["mean"] == pytest.approx(1.5, abs=4.0 * row["mean_err"]) and row["mean_err"] < 0.2
    assert table.loc[("Both", "M and X"), "flares"] == table.loc[("NEID", "M and X"), "flares"] + table.loc[("HARPS-N", "M and X"), "flares"]
    assert table.loc[("Both", "M and X"), "mean_err"] < table.loc[("NEID", "M and X"), "mean_err"]
    for instrument in ("NEID", "HARPS-N"):
        assert out["numbers"][instrument]["injection_efficiency"] == pytest.approx(1.0, abs=0.1)
    profiles = out["profiles"]
    assert set(profiles["instrument"]) == {"NEID", "HARPS-N"} and set(profiles["sample"]) == {"flares", "controls"}
    assert out["numbers"]["flares_in_both"] > 0  # the synthetic instruments watch the same flares

    assert main(["replication"]) == 0
    assert "Both" in capsys.readouterr().out
    for name in ("velocity_by_instrument", "replication_profiles", "replication_events", "early_window"):
        assert (archive_with_signal["root"] / "results" / f"{name}.csv").stat().st_size > 100


def test_the_signal_survives_other_cleaning_thresholds(archive_with_signal, monkeypatch, capsys):
    """Every variant of the cuts on whole days gives back the 1.5 m/s that the two synthetic instruments carry."""
    import helpers
    from flinch import _http, replication
    from flinch.__main__ import main

    helpers.write_harpsn(archive_with_signal["root"] / "data", archive_with_signal["flares"], signal_ms=1.5)
    monkeypatch.setattr(_http, "download", lambda *a, **k: pytest.fail("the network must not be used"))
    assert [label for label, _ in replication.cleaning_variants(replication.NEID)][-1] == "at least 80 points per day"
    assert replication.cleaning_variants(replication.HARPSN)[-1] == ("quality flag above 0.9", {"min_quality": 0.9})

    assert main(["replication", "--cleaning"]) == 0
    assert "cleaning thresholds" in capsys.readouterr().out
    table = pd.read_csv(archive_with_signal["root"] / "results" / "cleaning_variants.csv")
    assert len(table) == 2 * (6 + 7) + 4 and set(table["band"]) == {"M and X", "X"}  # the variants and the flares not preceded by another one
    assert (table["variant"] == replication.ISOLATED).sum() == 4
    every = table[(table["band"] == "M and X") & (table["flares"] > 5)]
    assert len(every) >= 8
    for _, row in every.iterrows():
        assert row["mean"] == pytest.approx(1.5, abs=5.0 * row["mean_err"])
