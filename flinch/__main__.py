"""Command line: ``python -m flinch <command>``; ``python -m flinch --help`` lists the commands."""
from __future__ import annotations

import argparse

import pandas as pd

from . import coverage, goes, neid
from .config import figures_dir, results_dir


def cmd_download(args: argparse.Namespace) -> int:
    for satellite in goes.SATELLITES:
        for product in goes.PRODUCTS:
            path = goes.download_product(satellite, product, overwrite=args.overwrite)
            print(f"GOES-{satellite} {product}: {path}")
    path = neid.download_solar_table(overwrite=args.overwrite)
    print(f"NEID solar table: {path}")
    from . import harpsn, pilot

    print(f"HARPS-N series: {harpsn.download_series(overwrite=args.overwrite)}")
    # One-minute X-ray fluxes of the years with M and X flares in the NEID era (for `robustness`).
    sample = pilot.major_flare_sample(goes.load_flares(), neid.read_solar_table()["obsjd"].to_numpy())
    for satellite, year in goes.download_avg1m(sample):
        print(f"GOES-{satellite} one-minute fluxes of {year}: on disk")
    return 0


def cmd_coverage(args: argparse.Namespace) -> int:
    flares = goes.load_flares()
    observations = neid.read_solar_table()
    jd = observations["obsjd"].to_numpy()
    in_era = (flares["jd_peak"] >= jd.min()) & (flares["jd_peak"] <= jd.max())
    major = flares["goes_class"].str[0].isin(["M", "X"])
    sample = coverage.add_coverage(flares[in_era & major].reset_index(drop=True), jd)

    print(f"NEID solar observations: {len(observations)}")
    print(f"M and X flares in the NEID era: {len(sample)}")
    print(coverage.summarize(sample).to_string(index=False))
    x_class = sample[sample["at_peak"] & (sample["goes_class"].str[0] == "X")]
    print("X-class flares observed at the peak:")
    for row in x_class.itertuples():
        note = "" if row.well_covered else "  (partial baseline)"
        print(f"  {row.goes_class:5s} {row.peak:%Y-%m-%d %H:%M}{note}")

    destination = results_dir() / "flare_sample.csv"
    sample.to_csv(destination, index=False)
    print(f"Sample written to {destination}")
    return 0


def cmd_pilot(args: argparse.Namespace) -> int:
    from . import pilot  # imported here: the other commands do not need the analysis code

    out = pilot.run(per_flare=args.controls, seed=args.seed)
    numbers = out["numbers"]
    print(f"Spectra: {numbers['spectra']}; passing the quality cuts: {numbers['good_spectra']}")
    print(f"Scatter of one spectrum about the daily trend: {numbers['point_sigma_ms']:.2f} m/s")
    print(f"Flares measured: {len(out['flares'])}; controls: {len(out['controls'])}")
    print(f"Noise of one event (scatter of the controls): {numbers['event_noise_ms']:.2f} m/s")
    print(
        f"Injection test: {numbers['injection_efficiency'] * 100:.0f} % of a "
        f"{numbers['injection_ms']:.1f} m/s signal is recovered"
    )
    with pd.option_context("display.width", 200, "display.float_format", "{:.3f}".format):
        print("\nVelocity change, signal window minus pre-flare window (m/s):")
        print(out["summary"].to_string(index=False))
        print("\nSame, with a two-sided baseline (m/s):")
        print(out["summary_two_sided"].to_string(index=False))
        print("\nStatistics against one-control-per-flare null samples:")
        print(out["tests"].to_string(index=False))

    directory = results_dir()
    out["flares"].to_csv(directory / "pilot_flares.csv", index=False)
    out["controls"].to_csv(directory / "pilot_controls.csv", index=False)
    out["summary"].to_csv(directory / "pilot_summary.csv", index=False)
    out["tests"].to_csv(directory / "pilot_tests.csv", index=False)
    out["profiles"].to_csv(directory / "pilot_profiles.csv", index=False)
    from . import plots

    plots.plot_profiles(out["profiles"], figures_dir() / "pilot_profiles.png")
    plots.plot_events(out["flares"], out["controls"], figures_dir() / "pilot_events.png")
    print(f"\nTables and figures written to {directory}")
    return 0


