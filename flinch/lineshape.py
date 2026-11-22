"""Shape of the mean photospheric line (the cross-correlation function) through a flare.

The cross-correlation function (CCF) of a spectrum with a line mask is an average line profile
built from thousands of lines, so its shape is known to a few parts in 10^5 per spectrum. A
flare can change that shape (weaker or filled-in lines in the flaring area) without moving its
centre, which is what the radial velocity measures.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.interpolate import CubicSpline
from scipy.optimize import least_squares

CONTINUUM_KMS = (20.0, 60.0)  # distance from the line centre used as continuum
FIT_HALF_WIDTH_KMS = 12.0
CONVERGENCE_STEPS = 40  # real profiles need 3 to 6 after the first fit
CONVERGED = 1.0e-13  # a step smaller than this, relative to each parameter, ends the fit


def velocity_grid(start: float, step: float, n: int) -> np.ndarray:
    return start + step * np.arange(n)


def normalize(velocity: np.ndarray, ccf: np.ndarray) -> np.ndarray:
    """CCF divided by its continuum, taken as the mean of both wings."""
    centre = velocity[np.argmin(ccf)]
    distance = np.abs(velocity - centre)
    wings = (distance >= CONTINUUM_KMS[0]) & (distance <= CONTINUUM_KMS[1])
    return ccf / ccf[wings].mean()


def gaussian_residual(parameters: np.ndarray, v: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Inverted Gaussian minus the profile, and its derivatives with respect to the parameters.

    The parameters are the centre (km/s), the depth, the standard deviation (km/s) and the level
    of the continuum.
    """
    centre, depth, sigma, level = parameters
    z = (v - centre) / sigma
    bell = np.exp(-0.5 * z * z)
    derivatives = np.column_stack([-depth * bell * z / sigma, -bell, -depth * bell * z * z / sigma, np.ones_like(v)])
    return level - depth * bell - y, derivatives


def gaussian_parameters(v: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Least-squares parameters of an inverted Gaussian, carried to convergence.

    ``least_squares`` stops when its step is small, not when it is zero. It leaves the depth and
    the width within a few hundredths of a part per million of the minimum, at a point that
    depends on the machine. Gauss-Newton steps with exact derivatives then take the fit to the
    limit of the arithmetic, so that every machine gives the same parameters.
    """
    start = least_squares(lambda p: gaussian_residual(p, v, y)[0], [v[np.argmin(y)], 1.0 - y.min(), 3.5, 1.0]).x
    parameters = start.copy()
    for _ in range(CONVERGENCE_STEPS):
        residual, derivatives = gaussian_residual(parameters, v, y)
        step = np.linalg.lstsq(derivatives, -residual, rcond=None)[0]
        if not np.all(np.isfinite(step)):
            break
        parameters = parameters + step
        if np.all(np.abs(step) <= CONVERGED * np.maximum(1.0, np.abs(parameters))):
            return parameters
    return start  # a profile that is not a line: the steps do not settle, and the first fit stands


def gaussian_fit(velocity: np.ndarray, profile: np.ndarray) -> tuple[float, float, float]:
    """Centre (km/s), depth and full width at half maximum (km/s) of an inverted Gaussian."""
    guess = velocity[np.argmin(profile)]
    use = np.abs(velocity - guess) <= FIT_HALF_WIDTH_KMS
    centre, depth, sigma, _ = gaussian_parameters(velocity[use], profile[use])
    return float(centre), float(depth), float(2.3548200450309493 * abs(sigma))


def bisector_span(velocity: np.ndarray, profile: np.ndarray, top=(0.10, 0.40), bottom=(0.60, 0.90)) -> float:
    """Bisector inverse slope in m/s: mean bisector near the top of the line minus near the bottom.

    The levels are fractions of the line depth, measured from the continuum.
    """
    # Work on a finely resampled profile: taking the minimum and the wings from the 0.25 km/s
    # samples makes the span jump by more than 1 m/s whenever the lowest sample changes.
    coarse_min = velocity[int(np.argmin(profile))]
    fine_v = np.arange(coarse_min - 15.0, coarse_min + 15.0, 0.005)
    fine_p = CubicSpline(velocity, profile)(fine_v)
    i_min = int(np.argmin(fine_p))
    depth = 1.0 - fine_p[i_min]
    levels = 1.0 - depth * np.linspace(0.05, 0.95, 91)
    blue_v, blue_p = fine_v[: i_min + 1][::-1], fine_p[: i_min + 1][::-1]  # from the core outwards
    red_v, red_p = fine_v[i_min:], fine_p[i_min:]
    # Keep the monotonic part of each wing, so that np.interp gets increasing abscissae.
    blue_end = int(np.argmax(blue_p >= levels[0])) + 1 if np.any(blue_p >= levels[0]) else len(blue_p)
    red_end = int(np.argmax(red_p >= levels[0])) + 1 if np.any(red_p >= levels[0]) else len(red_p)
    bisector = 0.5 * (
        np.interp(levels, blue_p[:blue_end], blue_v[:blue_end]) + np.interp(levels, red_p[:red_end], red_v[:red_end])
    )
    fraction = (1.0 - levels) / depth
    upper = bisector[(fraction >= top[0]) & (fraction <= top[1])].mean()
    lower = bisector[(fraction >= bottom[0]) & (fraction <= bottom[1])].mean()
    return float((upper - lower) * 1000.0)


def measure(ccfs: np.ndarray, start: float, step: float) -> pd.DataFrame:
    """Shape parameters of each CCF: centre (m/s), depth, width (km/s), area (km/s) and bisector span (m/s)."""
    velocity = velocity_grid(start, step, ccfs.shape[1])
    rows = []
    for ccf in ccfs:
        profile = normalize(velocity, ccf)
        centre, depth, fwhm = gaussian_fit(velocity, profile)
        near = np.abs(velocity - centre) <= CONTINUUM_KMS[0]
        rows.append(
            {
                "ccf_rv_ms": centre * 1000.0,
                "ccf_depth": depth,
                "ccf_fwhm_kms": fwhm,
                "ccf_area_kms": float(np.sum(1.0 - profile[near]) * step),
                "ccf_bis_ms": bisector_span(velocity, profile),
            }
        )
    return pd.DataFrame(rows)


def shifted_profiles(ccfs: np.ndarray, start: float, step: float, half_width_kms: float = 15.0):
    """Normalized CCFs resampled on a common grid centred on each line (removes velocity shifts).

    Returns the grid (km/s from the line centre) and the array (spectra, grid points).
    """
    velocity = velocity_grid(start, step, ccfs.shape[1])
    grid = np.arange(-half_width_kms, half_width_kms + 0.5 * step, step)
    out = np.empty((len(ccfs), len(grid)))
    for k, ccf in enumerate(ccfs):
        profile = normalize(velocity, ccf)
        centre, _, _ = gaussian_fit(velocity, profile)
        # A cubic spline: linear interpolation of a line sampled every 0.25 km/s is wrong by up
        # to a few parts in 10^4 at the core, more than the changes looked for.
        out[k] = CubicSpline(velocity, profile)(centre + grid)
    return grid, out
