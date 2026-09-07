import numpy as np
import pytest

from wave_particle_companion import (
    C, E_CHARGE, H, HBAR, M_C60, M_E, M_N,
    bragg_angle_rad, coherence_length_from_sigma_lambda,
    de_broglie_wavelength_from_kinetic_energy,
    de_broglie_wavelength_from_momentum, de_broglie_wavelength_from_speed,
    diffraction_ring_radius_m, distinguishability_bound, double_slit_intensity,
    electron_wavelength_from_voltage, finite_grating_intensity, fourier_sigma_k,
    fringe_visibility, gaussian_packet_density, gaussian_packet_width_m,
    group_velocity_from_momentum, kinetic_energy_relativistic_j,
    marker_overlap_visibility, momentum_from_kinetic_energy_j,
    phase_velocity_relativistic, relativistic_gamma, relativistic_momentum,
    rms, sample_detection_events,
)


def test_de_broglie_momentum_identity():
    p = 2.5e-24
    assert de_broglie_wavelength_from_momentum(p) == pytest.approx(H / p)


def test_nonrelativistic_speed_formula():
    v = 2.0e6
    result = de_broglie_wavelength_from_speed(M_E, v, relativistic=False)
    assert result == pytest.approx(H / (M_E * v), rel=1e-14)


def test_relativistic_wavelength_is_shorter():
    v = 0.7 * C
    rel = de_broglie_wavelength_from_speed(M_E, v, relativistic=True)
    nonrel = de_broglie_wavelength_from_speed(M_E, v, relativistic=False)
    assert rel < nonrel


def test_relativistic_gamma_and_momentum():
    v = 0.6 * C
    assert relativistic_gamma(v) == pytest.approx(1.25)
    assert relativistic_momentum(M_E, v) == pytest.approx(1.25 * M_E * v)


def test_energy_momentum_round_trip():
    v = 0.4 * C
    k = kinetic_energy_relativistic_j(M_E, v)
    p = momentum_from_kinetic_energy_j(M_E, k)
    assert p == pytest.approx(relativistic_momentum(M_E, v), rel=1e-14)


def test_150_volt_electron_wavelength_scale():
    wavelength = electron_wavelength_from_voltage(150.0, relativistic=False)
    assert wavelength == pytest.approx(1.002e-10, rel=3e-3)


def test_relativistic_voltage_correction_small_at_150v():
    rel = electron_wavelength_from_voltage(150.0, relativistic=True)
    nonrel = electron_wavelength_from_voltage(150.0, relativistic=False)
    assert rel < nonrel
    assert rel / nonrel > 0.999


def test_phase_group_velocity_product():
    v = 0.35 * C
    p = relativistic_momentum(M_E, v)
    vg = group_velocity_from_momentum(M_E, p)
    vp = phase_velocity_relativistic(v)
    assert vg == pytest.approx(v, rel=1e-14)
    assert vp * vg == pytest.approx(C**2, rel=1e-14)


def test_fourier_minimum_uncertainty_product():
    sigma_x = 2.0e-9
    sigma_p = HBAR * fourier_sigma_k(sigma_x)
    assert sigma_x * sigma_p == pytest.approx(HBAR / 2.0)


def test_gaussian_width_initial_and_even_time():
    sigma0 = 1.0e-9
    assert gaussian_packet_width_m(sigma0, 0.0, M_E) == pytest.approx(sigma0)
    assert gaussian_packet_width_m(sigma0, 2e-14, M_E) == pytest.approx(
        gaussian_packet_width_m(sigma0, -2e-14, M_E)
    )


def test_gaussian_packet_density_normalized_and_translated():
    x = np.linspace(-2e-6, 2e-6, 200001)
    p0 = M_E * 2.0e6
    t = 2.0e-13
    rho = gaussian_packet_density(x, t, M_E, 2e-8, mean_momentum_kg_m_s=p0)
    mean = np.trapezoid(x * rho, x)
    assert np.trapezoid(rho, x) == pytest.approx(1.0, rel=1e-12)
    assert mean == pytest.approx(p0 * t / M_E, abs=2e-10)


def test_bragg_angle_and_missing_order():
    theta = bragg_angle_rad(0.1e-9, 0.2e-9, 1)
    assert np.sin(theta) == pytest.approx(0.25)
    with pytest.raises(ValueError):
        bragg_angle_rad(0.5e-9, 0.2e-9, 1)


def test_diffraction_ring_geometry():
    theta = 0.05
    radius = diffraction_ring_radius_m(0.2, theta)
    assert radius == pytest.approx(0.2 * np.tan(0.1))


def test_finite_grating_principal_maximum():
    x = np.array([0.0, np.pi])
    intensity = finite_grating_intensity(x, 12)
    assert np.allclose(intensity, 1.0)


def test_finite_grating_is_bounded():
    x = np.linspace(-np.pi, np.pi, 10001)
    intensity = finite_grating_intensity(x, 8)
    assert np.min(intensity) >= 0.0
    assert np.max(intensity) <= 1.0 + 1e-12


def test_double_slit_density_normalized_and_visibility_limit():
    x = np.linspace(-4e-3, 4e-3, 20001)
    coherent = double_slit_intensity(x, 100e-12, 1.0, 2e-6, visibility=1.0)
    incoherent = double_slit_intensity(x, 100e-12, 1.0, 2e-6, visibility=0.0)
    assert np.trapezoid(coherent, x) == pytest.approx(1.0, rel=1e-12)
    assert np.std(coherent) > np.std(incoherent)


def test_visibility_formula():
    assert fringe_visibility(9.0, 1.0) == pytest.approx(0.8)


def test_marker_overlap_and_duality_bound():
    visibility = marker_overlap_visibility(0.6j)
    assert visibility == pytest.approx(0.6)
    assert distinguishability_bound(visibility) == pytest.approx(0.8)


def test_coherence_length_inverse_bandwidth():
    one = coherence_length_from_sigma_lambda(100e-12, 1e-12)
    two = coherence_length_from_sigma_lambda(100e-12, 2e-12)
    assert one == pytest.approx(2.0 * two)


def test_event_sampling_reproducible_and_shaped():
    x = np.linspace(-1.0, 1.0, 101)
    density = np.exp(-x**2 / 0.1)
    a = sample_detection_events(x, density, 1000, seed=7)
    b = sample_detection_events(x, density, 1000, seed=7)
    assert np.array_equal(a, b)
    assert abs(np.mean(a)) < 0.05


def test_mass_scaling_for_equal_speed():
    v = 100.0
    lambda_n = de_broglie_wavelength_from_speed(M_N, v, relativistic=False)
    lambda_c60 = de_broglie_wavelength_from_speed(M_C60, v, relativistic=False)
    assert lambda_c60 < lambda_n


def test_kinetic_energy_interface_matches_voltage_interface():
    voltage = 10_000.0
    via_k = de_broglie_wavelength_from_kinetic_energy(M_E, E_CHARGE * voltage)
    via_v = electron_wavelength_from_voltage(voltage)
    assert via_k == pytest.approx(via_v, rel=1e-15)


def test_invalid_inputs_raise():
    with pytest.raises(ValueError):
        relativistic_gamma(C)
    with pytest.raises(ValueError):
        electron_wavelength_from_voltage(0.0)
    with pytest.raises(ValueError):
        marker_overlap_visibility(1.2)
    with pytest.raises(ValueError):
        rms([])
