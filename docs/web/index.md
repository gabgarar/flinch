# flinch

Solar flares in Sun-as-a-star radial velocities.

*Do solar flares contaminate the radial-velocity detection of Earth analogues?*

To find a planet like the Earth around a star like the Sun, the velocity of the star has to be
measured to about 10 cm/s: the Earth moves the Sun by 9 cm/s. Some of the spectrographs built
for that also observe the Sun every clear day, as if it were a distant star. This project
cross-matches those solar velocities with the flares recorded by the GOES satellites and asks:

1. Does a flare move the radial velocity of the Sun seen as a star?
2. From which flare size, and by how much?
3. What does that mean for planet searches?

It uses two instruments that watch the Sun at different hours and therefore see different
flares: NEID (Arizona) and HARPS-N (La Palma).

## The answer

Solar flares do not significantly contaminate the detection of Earth analogues by radial
velocity. This has been shown for the Sun, not for Sun-like stars in general.

| Question | Answer | Evidence |
|---|---|---|
| Does the velocity change during a flare? | No, within 7 cm/s | 254 measurements of 253 flares of class M and X: −0.029 ± 0.026 m/s. NEID alone: −0.035 ± 0.035 (139 flares). HARPS-N alone: −0.021 ± 0.039 (115) |
| Do larger flares move it more? | No | 18 flares of class X: −0.074 ± 0.072 m/s. No change, but the limit, 0.2 m/s, is twice the signal of the Earth |
| Is there a rotation signature (opposite sign east and west)? | No | −0.006 ± 0.038 m/s for an X1 flare at the limb, within a factor of 1.6 to 3.5 of the largest shift expected |
| Would a signal have been seen? | Yes | 98 % of a shift added to the data is measured back |
| Do the spectra see the flares at all? | Yes | Ca II H and K and H alpha brighten in all 14 flares on the disc with spectra, by 2 to 5 parts per thousand |
| How much of the time is the Sun flaring? | 1.6 % | 358 flares of class M or X per year on average from 2020 to 2026, counted from start to end (19 minutes in the median); 3.8 % in 2024, the most active year |

The Sun does not flinch, but it blushes: the chromospheric lines brighten while the velocity
stays put. See [Results](results.md).

![Mean velocity around the flare peak, NEID and HARPS-N](img/two_instruments_profiles.png)

## What is in this documentation

| Page | Content |
|---|---|
| [Getting started](getting-started.md) | Installation and the commands |
| [GOES flares](data/goes.md) | The flare lists: what they contain, an example, how they are processed |
| [NEID velocities](data/neid-velocities.md) | The velocity table: columns, quality cuts, daily trend |
| [NEID spectra](data/neid-spectra.md) | The spectra: what is extracted from each 113 MB file |
| [HARPS-N velocities](data/harpsn.md) | The second instrument: what it is and how it is processed |
| [Method](method.md) | The measurement in four steps |
| [Results](results.md) | Tables and figures |
| [Reproducing the paper](reproduce.md) | One command that runs everything and checks the paper; what each step costs; what can still differ |

All data are public and need no registration. The site is available in English and in
Spanish: use the language button at the top of the page.
