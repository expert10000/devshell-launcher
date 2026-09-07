import numpy as np

from maxwell_induction_companion import (
    C0,
    EPS0,
    MU0,
    capacitor_currents,
    charge_relaxation,
    charge_relaxation_time,
    conduction_displacement_ratio,
    continuity_residual,
    coupled_inductance_eigenvalues,
    diffusion_convergence,
    effective_complex_permittivity,
    faraday_emf,
    identical_coupled_mode_frequencies,
    lc_energy,
    lc_state,
    magnetic_diffusion_time,
    magnetic_diffusivity,
    retardation_parameter,
    rl_current,
    sampled_vacuum_maxwell_residual,
    skin_depth,
)


def test_01_retardation_parameter_is_dimensionless():
    assert np.isclose(retardation_parameter(C0, 1.0), 1.0)


def test_02_conduction_displacement_crossover():
    omega = 100.0
    sigma = omega * 4.0 * EPS0
    assert np.isclose(conduction_displacement_ratio(sigma, omega, 4.0 * EPS0), 1.0)


def test_03_charge_relaxation_e_fold():
    tau = charge_relaxation_time(3.0, 6.0)
    assert np.isclose(charge_relaxation(tau, 2.0, 3.0, 6.0), 2.0 / np.e)


def test_04_magnetic_diffusivity_and_time_are_reciprocal_scales():
    mu, sigma, length = 2.0, 5.0, 0.4
    assert np.isclose(magnetic_diffusivity(mu, sigma) * magnetic_diffusion_time(mu, sigma, length), length**2)


def test_05_skin_depth_scaling():
    d1 = skin_depth(MU0, 1e6, 100.0)
    d2 = skin_depth(MU0, 1e6, 400.0)
    assert np.isclose(d2 / d1, 0.5)


def test_06_effective_permittivity_sign_convention():
    value = effective_complex_permittivity(2.0, 3.0, 4.0)
    assert np.isclose(value.real, 2.0) and np.isclose(value.imag, 0.75)


def test_07_rl_exact_initial_and_final_values():
    t = np.array([0.0, 100.0])
    current = rl_current(t, voltage=10.0, resistance=2.0, inductance=1.0)
    assert np.isclose(current[0], 0.0)
    assert np.isclose(current[-1], 5.0, atol=1e-10)


def test_08_lc_energy_is_conserved():
    t = np.linspace(0.0, 20.0, 2000)
    q, i = lc_state(t, capacitance=2.0, inductance=3.0, q0=4.0)
    energy = lc_energy(q, i, 2.0, 3.0)
    assert np.ptp(energy) < 1e-11


def test_09_inductance_matrix_positivity():
    eig = coupled_inductance_eigenvalues(2.0, 3.0, 1.0)
    assert np.all(eig > 0)
    assert coupled_inductance_eigenvalues(1.0, 1.0, 1.1)[0] < 0


def test_10_coupled_mode_zero_coupling_degeneracy():
    ws, wa = identical_coupled_mode_frequencies(2.0, 3.0, 0.0)
    assert np.isclose(ws, wa)


def test_11_capacitor_current_crossover():
    area, spacing, epsilon, omega = 2.0, 0.5, 4.0, 3.0
    sigma = omega * epsilon
    voltage = 5.0
    jc, jd = capacitor_currents(area, spacing, epsilon, sigma, voltage, omega * voltage)
    assert np.isclose(jc, jd)


def test_12_faraday_emf_of_sinusoidal_flux():
    t = np.linspace(0.0, 2.0 * np.pi, 2001)
    emf = faraday_emf(t, np.sin(t))
    assert np.max(np.abs(emf[2:-2] + np.cos(t[2:-2]))) < 5e-5


def test_13_continuity_residual_vanishes():
    x = np.linspace(0.0, 1.0, 50)
    drho = np.sin(x)
    assert np.max(np.abs(continuity_residual(drho, -drho))) == 0.0


def test_14_diffusion_and_maxwell_residuals_converge():
    _, errors, slope = diffusion_convergence([41, 81, 161], final_time=0.03)
    assert np.all(np.diff(errors) < 0) and slope > 1.8
    coarse = sampled_vacuum_maxwell_residual(51)
    fine = sampled_vacuum_maxwell_residual(201)
    assert fine.faraday_rms < coarse.faraday_rms / 8.0
    assert fine.ampere_rms < coarse.ampere_rms / 8.0
