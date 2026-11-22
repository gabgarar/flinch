# Reproducing the paper

One command downloads the public data, runs the whole analysis, compares every table with
the one kept in the repository and checks every number of the paper against the new tables.

```
python -m flinch reproduce
```

It needs 340 MB of downloads and about ten minutes. It leaves the spectra out, which are
143 GB; the levels below say how to include them. Nothing in the repository is modified.
The new tables, the figures, the output of every step and a report go to `reproduction/`.

## From zero

```
git clone https://github.com/gabgarar/flinch.git
cd flinch
python -m venv venv
venv/Scripts/python -m pip install -r requirements-lock.txt     # the exact versions used
venv/Scripts/python -m pip install --no-deps -e .
venv/Scripts/python -m flinch reproduce
```

On Linux and macOS the interpreter is `venv/bin/python`. The paper was computed with Python
3.14 on Windows 11. Without the first `pip` line, `pip install -e ".[analysis,dev]"` installs
the current versions instead, which is fine for using the package but is not the same test.

## Four levels

Each level adds a download to the one before.

| Level | Command | Download | Time | What it shows |
|---|---|---|---|---|
| 0 | `python -m flinch verify` | none | seconds | The numbers of the paper are those of the tables in the repository |
| 1 | `python -m flinch reproduce` | 340 MB | 10 min | The public archives and this code give the 14 velocity tables again |
| 2 | `python -m flinch reproduce --spectra sample` | 1.1 GB more | 5 min more | Ten spectra of the paper, drawn at random, are still the same in the archive |
| 3 | `python -m flinch reproduce --spectra all` | 143 GB more | 3 hours or more | The spectral tables too: Tables 2 and B.1 and Fig. 4 of the paper |

`--sample 30` changes the number of spectra of level 2. `--no-download` uses the data already
on disk. `--out` names another folder for the output. A run that is stopped can be started
again, and what is on disk is not downloaded twice.

## The report

`reproduction/report.txt` has six parts.

1. **Data.** Each input is compared with the one used in the paper by a fingerprint (SHA-256)
   of what the analysis reads from it. `identical` means that the archive still serves the
   same data.
2. **Velocity analysis.** One line per command, with the time it took and the file that
   keeps its output.
3. **Spectra.** How many extracts are identical to those of the paper, and whether the
   spectral analysis was repeated.
4. **Figures.** The figures of the paper, as PDF, in `reproduction/figures/`.
5. **Tables.** Each new table against the one in the repository. `identical` is the same
   text. `same numbers` means that every number agrees to nine significant digits, which is
   what another processor or another version of a library can change. `DIFFERENT` names the
   columns that differ and by how much.
6. **Numbers of the paper.** The 243 numbers of the text and the tables of the paper, each
   against the new tables. A number passes when the paper gives a correct rounding of it.

The last line is `Reproduced.` when no step failed, no table differs and every number agrees.
The command then ends with code 0, and with 1 otherwise.

`results/paper_check.csv` lists the 243 numbers with the place where each appears in the
paper, as the last run of `verify` left them.

## What was run for the paper

On 21 and 22 November 2026 everything was downloaded again into an empty folder and run from
a fresh clone, with the versions of `requirements-lock.txt`.

| What | Result |
|---|---|
| Inputs of the velocity analysis (12 files) | identical, 12 of 12 |
| Velocity tables (14) | identical, byte for byte |
| Spectra (1296 files, 143 GB) | identical, 1296 of 1296 |
| Spectral tables (2) | identical, byte for byte |
| Numbers of the paper (243) | 243 of 243 in agreement |
| Figures of the paper (5) | the same images, pixel by pixel |

The check found two numbers that had been rounded twice in the text. The scatter of the
velocity changes of the HARPS-N flares is 0.40 m/s, not 0.41, and the excess of Appendix C
is 0.43 ± 0.10 m/s, not 0.44 ± 0.11. Both are corrected.

On 22 November 2026 the `reproduce` workflow of the repository ran the same on Linux, from
the public archives, with ten spectra of the sample. It took six minutes. The 12 inputs and
the ten extracts are identical, the 243 numbers agree, and the 14 velocity tables are the
same numbers. The largest difference is in the eleventh significant digit.

## Step by step

`reproduce` runs these commands in this order. Each can be run alone, and then it writes to
`results/`.

```
python -m flinch download
python -m flinch coverage
python -m flinch replication
python -m flinch replication --cleaning
python -m flinch robustness
python -m flinch pilot
python -m flinch numbers
python -m flinch paper-spectra
python -m flinch chromosphere
python -m flinch paper-figures --out figures
python -m flinch verify
```

