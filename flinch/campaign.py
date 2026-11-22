"""Unattended download of the spectra around the strongest flares, in order of peak flux."""
from __future__ import annotations

import ctypes
import datetime as dt
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

from . import coverage, goes, neid, quality, spectra
from .config import data_dir, reference_dir, results_dir
from .timeutil import MINUTE, jd_to_datetime


def event_name(row) -> str:
    """Folder name of a flare: date, time of the peak and class, e.g. ``20260118_1809_X1.9``."""
    return f"{jd_to_datetime(row.jd_peak):%Y%m%d_%H%M}_{row.goes_class}"


def select_events(min_class: str = "M1.0", max_class: str | None = None) -> pd.DataFrame:
    """Flares observed at the peak or during the rise, strongest first.

    ``max_class`` is exclusive: ``select_events("M5.0", "X1.0")`` gives the flares from M5.0 up
    to, but not including, X1.0.
    """
    observations = neid.read_solar_table()
    jd = np.sort(observations["obsjd"].to_numpy())
    flares = goes.load_flares()
    flares = flares[(flares["jd_peak"] >= jd.min()) & (flares["jd_peak"] <= jd.max())]
    flares = flares[flares["peak_flux"] >= goes.class_to_flux(min_class)]
    if max_class is not None:
        flares = flares[flares["peak_flux"] < goes.class_to_flux(max_class)]
    flares = flares.reset_index(drop=True)
    covered = coverage.add_coverage(flares, jd)
    # Spectra between the start and the peak: a flare peaking just after the end of the
    # observing day still has its impulsive phase on record.
    start = covered["jd_start"].fillna(covered["jd_peak"] - 10.0 * MINUTE)
    covered["n_rise"] = coverage.count_between(jd, start.to_numpy(), covered["jd_peak"].to_numpy())
    covered = covered[covered["at_peak"] | (covered["n_rise"] >= 3)]
    return covered.sort_values("peak_flux", ascending=False, ignore_index=True)


def clear_sky(
    events: pd.DataFrame,
    steady_obsjd: np.ndarray,
    before_min: float = 26.0,
    window_min: tuple[float, float] = (-8.0, 10.0),
    min_before: int = 12,
    min_window: int = 9,
) -> pd.Series:
    """Flares with a steady, clear sky before their start and around their peak.

    Counts the spectra of ``steady_obsjd`` (see ``quality.stable_obsjd``) from ``before_min`` to
    2 min before the start of the flare, and in ``window_min`` around its peak. The criterion
    uses the signal-to-noise ratio of the spectra alone, never their content, so it can be
    applied before any spectrum is downloaded.
    """
    steady_obsjd = np.asarray(steady_obsjd, dtype=float)
    start = events["jd_start"].fillna(events["jd_peak"] - 10.0 * MINUTE).to_numpy()
    peak = events["jd_peak"].to_numpy()
    before = coverage.count_between(steady_obsjd, start - before_min * MINUTE, start - 2.0 * MINUTE)
    window = coverage.count_between(steady_obsjd, peak + window_min[0] * MINUTE, peak + window_min[1] * MINUTE)
    return pd.Series((before >= min_before) & (window >= min_window), index=events.index)


def control_events(events: pd.DataFrame, max_shift_days: int = 12, margin_min: float = 60.0) -> pd.DataFrame:
    """One flare-free epoch per flare: the same time of day on the nearest suitable day.

    A day is suitable when no M or X flare peaks within ``margin_min`` minutes of the shifted
    window and the spectrograph took at least 90 % as many spectra in it as in the window of the
    flare itself (which can be cut short by the start or the end of the observing day). The control
    keeps the class and position of its flare (to pair them) and is named after it.
    """
    observations = np.sort(neid.read_solar_table()["obsjd"].to_numpy())
    flares = goes.load_flares()
    major = np.sort(flares.loc[flares["goes_class"].str[0].isin(["M", "X"]), "jd_peak"].to_numpy())
    rows = []
    for row in events.itertuples():
        start = row.jd_start if row.jd_start == row.jd_start else row.jd_peak - 10.0 * MINUTE
        low, high = start - 30.0 * MINUTE, row.jd_peak + 45.0 * MINUTE
        expected = max(10, coverage.count_between(observations, low, high))
        for shift in (s * d for d in range(1, max_shift_days + 1) for s in (1, -1)):
            quiet = coverage.count_between(major, low + shift - margin_min * MINUTE, high + shift + margin_min * MINUTE) == 0
            observed = coverage.count_between(observations, low + shift, high + shift)
            if quiet and observed >= 0.9 * expected:
                control = row._asdict()
                control.pop("Index", None)
                control.update(jd_start=start + shift, jd_peak=row.jd_peak + shift, parent=event_name(row), shift_days=shift)
                rows.append(control)
                break
    return pd.DataFrame(rows)