def cmd_robustness(args: argparse.Namespace) -> int:
    from . import robust

    out = robust.run(seed=args.seed)
    numbers = out["numbers"]
    with pd.option_context("display.width", 250, "display.max_colwidth", 90, "display.float_format", "{:.3f}".format):
        print("Paired velocity change (flare minus its controls), m/s; errors from a bootstrap over days:")
        print(out["table"].to_string(index=False))
        print()
        print("Injection and recovery through the whole chain:")
        print(out["injections"].to_string(index=False))
    print()
    print(f"Most flares on one day: {numbers['flares_per_day_max']}")
    print(f"Rotation term, permutation of the positions: p = {numbers['rotation_permutation_p']:.3f}")
    print(f"95 % limit on the effective optical contrast per X1 flare: {numbers['optical_contrast_limit_per_X1']:.1e}")
    directory = results_dir()
    out["table"].to_csv(directory / "robustness.csv", index=False)
    out["injections"].to_csv(directory / "injections.csv", index=False)
    return 0


def cmd_spectra(args: argparse.Namespace) -> int:
    import datetime as dt

    from . import spectra
    from .timeutil import datetime_to_jd

    jd_from = datetime_to_jd(dt.datetime.fromisoformat(args.start))
    jd_to = datetime_to_jd(dt.datetime.fromisoformat(args.end))
    spectra.fetch_window(jd_from, jd_to, args.name, workers=args.workers, step=args.step)
    return 0


def cmd_campaign(args: argparse.Namespace) -> int:
    from . import campaign

    core = (-1.0e9, -1.0e9) if args.sparse else (10.0, 15.0)  # sparse: no full-cadence core
    campaign.run(
        hours=args.hours, max_files=args.max_files, step=args.step, workers=args.workers, kind=args.kind,
        usable_only=args.usable_only, core_before_min=core[0], core_after_min=core[1],
        min_class=args.min_class, max_class=args.max_class, clear_only=args.clear_only,
        before_min=args.before, after_min=args.after,
    )
    return 0


def cmd_paper_spectra(args: argparse.Namespace) -> int:
    from . import campaign

    checked = campaign.fetch_paper_spectra(workers=args.workers, sample=args.sample, seed=args.seed)
    counts = checked["status"].value_counts()
    print(f"Spectra of the paper checked: {len(checked)}")
    for label, number in counts.items():
        print(f"  {label}: {number}")
    for row in checked[checked["status"] != "identical"].itertuples():
        print(f"  {row.status}: {row.name}/{row.file}")
    if counts.get("failed", 0):
        return 1  # some downloads failed: run the command again
    return 0 if counts.get("identical", 0) == len(checked) else 2  # 2: the archive has changed


def cmd_replication(args: argparse.Namespace) -> int:
    from . import replication

    if args.cleaning:
        table = replication.cleaning_table()
        with pd.option_context("display.width", 220, "display.float_format", "{:.3f}".format):
            print("Velocity change under other cleaning thresholds (m/s):")
            print(table.to_string(index=False))
        table.to_csv(results_dir() / "cleaning_variants.csv", index=False)
        return 0
    out = replication.run()
    columns = ["instrument", "band", "flares", "mean", "mean_err", "limit_95", "per_X1", "per_X1_err", "rotation", "rotation_err", "flare_std", "control_std"]
    with pd.option_context("display.width", 220, "display.float_format", "{:.3f}".format):
        print("Velocity change during flares, paired with controls (m/s):")
        print(out["table"][columns].to_string(index=False))
        print()
        print("Mean residual from 60 to 50 min before the X-ray peak (m/s):")
        print(out["early_window"].to_string(index=False))
    for name, value in out["numbers"].items():
        print(f"{name}: {value}")
    directory = results_dir()
    out["table"].to_csv(directory / "velocity_by_instrument.csv", index=False)
    out["profiles"].to_csv(directory / "replication_profiles.csv", index=False)
    out["events"].to_csv(directory / "replication_events.csv", index=False)
    out["early_window"].to_csv(directory / "early_window.csv", index=False)
    return 0


