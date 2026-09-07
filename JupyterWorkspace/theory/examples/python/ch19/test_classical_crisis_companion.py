import math
import numpy as np
import pytest

from classical_crisis_companion import (
    C, E_CHARGE, H, K_B, M_E, DiagnosticDashboard,
    activation_ratio, compton_shift, de_broglie_wavelength_from_energy,
    diagnostic_activation_fraction, empirical_stopping_potential,
    fit_origin_slope, gaussian_line_spectrum, quadratic_relative_spacing,
    rayleigh_jeans_density, rayleigh_jeans_integrated, weighted_chi_square,
)


def test_rayleigh_jeans_zero_frequency():
    assert rayleigh_jeans_density(0.0, 300.0) == pytest.approx(0.0)


def test_ultraviolet_cutoff_cubic_scaling():
    u1 = rayleigh_jeans_integrated(1e13, 300.0)
    u2 = rayleigh_jeans_integrated(2e13, 300.0)
    assert u2 / u1 == pytest.approx(8.0)


def test_activation_ratio_definition():
    assert activation_ratio(K_B * 100.0, 100.0) == pytest.approx(1.0)


def test_activation_fraction_limits():
    low = diagnostic_activation_fraction(1e-21, 1.0)
    high = diagnostic_activation_fraction(1e-21, 1e5)
    assert low < 1e-20
    assert high > 0.99


def test_photoelectric_threshold_and_slope():
    phi = 2.0 * E_CHARGE
    nu0 = phi / H
    assert empirical_stopping_potential(nu0 * 0.99, phi) == pytest.approx(0.0)
    dv = empirical_stopping_potential(nu0 + 1e13, phi)
    assert dv == pytest.approx(H * 1e13 / E_CHARGE)


def test_compton_extrema():
    lamc = H / (M_E * C)
    assert compton_shift(0.0) == pytest.approx(0.0)
    assert compton_shift(math.pi) == pytest.approx(2.0 * lamc)


def test_de_broglie_inverse_sqrt_energy():
    l1 = de_broglie_wavelength_from_energy(10.0 * E_CHARGE)
    l4 = de_broglie_wavelength_from_energy(40.0 * E_CHARGE)
    assert l1 / l4 == pytest.approx(2.0)


def test_weighted_chi_square():
    assert weighted_chi_square([1, 2], [0, 4], [1, 2]) == pytest.approx(2.0)


def test_fit_origin_slope_exact():
    x = np.arange(1.0, 6.0)
    assert fit_origin_slope(x, 3.5 * x) == pytest.approx(3.5)


def test_gaussian_line_area():
    x = np.linspace(-10.0, 10.0, 20001)
    y = gaussian_line_spectrum(x, [0.0], [2.0], 0.5)
    assert np.trapezoid(y, x) == pytest.approx(2.0, rel=1e-5)


def test_coarse_resolution_reduces_peak_contrast():
    x = np.linspace(-4.0, 4.0, 4001)
    fine = gaussian_line_spectrum(x, [-0.5, 0.5], [1, 1], 0.08)
    coarse = gaussian_line_spectrum(x, [-0.5, 0.5], [1, 1], 0.8)
    assert fine.max() / fine[len(x)//2] > coarse.max() / coarse[len(x)//2]


def test_correspondence_spacing_decreases():
    assert quadratic_relative_spacing(100.0) < quadratic_relative_spacing(10.0)


def test_dashboard_validation():
    assert DiagnosticDashboard(0.5, 2.0, 100.0, 1.2).as_array().shape == (4,)
    with pytest.raises(ValueError):
        DiagnosticDashboard(-1.0, 1.0, 1.0, 1.0).as_array()


def test_domain_validation():
    with pytest.raises(ValueError):
        rayleigh_jeans_density(1.0, 0.0)
    with pytest.raises(ValueError):
        de_broglie_wavelength_from_energy(-1.0)
