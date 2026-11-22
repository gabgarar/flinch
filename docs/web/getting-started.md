# Getting started

## Installation

The package needs Python 3.10 or later.

```
git clone https://github.com/gabgarar/flinch.git
cd flinch
python -m venv venv
venv/Scripts/python -m pip install -e ".[analysis,dev]"     # Windows
venv/bin/python -m pip install -e ".[analysis,dev]"         # Linux and macOS
```

The distribution is called `flinch-rv` (the name `flinch` is taken on PyPI by an unrelated
package); the import name is `flinch`.

| Extra | Adds | Needed for |
|---|---|---|
| `analysis` | SciPy, Matplotlib, Astropy | Figures, line shapes, reading the spectra |
| `dev` | pytest | The tests |
| `docs` | mkdocs-material, mkdocstrings, mkdocs-static-i18n | Building this site |
| `notebooks` | ipykernel | Notebooks |

## The commands

Everything runs through `python -m flinch <command>`.

| Command | What it does | Time | Download |
|---|---|---|---|
| `download` | Everything the velocity analysis needs: flare lists, positions and one-minute fluxes (GOES), and the velocities of NEID and HARPS-N | 3 min | 340 MB |
| `coverage` | Which flares happened while NEID was observing | seconds | none |
| `replication` | The velocity measurement with NEID and with HARPS-N, and both together | 20 s | none |
| `robustness` | The NEID result under other windows, backgrounds and controls | 10 s | none |
| `pilot` | The first NEID analysis, with the oscillation power | 10 s | none |
| `numbers` | The counts and descriptive numbers of the text | 5 s | none |
| `spectra` | Extracts of every spectrum in a time window | 10 s per spectrum | 113 MB per spectrum |
| `campaign` | Unattended `spectra` for the strongest flares, or for their control windows | hours | 113 MB per spectrum |
| `paper-spectra` | Exactly the 1296 spectra of the paper, each checked against its fingerprint | 3 hours or more | 143 GB |
| `chromosphere` | Response of the spectral indices to the flares with spectra | 1 min | none |
| `paper-figures` | The figures of the paper, as PDF in journal style | 20 s | none |
| `verify` | Every number of the paper against the tables in `results/` | seconds | none |
| `reproduce` | All of the above in order, with a report of what agrees (see [Reproducing the paper](reproduce.md)) | 10 min | 340 MB, or 143 GB more with the spectra |

A first session:

```
python -m flinch download
python -m flinch coverage
python -m flinch replication
python -m pytest
```

## Where the data go

Downloads go to `data/` inside the repository, or to the folder named by the environment
variable `FLINCH_DATA`. Tables go to `results/`, or to the folder named by `FLINCH_RESULTS`,
and figures to `docs/web/img/`. `reproduce` writes everything to `reproduction/` and leaves
the repository as it was.

Flares and observations after 12 November 2026 are ignored, so that a later download gives
the same sample ([why](reproduce.md#what-is-fixed-and-how)).

!!! warning "Spectra are heavy to download"
    A level-2 NEID spectrum is 113 MB and the archive does not serve byte ranges, so each one
    is downloaded whole, reduced to a 0.2 MB extract and deleted. The 1296 spectra of the
    paper move 143 GB through the network and keep 260 MB. The computer must stay awake: on
    a laptop, keep it plugged in and with the lid open.

## Tests

```
python -m pytest
```

The tests use synthetic data and do not touch the network.
