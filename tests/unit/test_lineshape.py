import numpy as np
import pytest

from flinch import lineshape

START, STEP, N = -100.0, 0.25, 804
VELOCITY = lineshape.velocity_grid(START, STEP, N)


def line(centre=-0.64, depth=0.45, fwhm=7.5, skew=0.0, level=3.0e9):
    """An absorption line on a continuum of arbitrary level; ``skew`` shifts its upper part."""
    sigma = fwhm / 2.3548200450309493
    core = np.exp(-0.5 * ((VELOCITY - centre) / sigma) ** 2)
    wide = np.exp(-0.5 * ((VELOCITY - centre - skew) / (1.6 * sigma)) ** 2)
    return level * (1.0 - depth * (0.7 * core + 0.3 * wide))


def test_gaussian_parameters_are_recovered():
    table = lineshape.measure(np.vstack([line(), line(centre=-0.63, depth=0.4505)]), START, STEP)
    assert table.loc[0, "ccf_rv_ms"] == pytest.approx(-640.0, abs=0.5)
    assert table.loc[1, "ccf_rv_ms"] - table.loc[0, "ccf_rv_ms"] == pytest.approx(10.0, abs=0.05)
    # a depth change of one part in a thousand is measured to a few parts per million
    assert table.loc[1, "ccf_depth"] / table.loc[0, "ccf_depth"] - 1 == pytest.approx(0.4505 / 0.45 - 1, abs=1e-5)
    assert table.loc[0, "ccf_fwhm_kms"] == pytest.approx(table.loc[1, "ccf_fwhm_kms"], rel=2e-5)


def test_the_fit_is_carried_to_convergence_and_does_not_depend_on_where_it_starts(monkeypatch):
    profile = lineshape.normalize(VELOCITY, line(skew=0.2))  # not a Gaussian: the fit leaves residuals
    use = np.abs(VELOCITY - VELOCITY[np.argmin(profile)]) <= lineshape.FIT_HALF_WIDTH_KMS
    v, y = VELOCITY[use], profile[use]
    found = lineshape.gaussian_parameters(v, y)
    # at the minimum the residuals have no component along any derivative: the next step is zero
    residual, derivatives = lineshape.gaussian_residual(found, v, y)
    step = np.linalg.lstsq(derivatives, -residual, rcond=None)[0]
    assert np.all(np.abs(step) <= 1e-12 * np.maximum(1.0, np.abs(found)))
    # a first fit that stops elsewhere, as on another machine, ends at the same parameters
    first = lineshape.least_squares

    def moved(function, start, **options):
        fit = first(function, start, **options)
        fit.x = fit.x * (1.0 + 1.0e-6 * np.array([1.0, -1.0, 1.0, -1.0]))
        return fit

    monkeypatch.setattr(lineshape, "least_squares", moved)
    again = lineshape.gaussian_parameters(v, y)
    assert np.allclose(again, found, rtol=1e-11, atol=0.0)  # one part in a million moved, 1e-5 ppm left


def test_a_profile_that_is_not_a_line_keeps_the_first_fit():
    flat = np.ones(97)
    found = lineshape.gaussian_parameters(np.linspace(-12.0, 12.0, 97), flat)
    assert np.all(np.isfinite(found))


def test_bisector_span_is_zero_for_a_symmetric_line_and_follows_the_asymmetry():
    symmetric, red, blue = lineshape.measure(np.vstack([line(), line(skew=0.3), line(skew=-0.3)]), START, STEP)[
        "ccf_bis_ms"
    ]
    assert symmetric == pytest.approx(0.0, abs=0.1)  # the 0.25 km/s sampling leaves a few cm/s
    assert red > 5.0 and blue == pytest.approx(-red, rel=1e-3)


def test_shifted_profiles_remove_the_velocity_shift():
    grid, profiles = lineshape.shifted_profiles(np.vstack([line(), line(centre=-0.2)]), START, STEP)
    assert grid[0] == -15.0 and grid[-1] == 15.0
    assert np.allclose(profiles[0], profiles[1], atol=1e-5)
    assert profiles[0].min() == pytest.approx(1.0 - 0.45, abs=1e-3)