def control_name(row) -> str:
    return f"{row.parent}_control{int(row.shift_days):+d}d"


def write_manifest(rows: list[dict]) -> None:
    """Record of every window fetched: name, kind, times and the flare it belongs to."""
    path = data_dir() / "spectra" / "events.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    new = pd.DataFrame(rows)
    if path.exists():
        new = pd.concat([pd.read_csv(path), new], ignore_index=True).drop_duplicates("name", keep="last")
    new.to_csv(path, index=False)


def keep_awake(enable: bool) -> None:
    """Ask Windows not to sleep while the campaign runs (no effect elsewhere)."""
    if sys.platform != "win32":
        return
    continuous, system_required = 0x80000000, 0x00000001
    ctypes.windll.kernel32.SetThreadExecutionState(continuous | (system_required if enable else 0))


def log(message: str) -> None:
    print(f"{dt.datetime.now():%Y-%m-%d %H:%M:%S}  {message}", flush=True)


def run(
    hours: float = 7.5,
    max_files: int = 600,
    step: int = 3,
    before_min: float = 30.0,
    after_min: float = 45.0,
    workers: int = 3,
    min_class: str = "M1.0",
    core_before_min: float = 10.0,
    core_after_min: float = 15.0,
    kind: str = "flares",
    usable_only: bool = False,
    max_class: str | None = None,
    clear_only: bool = False,
) -> None:
    """Fetch spectrum extracts flare by flare until the time or the file budget runs out.

    Each flare gets the window from ``before_min`` minutes before its start to ``after_min``
    minutes after its peak. Every spectrum is taken in the core of the flare (from
    ``core_before_min`` minutes before the start to ``core_after_min`` after the peak, where
    things change within a minute) and every ``step``-th one outside it. Extracts already on
    disk are skipped, so the campaign can be stopped and run again.

    With ``kind`` = "controls" the same windows are fetched on a flare-free day for every
    flare that already has spectra (see ``control_events``). With ``usable_only`` the controls
    are limited to the flares marked as usable in ``results/spectral_response.csv``.

    ``max_class`` (exclusive) limits the flares from above. With ``clear_only`` only the flares
    that pass ``clear_sky`` are fetched, and of them only the spectra taken through a steady
    sky: the others would be discarded by the analysis anyway, and each costs 113 MB.
    """
    deadline = time.monotonic() + hours * 3600.0
    events = select_events(min_class, max_class)
    steady = quality.stable_obsjd(neid.read_solar_table()) if clear_only else None
    if clear_only and kind == "flares":
        events = events[clear_sky(events, steady)].reset_index(drop=True)
    root = data_dir() / "spectra"
    if kind == "controls":
        fetched_flares = [len(list((root / event_name(r)).glob("neidL2_*.npz"))) >= 10 for r in events.itertuples()]
        events = control_events(events[fetched_flares])
        if usable_only:
            measured = pd.read_csv(results_dir() / "spectral_response.csv")
            wanted = set(measured.loc[(measured["kind"] == "flare") & measured["usable"], "name"])
            events = events[events["parent"].isin(wanted)].reset_index(drop=True)
    name_of = control_name if kind == "controls" else event_name
    manifest = []
    scratch = Path(tempfile.gettempdir()) / "flinch_spectra"
    scratch.mkdir(parents=True, exist_ok=True)
    fetched = 0
    keep_awake(True)
    log(f"campaign: {len(events)} {kind}, budget {hours} h / {max_files} files, step {step}")
    try:
        for row in events.itertuples():
            if time.monotonic() > deadline or fetched >= max_files:
                break
            name = name_of(row)
            start = row.jd_start if row.jd_start == row.jd_start else row.jd_peak - 10.0 * MINUTE
            try:
                files = spectra.list_files(start - before_min * MINUTE, row.jd_peak + after_min * MINUTE)
                if steady is not None:
                    files = files[quality.matches(files["obsjd"].to_numpy(), steady)].reset_index(drop=True)
                core =(files["obsjd"] >= start - core_before_min * MINUTE) & (
                    files["obsjd"] <= row.jd_peak + core_after_min * MINUTE
                )
                files = files[core | (np.arange(len(files)) % step == 0)]
            except Exception as exc:  # noqa: BLE001  (network trouble: go on with the next flare)
                log(f"{name}: could not list files ({type(exc).__name__}: {exc})")
                continue
            directory = root / name
            directory.mkdir(parents=True, exist_ok=True)
            todo = [f for f in files.itertuples() if not (directory / (Path(f.l2filename).stem + ".npz")).exists()]
            todo = todo[: max(0, max_files - fetched)]

            def task(item) -> bool:
                if time.monotonic() > deadline:
                    return False
                try:
                    spectra.fetch_one(item.l2filepath, item.l2filename, directory, scratch)
                    return True
                except Exception as exc:  # noqa: BLE001
                    log(f"{name}: {item.l2filename} failed ({type(exc).__name__}: {exc})")
                    return False

            began = time.monotonic()
            with ThreadPoolExecutor(max_workers=workers) as pool:
                done = sum(pool.map(task, todo))
            fetched += done
            manifest.append(
                {
                    "name": name, "kind": kind, "parent": getattr(row, "parent", name),
                    "jd_start": start, "jd_peak": row.jd_peak, "goes_class": row.goes_class,
                    "peak_flux": row.peak_flux, "x_norm": row.x_norm, "y_norm": row.y_norm, "r_norm": row.r_norm,
                }
            )
            write_manifest(manifest)
            have = len(list(directory.glob("neidL2_*.npz")))
            rate = (time.monotonic() - began) / max(done, 1)
            log(f"{name}: +{done} (now {have} of {len(files)}), {rate:.0f} s per file, total fetched {fetched}")
    finally:
        keep_awake(False)
        log(f"campaign finished: {fetched} files fetched")


