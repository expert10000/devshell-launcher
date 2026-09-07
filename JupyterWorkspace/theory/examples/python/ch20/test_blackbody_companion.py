import numpy as np
import pytest

from blackbody_companion import (
    A_RAD, C, H, KB, SIGMA, WIEN_B, band_fraction, band_signal,
    brightness_temperature, cavity_mode_count, convolve_gaussian,
    dimensionless_frequency, finite_difference_log_slope,
    fit_graybody_temperature, mean_photon_energy, normalized_gaussian_response,
    photon_number_density, planck_frequency, planck_wavelength,
    rayleigh_jeans_frequency, spectral_radiance_wavelength,
    total_energy_density, total_exitance, two_color_temperature,
)


def test_planck_frequency_positive_and_finite():
    y = planck_frequency(np.geomspace(1e8, 1e16, 500), 3000.0)
    assert np.all(np.isfinite(y)) and np.all(y >= 0.0) and np.max(y) > 0.0


def test_frequency_wavelength_jacobian():
    lam = np.geomspace(0.5e-6, 30e-6, 300)
    nu = C / lam
    lhs = planck_wavelength(lam, 1200.0)
    rhs = planck_frequency(nu, 1200.0) * C / lam**2
    assert np.allclose(lhs, rhs, rtol=3e-13)


def test_rayleigh_jeans_limit():
    nu = np.array([1e8, 3e8, 1e9])
    ratio = planck_frequency(nu, 6000.0) / rayleigh_jeans_frequency(nu, 6000.0)
    assert np.allclose(ratio, 1.0, rtol=3e-5)


def test_integrated_energy_matches_a_t4():
    t = 900.0
    lam = np.geomspace(1e-9, 5e-2, 120000)
    numerical = np.trapezoid(planck_wavelength(lam, t), lam)
    assert numerical == pytest.approx(total_energy_density(t), rel=3e-5)


def test_stefan_relation():
    for t in (100.0, 300.0, 3000.0):
        assert total_exitance(t) == pytest.approx(C * total_energy_density(t) / 4.0, rel=1e-14)
        assert total_exitance(t) == pytest.approx(SIGMA * t**4, rel=1e-14)


def test_wien_peak_wavelength():
    t = 1800.0
    lam = np.geomspace(0.2e-6, 20e-6, 20000)
    peak = lam[np.argmax(planck_wavelength(lam, t))]
    assert peak == pytest.approx(WIEN_B / t, rel=4e-4)


def test_photon_number_scaling():
    assert photon_number_density(600.0) / photon_number_density(300.0) == pytest.approx(8.0)


def test_mean_photon_energy_constant_ratio():
    ratio = mean_photon_energy(1200.0) / (KB * 1200.0)
    assert ratio == pytest.approx(2.701178, rel=3e-6)


def test_cavity_mode_count_scaling():
    n1 = cavity_mode_count(0.5, 1e9, 2e9)
    n2 = cavity_mode_count(1.0, 1e9, 2e9)
    assert n2 == pytest.approx(2.0 * n1)


def test_brightness_temperature_round_trip():
    lam = np.array([1.5e-6, 3e-6, 8e-6])
    b = spectral_radiance_wavelength(lam, 1450.0)
    assert np.allclose(brightness_temperature(lam, b), 1450.0, rtol=2e-13)


def test_normalized_response_integrates_to_one():
    lam = np.linspace(2e-6, 8e-6, 5000)
    r = normalized_gaussian_response(lam, 5e-6, 0.5e-6)
    assert np.trapezoid(r, lam) == pytest.approx(1.0, rel=2e-12)


def test_band_signal_gray_emissivity_scaling():
    lam = np.linspace(2e-6, 8e-6, 4000)
    r = normalized_gaussian_response(lam, 5e-6, 0.8e-6)
    full = band_signal(lam, 1000.0, r)
    gray = band_signal(lam, 1000.0, r, emissivity=0.6)
    assert gray == pytest.approx(0.6 * full, rel=2e-12)


def test_band_fraction_valid_range():
    f = band_fraction(300.0, 8e-6, 14e-6)
    assert 0.2 < f < 0.5


def test_gaussian_convolution_preserves_constant():
    lam = np.linspace(1e-6, 10e-6, 2000)
    y = np.full_like(lam, 3.0)
    out = convolve_gaussian(lam, y, 0.2e-6)
    assert np.allclose(out, 3.0, atol=1e-12)


def test_graybody_fit_recovers_temperature_and_scale():
    lam = np.linspace(2e-6, 12e-6, 80)
    true_t, true_scale = 1120.0, 0.72
    y = true_scale * spectral_radiance_wavelength(lam, true_t)
    sigma = np.maximum(0.01 * y, np.max(y) * 1e-6)
    grid = np.arange(1000.0, 1241.0, 2.0)
    fit = fit_graybody_temperature(lam, y, sigma, grid)
    assert fit.temperature == pytest.approx(true_t, abs=2.0)
    assert fit.scale == pytest.approx(true_scale, rel=2e-4)
    assert fit.chi_square < 1e-8


def test_two_color_round_trip():
    lam1, lam2, t = 1.2e-6, 1.8e-6, 2400.0
    b = spectral_radiance_wavelength(np.array([lam1, lam2]), t)
    inferred = two_color_temperature(lam1, lam2, float(b[0] / b[1]))
    assert inferred == pytest.approx(t, rel=1e-9)


def test_t4_log_slope():
    t = np.geomspace(100.0, 5000.0, 100)
    slope = finite_difference_log_slope(t, np.array([total_exitance(v) for v in t]))
    assert np.allclose(slope[2:-2], 4.0, atol=1e-10)


def test_dimensionless_frequency_scaling():
    assert dimensionless_frequency(2e12, 600.0) == pytest.approx(dimensionless_frequency(1e12, 300.0))


def test_invalid_inputs_raise():
    with pytest.raises(ValueError):
        planck_wavelength(np.array([-1.0]), 300.0)
    with pytest.raises(ValueError):
        cavity_mode_count(-1.0, 1.0, 2.0)
    with pytest.raises(ValueError):
        band_fraction(300.0, 10e-6, 8e-6)