def cmd_numbers(args: argparse.Namespace) -> int:
    from . import numbers

    table = numbers.run()
    with pd.option_context("display.width", 200, "display.max_rows", 200, "display.float_format", "{:.4f}".format):
        print(table.to_string(index=False))
    table.to_csv(results_dir() / "text_numbers.csv", index=False)
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    from . import verify

    table = verify.run()
    failed = table[~table["ok"]]
    with pd.option_context("display.width", 250, "display.max_rows", 1000, "display.max_colwidth", 90):
        shown = table if args.all else failed
        if len(shown):
            print(shown.assign(ok=shown["ok"].map({True: "yes", False: "NO"})).to_string(index=False))
    print(f"Numbers of the paper checked: {len(table)}; in agreement: {len(table) - len(failed)}; not in agreement: {len(failed)}")
    table.to_csv(results_dir() / "paper_check.csv", index=False)
    return 0 if failed.empty else 1


def cmd_reproduce(args: argparse.Namespace) -> int:
    from . import reproduce

    return reproduce.run(spectra=args.spectra, sample=args.sample, download=not args.no_download, out=args.out)


def cmd_chromosphere(args: argparse.Namespace) -> int:
    from . import chromosphere

    events, indices = [], []
    for band, low, high in (("X", "X1.0", None), ("M5-M9", "M5.0", "X1.0")):
        out = chromosphere.run(min_class=low, max_class=high)
        if not len(out["events"]):
            continue
        if events:  # the control windows are the same for every band: keep them once
            out["events"] = out["events"][out["events"]["kind"] == "flare"]
        events.append(out["events"].assign(band=band))
        indices.append(out["indices"].assign(band=band))
        print(f"{band}: {out['numbers']}")
    if not events:
        print("No flare has spectra yet: run `python -m flinch campaign` first.")
        return 1
    directory = results_dir()
    pd.concat(events, ignore_index=True).to_csv(directory / "spectral_response.csv", index=False)
    table = pd.concat(indices, ignore_index=True)
    table.to_csv(directory / "spectral_indices.csv", index=False)
    with pd.option_context("display.width", 220, "display.float_format", "{:.2f}".format):
        print(table[["band", "index", "flares", "detected_total_error", "disc_mean", "disc_mean_err", "limb_mean", "limb_mean_err", "control_std"]].to_string(index=False))
    return 0


