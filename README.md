# flinch

[![tests](https://github.com/gabgarar/flinch/actions/workflows/tests.yml/badge.svg)](https://github.com/gabgarar/flinch/actions/workflows/tests.yml)
[![docs](https://github.com/gabgarar/flinch/actions/workflows/docs.yml/badge.svg)](https://gabgarar.github.io/flinch/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: BSD-3-Clause](https://img.shields.io/badge/license-BSD--3--Clause-blue.svg)](LICENSE)

**Do solar flares contaminate the radial-velocity detection of Earth analogues?**

`flinch` measures what a solar flare does to the radial velocity of the Sun observed as a star.
It pairs the solar velocities of two planet-search spectrographs, NEID and HARPS-N, with the
flares recorded by the GOES satellites, and compares every flare with flare-free days at the
same hour.

Documentation, in English and Spanish: **<https://gabgarar.github.io/flinch/>**

## Result

- The radial velocity of the Sun does not change during M- and X-class flares. The mean change
  is −0.029 ± 0.026 m/s over 254 measurements, below 0.07 m/s at 95 % confidence. An Earth
  analogue moves the Sun by 0.09 m/s.
- NEID and HARPS-N observed different flares, and they agree.
- The same NEID spectra do record the flares: Ca II H and K and H alpha brighten in all 14
  flares on the disc with usable spectra.

This has been shown for the Sun, not for Sun-like stars in general. Figures, tables and
limitations are on the [results page](https://gabgarar.github.io/flinch/results/).

## Install

```
git clone https://github.com/gabgarar/flinch.git
cd flinch
python -m venv venv
venv/Scripts/python -m pip install -e ".[analysis,dev]"
```

On Linux and macOS the interpreter is `venv/bin/python`. Python 3.10 or later.

## Use

```
python -m flinch download      # flare lists and the velocities of NEID and HARPS-N into data/ (340 MB)
python -m flinch replication   # the measurement with NEID and with HARPS-N
python -m flinch robustness    # the same under other analysis choices
python -m pytest               # tests, no network needed
```

## Reproduce the paper

```
python -m flinch reproduce
```

One command downloads the public data (340 MB), runs every step, compares each table with
the one in `results/` and checks the 255 numbers of the paper against the new tables. It
takes about ten minutes and writes a report to `reproduction/`. The spectra are 143 GB and
are left out unless asked for (`--spectra sample` or `--spectra all`).
`python -m flinch verify` alone checks the numbers of the paper against the tables of the
repository, in seconds and without any download.

The levels, the cost of each, every command with the table it writes, and what can still
make a reproduction differ are in
[Reproducing the paper](https://gabgarar.github.io/flinch/reproduce/).

## Data

All sources are public and need no registration.

| Data | Source |
|---|---|
| Flare list, positions and X-ray fluxes | GOES-16 and GOES-18 XRS science-quality products, NOAA/NCEI |
| Solar radial velocities and spectra | NEID solar archive, NExScI |
| Solar radial velocities of a second instrument | HARPS-N solar data release (Dumusque et al. 2026), DACE |

## Cite

> García, G. (2026). *flinch: solar flares in Sun-as-a-star radial velocities* (v0.1.0).
> <https://github.com/gabgarar/flinch>

GitHub shows a ready-made citation under "Cite this repository", generated from
[CITATION.cff](CITATION.cff). A paper is in preparation. The acknowledgements that the data
providers ask for are on the [Cite page](https://gabgarar.github.io/flinch/cite/).

## Development note

AI-assisted tools provided support during software development, data analysis, technical
documentation, and language editing. All scientific and methodological decisions, final
implementation, testing, validation, and maintenance remain the responsibility of the author.

## Licence

BSD 3-Clause, see [LICENSE](LICENSE).