| Output | Made by | Content |
|---|---|---|
| `results/flare_sample.csv` | `coverage` | The 2122 M and X flares and their coverage by NEID |
| `results/velocity_by_instrument.csv` | `replication` | Mean change, shift of an X1 flare and rotation term, by class and instrument, and both together (Table 1) |
| `results/replication_events.csv` | `replication` | Every flare and control of both instruments, with its velocity change (Fig. 3) |
| `results/replication_profiles.csv` | `replication` | Mean velocity around the peak in 10-minute bins (Fig. 2) |
| `results/early_window.csv` | `replication` | Mean velocity from 60 to 50 minutes before the peak, by class and instrument (Appendix C) |
| `results/cleaning_variants.csv` | `replication --cleaning` | The mean change and the rotation term with other thresholds for dropping days and, for HARPS-N, with the quality flag above 0.9 |
| `results/robustness.csv` | `robustness` | The table of variants with NEID (Table A.1) |
| `results/injections.csv` | `robustness` | A shift added and measured back with NEID (Appendix A) |
| `results/pilot_*.csv` | `pilot` | The first NEID analysis, including the oscillation power |
| `results/text_numbers.csv` | `numbers` | The counts and descriptive numbers of the text: velocities and days, what the cuts remove, the tests of a fair sample, the flare rate and the time in flare |
| `data/spectra/` | `paper-spectra` | The extracts of the 1296 spectra of the paper, each checked against its fingerprint |
| `results/spectral_response.csv` | `chromosphere` | Response of every flare and control, with its errors (Table B.1) |
| `results/spectral_indices.csv` | `chromosphere` | Summary of each index by class band (Table 2) |
| PDF files | `paper-figures` | The example of the method, the mean velocity around the peak, the change of each flare against class and position, and the mean response of the spectra |
| `results/paper_check.csv` | `verify` | Every number of the paper against the tables |

Three environment variables move things. `FLINCH_DATA` is the folder of the downloads
(`data/` by default), `FLINCH_RESULTS` that of the tables (`results/`), and `FLINCH_DATA_END`
the last day of data (see below).

## What is fixed, and how

Four things made the results depend on the day and on the machine. They are now fixed in the
code.

- **The last day of data.** The NEID table grows every clear day and the GOES lists are
  reissued with a later end date, so a later download had more flares, more observations and
  other controls. `DATA_END` in `flinch/config.py` is 13 November 2026. Flares and
  observations from that day on are ignored, whatever the download holds. The last NEID
  observation of the paper is of 12 November 2026.
- **The spectra.** They were fetched with `campaign`, which works through the flares from the
  strongest down until a budget of hours and files runs out. What it fetches depends on the
  connection and on the day. `flinch/reference/spectra_files.csv` lists the 1296 files that
  it fetched for the paper, with the fingerprint of each extract, and `paper-spectra` fetches
  exactly those.
- **The random choices.** Controls and bootstrap use a fixed seed.
- **The numbers of the text.** Counts, percentages and tests that were not in any table are
  now written by `numbers`.

## Limits

What follows can still make a reproduction differ, or makes it expensive.

- **The archives can change the data.** NEID can reprocess its spectra with a newer pipeline
  (the 1296 used here are all of version 1.5.3), and NOAA reissues the GOES files. There is
  no frozen copy of the inputs outside the archives yet. The fingerprints do not prevent a
  change, but they detect it. The report then says which input is `different`, and a table
  that differs has an explanation. The HARPS-N series is a fixed release with a DOI.
- **The spectra are 143 GB.** A level-2 file is 113 MB and the archive does not serve parts
  of a file, so each one is downloaded whole, reduced to an extract of 0.2 MB and deleted.
  The 1296 files took 3 hours and 14 minutes here, at 12 MB per second, which is 9 seconds
  per file. A slower line needs more in proportion. They need 400 MB of free disk at a time
  and leave 260 MB of extracts. A home connection may slow down after tens of GB. In the
  first campaign it fell to a tenth of its speed after 100 GB. In this second download it
  did not. The computer must stay awake, so a laptop should be plugged in and should not
  sleep when the lid closes. Level 2 is the cheap alternative. It does not repeat the
  spectral analysis, but it shows that the archive and the extraction still give the same
  extracts.
- **Some spectra cannot be read.** For 51 exposures of two windows (27 of the X1.3 flare of
  4 July 2026 and 24 of the control of the X4.9 flare of 31 December 2023) the archive
  serves files without the stitched spectrum. They are not in the list, and those two
  windows have fewer spectra than the others. That flare and that control are not among the
  usable ones.
- **The choice of the spectra is not repeated.** The list records which spectra were
  fetched, not a rule that gives them again. The windows are the 20 X-class flares that NEID
  observed at the peak or during the rise, the same hours on the nearest flare-free day for
  14 of them, and the 11 of the 25 flares between M5 and M9 that had a steady clear sky.
  Within a window, every spectrum near the flare was taken and one in two or three farther
  away. Running `campaign` again would not give the same files, because its budget cut the
  last window short and the two windows above lost spectra.
- **Software versions and machines.** With the versions of `requirements-lock.txt` on
  Windows 11 the tables come out identical, byte by byte. On Linux the same versions give
  the same numbers to eleven significant digits, but not the same text, because another
  processor and other mathematical libraries round the last digits differently. Tables are
  therefore compared number by number, not only as text, and the report says
  `same numbers`. The spectral analysis has not been repeated on Linux, because it needs
  the 143 GB. NumPy does not promise the same random numbers in every future version. If
  they changed, the controls drawn and the bootstrap errors would change in their last
  digits.
- **Figures are not compared by the command.** They are drawn again from the new tables.
  For the run described above they were turned into images and compared with those of the
  paper, and the five are the same pixel by pixel. With other versions of Matplotlib or
  other fonts they can differ in details that do not change what they show.
- **Numbers taken from other papers** (the brightening of flares in visible light, the old
  GOES scale) are not computed here.

## Tests

```
python -m pytest              # 120 tests on synthetic data, no network, one minute
python -m pytest -m network   # 2 tests: the archives still answer as the code expects
```

Three more tests compare the real downloads with the tables of the repository. They run
when the data are on disk.
