"""Reproduce the paper from the public archives, in one command, and report what agrees.

``python -m flinch reproduce`` downloads the data, runs every step of the analysis, compares
each new table with the one kept in the repository and checks every number of the paper
against the new tables. The steps are the ordinary commands of the package, run one after
another; this module only puts them in order, times them and writes the report. The new
tables go to their own folder, so the repository is left as it was.

The spectra are the expensive part: 1296 files of 113 MB that the archive serves whole, 143 GB
in all. They are left out by default. ``--spectra sample`` fetches a few of them and compares
each with the fingerprint of the one used in the paper; ``--spectra all`` fetches them all and
repeats the spectral analysis.
"""
from __future__ import annotations

import datetime as dt
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from .config import REPO_ROOT, data_dir

VELOCITY_STEPS = ("coverage", "replication", "replication --cleaning", "robustness", "pilot", "numbers")
VELOCITY_TABLES = (
    "flare_sample.csv", "velocity_by_instrument.csv", "replication_events.csv", "replication_profiles.csv",
    "early_window.csv", "cleaning_variants.csv", "robustness.csv", "injections.csv", "pilot_flares.csv",
    "pilot_controls.csv", "pilot_summary.csv", "pilot_tests.csv", "pilot_profiles.csv", "text_numbers.csv",
)
SPECTRAL_TABLES = ("spectral_response.csv", "spectral_indices.csv")
RELATIVE_TOLERANCE = 1.0e-9  # two numbers closer than this are the same number computed on another machine


def compare_tables(reference: Path, new: Path) -> tuple[str, str]:
    """Compare a new table with the reference one.

    Returns the verdict and a detail: "identical" (the same text), "same numbers" (every number
    within ``RELATIVE_TOLERANCE``), "DIFFERENT" (with the columns that differ and by how much),
    or "missing".
    """
    if not reference.exists() or not new.exists():
        return "missing", "no reference table" if not reference.exists() else "the step did not write it"
    if reference.read_bytes().replace(b"\r\n", b"\n") == new.read_bytes().replace(b"\r\n", b"\n"):
        return "identical", ""
    old, now = pd.read_csv(reference), pd.read_csv(new)
    if list(old.columns) != list(now.columns):
        return "DIFFERENT", "other columns"
    if len(old) != len(now):
        return "DIFFERENT", f"{len(old)} rows in the repository, {len(now)} now"
    differing = []
    for column in old.columns:
        a, b = old[column], now[column]
        if pd.api.types.is_numeric_dtype(a) and pd.api.types.is_numeric_dtype(b):
            x, y = a.to_numpy(dtype=float), b.to_numpy(dtype=float)
            both = np.isfinite(x) & np.isfinite(y)
            if not np.array_equal(np.isfinite(x), np.isfinite(y)):
                differing.append(f"{column} (values missing in one of them)")
            elif both.any():
                gap = np.abs(x[both] - y[both])
                allowed = RELATIVE_TOLERANCE * np.maximum(1.0, np.abs(x[both]))
                if np.any(gap > allowed):
                    differing.append(f"{column} (by up to {gap.max():.3g})")
        elif not a.astype(str).equals(b.astype(str)):
            differing.append(column)
    if differing:
        return "DIFFERENT", ", ".join(differing)
    return "same numbers", f"differences below {RELATIVE_TOLERANCE:g}"