# ---------------------------------------------------------------------------------------------
# The spectra of the paper. ``run`` above chose them with a budget of hours and files, so what
# it fetches depends on the connection and on the day. The two tables in ``flinch/reference``
# record what it fetched for the paper, and ``fetch_paper_spectra`` fetches exactly that.
# ---------------------------------------------------------------------------------------------
FILE_MB = 113  # size of one level-2 file


def paper_windows() -> pd.DataFrame:
    """The windows of spectra of the paper, flares and controls: name, kind, times, class and position."""
    return pd.read_csv(reference_dir() / "spectra_windows.csv")


def paper_files() -> pd.DataFrame:
    """Every spectrum of the paper: window, level-2 file, start of the exposure, pipeline version and fingerprint."""
    return pd.read_csv(reference_dir() / "spectra_files.csv")


def freeze_paper_spectra() -> None:
    """Write the two tables above from the extracts on disk.

    Run by the author when the sample of the paper was closed
    (``python -c "from flinch import campaign; campaign.freeze_paper_spectra()"``).
    """
    root = data_dir() / "spectra"
    windows = pd.read_csv(root / "events.csv")
    versions = neid.read_solar_table().drop_duplicates("l2filename").set_index("l2filename")["swversion"]
    rows = []
    for name in windows["name"]:
        for path in sorted((root / name).glob("neidL2_*.npz")):
            with np.load(path, allow_pickle=False) as data:
                rows.append(
                    {
                        "name": name,
                        "file": path.stem + ".fits",
                        "obsjd": float(data["obsjd"]),
                        "swversion": versions.get(path.stem + ".fits", ""),
                        "sha256": spectra.digest(data),
                    }
                )
    reference_dir().mkdir(parents=True, exist_ok=True)
    windows.to_csv(reference_dir() / "spectra_windows.csv", index=False, lineterminator="\n")
    pd.DataFrame(rows).to_csv(reference_dir() / "spectra_files.csv", index=False, lineterminator="\n")