def cmd_paper_figures(args: argparse.Namespace) -> int:
    from . import paperfigs

    for path in paperfigs.make_all(args.out, event_name=args.event):
        print(path)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="flinch", description="Solar flares in Sun-as-a-star radial velocities")
    commands = parser.add_subparsers(dest="command", required=True)
    download = commands.add_parser(
        "download", help="download everything the velocity analysis needs: GOES flare lists and one-minute fluxes, NEID table, HARPS-N series (340 MB)"
    )
    download.add_argument("--overwrite", action="store_true", help="download again files that already exist")
    download.set_defaults(run=cmd_download)
    cover = commands.add_parser("coverage", help="cross-match flares with NEID observations")
    cover.set_defaults(run=cmd_coverage)
    pilot = commands.add_parser("pilot", help="stacked velocity response to flares, against controls")
    pilot.add_argument("--controls", type=int, default=10, help="controls per flare (default 10)")
    pilot.add_argument("--seed", type=int, default=0, help="seed of the random choices (default 0)")
    pilot.set_defaults(run=cmd_pilot)
    robustness = commands.add_parser("robustness", help="the velocity result under other estimators, backgrounds and controls")
    robustness.add_argument("--seed", type=int, default=0)
    robustness.set_defaults(run=cmd_robustness)
    spec = commands.add_parser(
        "spectra", help="extract indices and line windows from every spectrum in a time window (113 MB each)"
    )
    spec.add_argument("--start", required=True, help="UTC start, e.g. 2026-01-18T16:40")
    spec.add_argument("--end", required=True, help="UTC end, e.g. 2026-01-18T19:10")
    spec.add_argument("--name", required=True, help="name of the output folder under data/spectra/")
    spec.add_argument("--workers", type=int, default=3, help="simultaneous downloads (default 3)")
    spec.add_argument("--step", type=int, default=1, help="take every n-th spectrum (default 1: all)")
    spec.set_defaults(run=cmd_spectra)
    camp = commands.add_parser("campaign", help="unattended download of spectra around the strongest flares")
    camp.add_argument("--hours", type=float, default=7.5, help="time budget (default 7.5)")
    camp.add_argument("--max-files", type=int, default=600, help="file budget, 113 MB each (default 600)")
    camp.add_argument("--step", type=int, default=3, help="take every n-th spectrum (default 3)")
    camp.add_argument("--workers", type=int, default=3, help="simultaneous downloads (default 3)")
    camp.add_argument("--kind", choices=["flares", "controls"], default="flares", help="flare windows, or flare-free windows for the flares already fetched")
    camp.add_argument("--usable-only", action="store_true", help="controls only for the flares with usable spectra")
    camp.add_argument("--sparse", action="store_true", help="every n-th spectrum throughout, without the full-cadence core")
    camp.add_argument("--min-class", default="M1.0", help="weakest flare class to fetch (default M1.0)")
    camp.add_argument("--max-class", default=None, help="flares below this class only, e.g. X1.0 (default: no limit)")
    camp.add_argument("--clear-only", action="store_true", help="only flares, and spectra, with a steady clear sky")
    camp.add_argument("--before", type=float, default=30.0, help="minutes fetched before the start of the flare (default 30)")
    camp.add_argument("--after", type=float, default=45.0, help="minutes fetched after the peak of the flare (default 45)")
    camp.set_defaults(run=cmd_campaign)
    listed = commands.add_parser(
        "paper-spectra", help="fetch exactly the spectra used in the paper (1296 files of 113 MB) and check each against its fingerprint"
    )
    listed.add_argument("--sample", type=int, default=None, help="only this many files, drawn at random: a check that costs 113 MB per file")
    listed.add_argument("--seed", type=int, default=0, help="seed of the random sample (default 0)")
    listed.add_argument("--workers", type=int, default=3, help="simultaneous downloads (default 3)")
    listed.set_defaults(run=cmd_paper_spectra)

    again = commands.add_parser("replication", help="the velocity response measured with NEID and with HARPS-N, and both combined")
    again.add_argument("--cleaning", action="store_true", help="instead, repeat the measurement with other cleaning thresholds")
    again.set_defaults(run=cmd_replication)

    text = commands.add_parser("numbers", help="counts and descriptive numbers of the text: data, cuts, flare rate, representativeness of the sample")
    text.set_defaults(run=cmd_numbers)

    check = commands.add_parser("verify", help="check every number of the paper against the tables in results/")
    check.add_argument("--all", action="store_true", help="print every check, not only those that fail")
    check.set_defaults(run=cmd_verify)

    again_all = commands.add_parser(
        "reproduce", help="download the data, run every step, compare the tables with those of the repository and check the numbers of the paper"
    )
    again_all.add_argument(
        "--spectra", choices=["none", "sample", "all"], default="none",
        help="none (default): the spectra are not fetched; sample: a few are fetched and checked; all: the 1296 of the paper (143 GB)",
    )
    again_all.add_argument("--sample", type=int, default=10, help="spectra fetched with --spectra sample, 113 MB each (default 10)")
    again_all.add_argument("--no-download", action="store_true", help="use the data already on disk")
    again_all.add_argument("--out", default=None, help="folder for the report, the logs and the figures (default reproduction/)")
    again_all.set_defaults(run=cmd_reproduce)

    lines = commands.add_parser("chromosphere", help="response of the spectral indices to the flares with spectra, by class band")
    lines.set_defaults(run=cmd_chromosphere)

    figures = commands.add_parser("paper-figures", help="figures of the paper, as PDF in journal style, from the tables in results/")
    figures.add_argument("--out", default="docs/paper/figuras", help="folder for the PDF files (default docs/paper/figuras)")
    figures.add_argument("--event", default=None, help="also draw the figure of this single flare, e.g. 20240222_2233_X6.3")
    figures.set_defaults(run=cmd_paper_figures)
    args = parser.parse_args(argv)
    return args.run(args)


if __name__ == "__main__":
    raise SystemExit(main())
