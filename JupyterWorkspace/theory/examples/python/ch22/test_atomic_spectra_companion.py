import numpy as np
import pytest

from atomic_spectra_companion import (
    A0, ALPHA, C, E_CHARGE, H, M_D, M_E, M_P, R_INF, RYDBERG_EV,
    adjacent_transition_frequency_hz, bohr_energy_ev, bohr_radius_m,
    bohr_speed_m_s, classical_orbital_frequency_hz, doppler_fwhm_frequency_hz,
    fine_structure_scale_ev, finite_mass_rydberg, gaussian_profile,
    isotope_shift_wavelength_m, photon_energy_ev_from_wavelength,
    reconstruct_ritz_terms, reduced_mass, resolving_power, rydberg_wavenumber,
    series_limit_wavelength_m, series_wavelength_m, synthetic_line_spectrum,
    transition_energy_ev, wavelength_from_photon_energy_ev,
    zeeman_frequency_shift_hz,
)


def test_photon_conversion_round_trip():
    wavelength = 486.133e-9
    energy = photon_energy_ev_from_wavelength(wavelength)
    assert wavelength_from_photon_energy_ev(energy) == pytest.approx(wavelength, rel=1e-14)


def test_reduced_mass_bounds():
    mu = reduced_mass(M_E, M_P)
    assert 0.0 < mu < M_E
    assert mu / M_E == pytest.approx(1.0 / (1.0 + M_E / M_P), rel=1e-14)


def test_finite_mass_rydberg_less_than_infinite_mass():
    assert finite_mass_rydberg(M_P) < R_INF
    assert finite_mass_rydberg(M_D) > finite_mass_rydberg(M_P)


def test_rydberg_balmer_alpha():
    wavelength = series_wavelength_m(2, 3, finite_mass_rydberg(M_P))
    assert wavelength == pytest.approx(656.47e-9, rel=5e-4)


def test_series_limit():
    assert series_limit_wavelength_m(2, R_INF) == pytest.approx(4.0 / R_INF)


def test_bohr_energy_scaling():
    assert bohr_energy_ev(1) == pytest.approx(-RYDBERG_EV)
    assert bohr_energy_ev(2) == pytest.approx(bohr_energy_ev(1) / 4.0)
    assert bohr_energy_ev(1, 2) == pytest.approx(4.0 * bohr_energy_ev(1))


def test_transition_energy_matches_level_difference():
    assert transition_energy_ev(2, 3) == pytest.approx(bohr_energy_ev(3) - bohr_energy_ev(2))


def test_bohr_radius_and_speed_scaling():
    assert bohr_radius_m(1) == pytest.approx(A0)
    assert bohr_radius_m(3) == pytest.approx(9.0 * A0)
    assert bohr_radius_m(1, 2) == pytest.approx(A0 / 2.0)
    assert bohr_speed_m_s(1, 2) == pytest.approx(2.0 * ALPHA * C)


def test_correspondence_ratio_approaches_one():
    ratios = []
    for n in (10, 30, 100):
        ratios.append(adjacent_transition_frequency_hz(n) / classical_orbital_frequency_hz(n))
    assert abs(ratios[-1] - 1.0) < abs(ratios[0] - 1.0)
    assert ratios[-1] == pytest.approx(1.0, rel=0.02)


def test_isotope_shift_sign_and_scale():
    shift = isotope_shift_wavelength_m(2, 3)
    assert shift < 0.0  # deuterium has larger R and shorter wavelength
    assert abs(shift) < 1e-9


def test_zeeman_frequency_linear_scaling():
    one = zeeman_frequency_shift_hz(1, 1.0)
    assert zeeman_frequency_shift_hz(2, 0.5) == pytest.approx(one)


def test_fine_structure_z_scaling():
    assert fine_structure_scale_ev(2, 2) / fine_structure_scale_ev(2, 1) == pytest.approx(16.0)


def test_resolving_power():
    assert resolving_power(500e-9, 0.01e-9) == pytest.approx(50_000.0)


def test_gaussian_area():
    grid = np.linspace(-5.0, 5.0, 10001)
    profile = gaussian_profile(grid, 0.0, 0.5, area=3.0)
    assert np.trapezoid(profile, grid) == pytest.approx(3.0, rel=1e-12)


def test_doppler_width_temperature_scaling():
    f = 5e14
    m = M_P
    width1 = doppler_fwhm_frequency_hz(f, 300.0, m)
    width4 = doppler_fwhm_frequency_hz(f, 1200.0, m)
    assert width4 == pytest.approx(2.0 * width1)


def test_synthetic_spectrum_area():
    grid = np.linspace(400e-9, 700e-9, 20000)
    spec = synthetic_line_spectrum(grid, [486e-9, 656e-9], 0.2e-9, [2.0, 3.0])
    assert np.trapezoid(spec, grid) == pytest.approx(5.0, rel=1e-10)


def test_ritz_reconstruction_exact_network():
    # Terms T=[0,-10000,-18000,-24000]; observed lines T_lower-T_upper.
    true_terms = np.array([0.0, -10_000.0, -18_000.0, -24_000.0])
    lo = np.array([0, 0, 1, 1, 2])
    up = np.array([1, 2, 2, 3, 3])
    y = true_terms[lo] - true_terms[up]
    fit = reconstruct_ritz_terms(lo, up, y, np.ones_like(y), 4, 0)
    assert np.allclose(fit.term_values_m_inv, true_terms, atol=1e-9)
    assert fit.chi_square < 1e-18


def test_ritz_rejects_disconnected_singular_network():
    lo = np.array([0])
    up = np.array([1])
    with pytest.raises(np.linalg.LinAlgError):
        reconstruct_ritz_terms(lo, up, np.array([1.0]), np.array([1.0]), 3, 0)


def test_invalid_inputs_raise():
    with pytest.raises(ValueError):
        rydberg_wavenumber(3, 2)
    with pytest.raises(ValueError):
        bohr_energy_ev(0)
    with pytest.raises(ValueError):
        gaussian_profile(np.array([1.0, 0.0]), 0.5, 0.1)