def _fetch_listed_window(name: str, listed: pd.DataFrame, root: Path, scratch: Path, workers: int) -> tuple[dict, int]:
    """Fetch the listed files of one window that are not on disk; status of every listed file and number fetched."""
    directory = root / name
    directory.mkdir(parents=True, exist_ok=True)

    def extract_of(filename: str) -> Path:
        return directory / (Path(filename).stem + ".npz")

    status = {filename: "failed" for filename in listed["file"]}
    todo = listed[[not extract_of(filename).exists() for filename in listed["file"]]]
    fetched = 0
    if len(todo):
        try:
            archive = spectra.list_files(todo["obsjd"].min() - MINUTE, todo["obsjd"].max() + MINUTE)
            paths = dict(zip(archive["l2filename"], archive["l2filepath"]))
        except Exception as exc:  # noqa: BLE001  (network trouble: left for the next round)
            log(f"{name}: could not list files ({type(exc).__name__}: {exc})")
            paths = None
        if paths is not None:
            wanted = []
            for filename in todo["file"]:
                if filename in paths:
                    wanted.append(filename)
                else:
                    status[filename] = "not in the archive"

            def task(filename: str) -> bool:
                try:
                    spectra.fetch_one(paths[filename], filename, directory, scratch)
                    return True
                except Exception as exc:  # noqa: BLE001
                    log(f"{name}: {filename} failed ({type(exc).__name__}: {exc})")
                    return False

            with ThreadPoolExecutor(max_workers=workers) as pool:
                fetched = sum(pool.map(task, wanted))
    for row in listed.itertuples():
        if extract_of(row.file).exists():
            with np.load(extract_of(row.file), allow_pickle=False) as data:
                status[row.file] = "identical" if spectra.digest(data) == row.sha256 else "different"
    return status, fetched


def fetch_paper_spectra(
    workers: int = 3, sample: int | None = None, seed: int = 0, rounds: int = 4, pause_s: float = 300.0
) -> pd.DataFrame:
    """Fetch exactly the spectra used in the paper and compare every extract with its fingerprint.

    The files are those of ``paper_files``. Extracts already on disk are not downloaded again,
    only checked, so the command can be stopped and repeated. With ``sample`` only that many
    files, drawn at random with ``seed``, are fetched: a check of the archive and of the
    extraction that costs ``sample`` times 113 MB instead of the whole list. Files that fail
    are tried again in up to ``rounds`` rounds, ``pause_s`` seconds apart.

    Returns the list with a column ``status``: "identical"; "different" (the archive now serves
    another version of that spectrum); "not in the archive"; or "failed" (the download failed
    in every round: run the command again). The table is also written to ``spectra/check.csv``
    in the data directory, and the list of windows to ``spectra/events.csv``, where
    ``chromosphere`` reads it.
    """
    files = paper_files()
    if sample is not None and sample < len(files):
        files = files.sample(n=sample, random_state=seed).sort_index()
    root = data_dir() / "spectra"
    root.mkdir(parents=True, exist_ok=True)
    paper_windows().to_csv(root / "events.csv", index=False)
    scratch = Path(tempfile.gettempdir()) / "flinch_spectra"
    scratch.mkdir(parents=True, exist_ok=True)
    status = pd.Series("failed", index=files.index)
    total = 0
    keep_awake(True)
    log(f"paper spectra: {len(files)} files in {files['name'].nunique()} windows, up to {len(files) * FILE_MB / 1024:.0f} GB to download")
    try:
        for attempt in range(rounds):
            pending = files[status == "failed"]
            if pending.empty:
                break
            if attempt:
                log(f"round {attempt + 1}: {len(pending)} files left, waiting {pause_s:.0f} s")
                time.sleep(pause_s)
            for name in pending["name"].unique():
                began = time.monotonic()
                listed = files[files["name"] == name]
                result, fetched = _fetch_listed_window(name, listed, root, scratch, workers)
                total += fetched
                status[listed.index] = [result[filename] for filename in listed["file"]]
                counts = pd.Series(result).value_counts()
                rate = (time.monotonic() - began) / max(fetched, 1)
                log(
                    f"{name}: +{fetched}, {rate:.0f} s per file, "
                    + ", ".join(f"{number} {label}" for label, number in counts.items())
                    + f", total fetched {total}"
                )
    finally:
        keep_awake(False)
        out = files.assign(status=status)
        out.to_csv(root / "check.csv", index=False)
        log("paper spectra finished: " + ", ".join(f"{number} {label}" for label, number in status.value_counts().items()))
    return out