class Report:
    """Lines printed as the run goes and saved at the end."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.lines: list[str] = []

    def say(self, text: str = "") -> None:
        print(text, flush=True)
        self.lines.append(text)
        self.path.write_text("\n".join(self.lines) + "\n", encoding="utf-8")


def step(report: Report, out: Path, command: str, *paths: str) -> int:
    """Run ``python -m flinch <command> <paths>``, keep its output in a file and report how it went.

    The command writes its tables and figures under ``out``, not in the repository.
    """
    began = time.monotonic()
    log = out / "logs" / (command.replace(" ", "_").replace("--", "") + ".txt")
    env = dict(os.environ, FLINCH_RESULTS=str(out / "results"), FLINCH_FIGURES=str(out / "site_figures"))
    with open(log, "w", encoding="utf-8") as handle:
        done = subprocess.run(
            [sys.executable, "-m", "flinch", *command.split(), *paths], cwd=REPO_ROOT, env=env, stdout=handle, stderr=subprocess.STDOUT
        )
    seconds = time.monotonic() - began
    verdict = "done" if done.returncode == 0 else f"exit code {done.returncode}"
    report.say(f"  {command:28s} {verdict:14s} {seconds:7.0f} s   output in {log}")
    return done.returncode


def spectra_complete() -> bool:
    """Whether every spectrum of the paper has its extract on disk."""
    from . import campaign

    root = data_dir() / "spectra"
    return all((root / row.name / (Path(row.file).stem + ".npz")).exists() for row in campaign.paper_files().itertuples())


def run(spectra: str = "none", sample: int = 10, download: bool = True, out: Path | None = None) -> int:
    """Run everything and write the report; returns 0 when every table and every number agrees.

    Nothing in the repository is touched: the new tables, the figures, the output of every step
    and the report go to ``out`` (``reproduction/`` by default).
    """
    from . import campaign, inputs, verify

    out = Path(out or REPO_ROOT / "reproduction").resolve()
    committed, new, figures = REPO_ROOT / "results", out / "results", out / "figures"
    for folder in (out / "logs", new, figures):
        folder.mkdir(parents=True, exist_ok=True)
    report = Report(out / "report.txt")
    files = len(campaign.paper_files())
    report.say(f"flinch reproduce, {dt.datetime.now():%Y-%m-%d %H:%M}")
    report.say(f"{platform.platform()}, Python {sys.version.split()[0]}, numpy {np.__version__}, pandas {pd.__version__}")
    report.say(f"Data in {data_dir()}")
    report.say(f"Last day of data: {os.environ.get('FLINCH_DATA_END', 'as in the paper')}")
    plan = {
        "none": "not fetched",
        "sample": f"{sample} files, {sample * campaign.FILE_MB / 1024:.1f} GB",
        "all": f"{files} files, {files * campaign.FILE_MB / 1024:.0f} GB",
    }[spectra]
    report.say(f"Spectra: {plan}")
    report.say()
    failures = 0

    report.say("1. Data")
    if download:
        failures += step(report, out, "download") != 0
    try:
        checked = inputs.check()
        for row in checked.itertuples():
            report.say(f"  {row.input:36s} {row.status}")
        if (checked["status"] != "identical").any():
            report.say("  Some inputs are not those of the paper: the archive has changed, and the tables below may differ for that reason.")
    except Exception as exc:  # noqa: BLE001  (no data: the steps below say so one by one)
        report.say(f"  the inputs could not be read ({type(exc).__name__}: {exc})")
        failures += 1
    report.say()

    report.say("2. Velocity analysis")
    for command in VELOCITY_STEPS:
        failures += step(report, out, command) != 0
    report.say()

    report.say("3. Spectra")
    if spectra != "none":
        code = step(report, out, "paper-spectra" + (f" --sample {sample}" if spectra == "sample" else ""))
        check = data_dir() / "spectra" / "check.csv"
        if check.exists():
            counts = pd.read_csv(check)["status"].value_counts()
            report.say("  extracts compared with those of the paper: " + ", ".join(f"{number} {label}" for label, number in counts.items()))
        failures += code != 0
    recomputed = spectra_complete()
    if recomputed:
        failures += step(report, out, "chromosphere") != 0
    else:
        report.say(f"  spectral analysis not repeated: it needs the {files} spectra of the paper (--spectra all)")
        for name in SPECTRAL_TABLES:  # the check of the numbers below reads them
            if (committed / name).exists():
                shutil.copyfile(committed / name, new / name)
    report.say()

    report.say("4. Figures")
    failures += step(report, out, "paper-figures --out", str(figures)) != 0
    report.say()

    report.say("5. New tables, against those of the repository")
    different = 0
    for name in (*VELOCITY_TABLES, *SPECTRAL_TABLES):
        if name in SPECTRAL_TABLES and not recomputed:
            report.say(f"  {name:30s} not recomputed")
            continue
        verdict, detail = compare_tables(committed / name, new / name)
        different += verdict in ("DIFFERENT", "missing")
        report.say(f"  {name:30s} {verdict}" + (f": {detail}" if detail else ""))
    report.say()

    report.say("6. Numbers of the paper, against the new tables")
    table = verify.run(new)
    table.to_csv(new / "paper_check.csv", index=False)
    wrong = table[~table["ok"]]
    for row in wrong.itertuples():
        report.say(f"  NOT IN AGREEMENT  {row.where}, {row.what}: paper {row.paper}, here {row.here}")
    report.say(f"  {len(table)} numbers checked, {len(table) - len(wrong)} in agreement, {len(wrong)} not")
    if not recomputed:
        report.say("  (the numbers of the spectra were checked against the tables of the repository, not against new ones)")
    report.say()

    ok = failures == 0 and different == 0 and wrong.empty
    summary = f"Not fully reproduced: {failures} steps failed, {different} tables differ, {len(wrong)} numbers of the paper not in agreement."
    report.say("Reproduced." if ok else summary)
    report.say(f"Everything is in {out}: report.txt, results/, figures/ and logs/")
    return 0 if ok else 1
