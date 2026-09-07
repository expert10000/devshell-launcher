import numpy as np
import pytest

from photon_evidence_companion import (
    C, E_CHARGE, H, LAMBDA_C, M_E, M_E_C2_EV,
    chi_square, common_mode_covariance, compton_edge_ev, compton_recoil_energy_ev,
    compton_scattered_energy_ev, compton_shift, evaluate_calibration,
    finite_difference_jacobian, gaussian_response, generalized_linear_fit,
    infer_scatterer_mass, photon_energy_ev, photoelectric_stopping_potential,
    polynomial_energy_calibration, propagate_covariance, quantum_efficiency,
    recoil_electron_angle_rad, retarding_current, synthetic_compton_spectrum,
    threshold_frequency, threshold_wavelength,
)


def test_photon_energy_exact_scaling():
    assert photon_energy_ev(2e15) == pytest.approx(2.0 * photon_energy_ev(1e15))


def test_threshold_round_trip():
    phi = 4.3
    assert photon_energy_ev(threshold_frequency(phi)) == pytest.approx(phi, rel=1e-14)
    assert threshold_wavelength(phi) * threshold_frequency(phi) == pytest.approx(C, rel=1e-14)


def test_stopping_potential_line_and_contact_offset():
    nu = np.array([8e14, 9e14])
    raw = photoelectric_stopping_potential(nu, 2.1)
    shifted = photoelectric_stopping_potential(nu, 2.1, 0.17)
    assert np.allclose(shifted - raw, 0.17)
    assert (raw[1] - raw[0]) / (nu[1] - nu[0]) == pytest.approx(H / E_CHARGE)


def test_quantum_efficiency_round_trip():
    nu, power, eta = 6e14, 2e-3, 0.23
    current = eta * power / (H * nu) * E_CHARGE
    assert quantum_efficiency(current, power, nu) == pytest.approx(eta)


def test_retarding_current_limits():
    v = np.array([-3.0, 0.0, 3.0])
    current = retarding_current(v, 1.2, saturation_current_a=2.0, resolution_v=0.05)
    assert current[0] < 1e-12
    assert current[-1] == pytest.approx(2.0, rel=1e-12)


def test_generalized_linear_fit_exact():
    x = np.arange(5.0)
    y = 2.5 * x - 1.2
    fit = generalized_linear_fit(x, y, np.eye(5) * 0.04)
    assert fit.slope == pytest.approx(2.5)
    assert fit.intercept == pytest.approx(-1.2)
    assert fit.chi_square < 1e-24


def test_common_mode_covariance_structure():
    cov = common_mode_covariance(np.array([1.0, 2.0, 3.0]), 0.5)
    assert np.allclose(np.diag(cov), np.array([1.25, 4.25, 9.25]))
    assert cov[0, 2] == pytest.approx(0.25)


def test_compton_shift_limits():
    assert compton_shift(0.0) == pytest.approx(0.0, abs=1e-30)
    assert compton_shift(np.pi / 2) == pytest.approx(LAMBDA_C)
    assert compton_shift(np.pi) == pytest.approx(2.0 * LAMBDA_C)


def test_compton_energy_conservation():
    e = 250e3
    angle = 1.1
    scattered = compton_scattered_energy_ev(e, angle)
    recoil = compton_recoil_energy_ev(e, angle)
    assert scattered + recoil == pytest.approx(e, rel=1e-14)
    assert 0.0 < scattered < e


def test_low_energy_compton_limit():
    e = 100.0
    scattered = compton_scattered_energy_ev(e, np.pi / 2)
    first_order = e * (1.0 - e / M_E_C2_EV)
    assert scattered == pytest.approx(first_order, rel=1e-7)


def test_recoil_angle_range():
    phi = recoil_electron_angle_rad(100e3, np.pi / 2)
    assert 0.0 < phi < np.pi / 2


def test_compton_edge_matches_backscatter_transfer():
    e = 662e3
    assert compton_edge_ev(e) == pytest.approx(compton_recoil_energy_ev(e, np.pi))


def test_infer_electron_mass_from_exact_shifts():
    angles = np.deg2rad(np.array([30, 60, 90, 120, 150], dtype=float))
    shifts = compton_shift(angles)
    cov = np.eye(angles.size) * (0.002e-12) ** 2
    mass, sigma = infer_scatterer_mass(angles, shifts, cov)
    assert mass == pytest.approx(M_E, rel=1e-12)
    assert sigma > 0.0


def test_polynomial_calibration_round_trip():
    ch = np.array([0.0, 100.0, 300.0, 700.0])
    energies = 5.0 + 0.8 * ch + 1e-4 * ch**2
    coeff = polynomial_energy_calibration(ch, energies, degree=2)
    assert np.allclose(evaluate_calibration(ch, coeff), energies, rtol=1e-12, atol=1e-10)


def test_gaussian_response_area():
    grid = np.linspace(0.0, 10.0, 10000)
    response = gaussian_response(grid, 4.2, 0.3, area=2.5)
    assert np.trapezoid(response, grid) == pytest.approx(2.5, rel=1e-12)


def test_synthetic_spectrum_positive():
    grid = np.linspace(0.0, 1000.0, 5000)
    y = synthetic_compton_spectrum(grid, 420.0, 662.0, 12.0)
    assert np.all(np.isfinite(y)) and np.all(y > 0.0)


def test_chi_square_zero_for_exact_model():
    y = np.array([1.0, 2.0, 3.0])
    assert chi_square(y, y, np.eye(3)) == pytest.approx(0.0)


def test_finite_difference_jacobian():
    fun = lambda x: np.array([x[0] ** 2 + 3.0 * x[1]])
    jac = finite_difference_jacobian(fun, np.array([2.0, 4.0]), 1e-5)
    assert jac[0, 0] == pytest.approx(4.0, rel=1e-9)
    assert jac[0, 1] == pytest.approx(3.0, rel=1e-9)


def test_covariance_propagation_linear_map():
    matrix = np.array([[2.0, -1.0], [0.5, 3.0]])
    fun = lambda x: matrix @ x
    cov = np.array([[0.04, 0.01], [0.01, 0.09]])
    out = propagate_covariance(fun, np.array([1.0, 2.0]), cov, 1e-5)
    assert np.allclose(out, matrix @ cov @ matrix.T, rtol=1e-9, atol=1e-12)


def test_invalid_inputs_raise():
    with pytest.raises(ValueError):
        threshold_frequency(-1.0)
    with pytest.raises(ValueError):
        compton_shift(-0.1)
    with pytest.raises(ValueError):
        gaussian_response(np.array([1.0, 0.0]), 0.5, 0.1)
