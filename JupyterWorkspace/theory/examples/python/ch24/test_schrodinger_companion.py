import numpy as np
import pytest

from schrodinger_companion import (
    E_CHARGE, HBAR, M_E, barrier_transmission, continuity_residual,
    finite_difference_hamiltonian, free_gaussian_wavefunction,
    harmonic_ground_state, harmonic_oscillator_energy, infinite_well_energy,
    infinite_well_state, normalize_wavefunction, potential_step_coefficients,
    probability_current, probability_density, probability_norm,
    solve_bound_states, split_step_propagate,
)


def uniform_grid(a=-1e-9, b=1e-9, n=1201):
    return np.linspace(a, b, n)


def test_normalization_of_arbitrary_state():
    x = uniform_grid()
    psi = np.exp(-(x / 0.25e-9) ** 2) * np.exp(1j * 3e10 * x)
    state = normalize_wavefunction(psi, x)
    assert probability_norm(state, x) == pytest.approx(1.0, rel=1e-12)


def test_zero_state_rejected():
    x = uniform_grid()
    with pytest.raises(ValueError):
        normalize_wavefunction(np.zeros_like(x), x)


def test_density_nonnegative():
    psi = np.array([1 + 2j, -3j])
    assert np.all(probability_density(psi) >= 0.0)


def test_plane_wave_current_sign_and_scale():
    x = uniform_grid(n=3001)
    k = 4e9
    psi = normalize_wavefunction(np.exp(1j * k * x), x)
    j = probability_current(psi, x, M_E)
    rho = probability_density(psi)
    expected = HBAR * k * rho / M_E
    assert np.median(j[10:-10] / expected[10:-10]) == pytest.approx(1.0, rel=2e-5)


def test_real_stationary_profile_has_zero_current():
    x = np.linspace(0.0, 2e-9, 2001)
    psi = infinite_well_state(2, x, 2e-9)
    assert np.max(np.abs(probability_current(psi, x, M_E))) < 1e-12


def test_infinite_well_energy_n_squared():
    e1 = infinite_well_energy(1, 1e-9)
    assert infinite_well_energy(3, 1e-9) == pytest.approx(9.0 * e1)


def test_infinite_well_state_normalized():
    x = np.linspace(0.0, 1e-9, 3001)
    psi = infinite_well_state(4, x, 1e-9)
    assert probability_norm(psi, x) == pytest.approx(1.0, rel=1e-12)


def test_infinite_well_orthogonality():
    x = np.linspace(0.0, 1e-9, 3001)
    p1 = infinite_well_state(1, x, 1e-9)
    p2 = infinite_well_state(2, x, 1e-9)
    assert np.trapezoid(np.conjugate(p1) * p2, x) == pytest.approx(0.0, abs=1e-12)


def test_free_gaussian_normalized_and_translated():
    x = np.linspace(-2e-6, 2e-6, 20001)
    p0 = M_E * 1e6
    t = 2e-13
    psi = free_gaussian_wavefunction(x, t, M_E, 20e-9, mean_momentum_kg_m_s=p0)
    rho = probability_density(psi)
    assert probability_norm(psi, x) == pytest.approx(1.0, rel=1e-10)
    assert np.trapezoid(x * rho, x) == pytest.approx(p0 * t / M_E, abs=2e-10)


def test_free_gaussian_spreads():
    x = np.linspace(-1e-6, 1e-6, 20001)
    p0 = free_gaussian_wavefunction(x, 0.0, M_E, 2e-9)
    p1 = free_gaussian_wavefunction(x, 5e-13, M_E, 2e-9)
    var0 = np.trapezoid(x**2 * probability_density(p0), x)
    var1 = np.trapezoid(x**2 * probability_density(p1), x)
    assert var1 > var0


def test_step_coefficients_conserve_flux():
    r, t = potential_step_coefficients(5.0, 2.0)
    assert r + t == pytest.approx(1.0)
    assert 0.0 < r < 1.0


def test_subthreshold_step_is_total_reflection():
    assert potential_step_coefficients(1.0, 2.0) == (1.0, 0.0)


def test_barrier_transmission_bounded():
    e = np.linspace(0.05, 2.0, 300) * E_CHARGE
    t = barrier_transmission(e, 1.0 * E_CHARGE, 0.7e-9)
    assert np.all((t >= 0.0) & (t <= 1.0))


def test_barrier_thicker_reduces_subthreshold_transmission():
    e = 0.3 * E_CHARGE
    thin = float(barrier_transmission(e, E_CHARGE, 0.3e-9))
    thick = float(barrier_transmission(e, E_CHARGE, 0.8e-9))
    assert thick < thin


def test_barrier_has_above_barrier_resonances():
    e = np.linspace(1.01, 5.0, 5000) * E_CHARGE
    t = barrier_transmission(e, E_CHARGE, 1e-9)
    assert np.max(t) > 0.999


def test_oscillator_energy_spacing():
    omega = 2e15
    assert harmonic_oscillator_energy(4, omega) - harmonic_oscillator_energy(3, omega) == pytest.approx(HBAR * omega)


def test_oscillator_ground_state_normalized():
    x = uniform_grid(-3e-9, 3e-9, 5001)
    psi = harmonic_ground_state(x, M_E, 2e15)
    assert probability_norm(psi, x) == pytest.approx(1.0, rel=1e-12)


def test_finite_difference_hamiltonian_is_symmetric():
    x = uniform_grid(n=101)
    h = finite_difference_hamiltonian(x, np.zeros_like(x))
    assert np.allclose(h, h.T)


def test_fd_infinite_box_energy_accuracy():
    width = 2e-9
    x = np.linspace(0.0, width, 401)
    sol = solve_bound_states(x, np.zeros_like(x), 3)
    exact = np.array([infinite_well_energy(n, width) for n in (1, 2, 3)])
    assert np.allclose(sol.energies_j, exact, rtol=2e-4)


def test_fd_states_are_normalized_and_orthogonal():
    x = np.linspace(-3e-9, 3e-9, 401)
    v = 0.5 * M_E * (2e15**2) * x**2
    sol = solve_bound_states(x, v, 3)
    overlap = np.trapezoid(np.conjugate(sol.states[0]) * sol.states[1], x)
    assert probability_norm(sol.states[2], x) == pytest.approx(1.0, rel=1e-12)
    assert overlap == pytest.approx(0.0, abs=1e-10)


def test_fd_oscillator_energies():
    omega = 2e15
    x = np.linspace(-1.2e-9, 1.2e-9, 501)
    v = 0.5 * M_E * omega**2 * x**2
    sol = solve_bound_states(x, v, 3)
    exact = np.array([harmonic_oscillator_energy(n, omega) for n in range(3)])
    assert np.allclose(sol.energies_j, exact, rtol=2e-3)


def test_split_step_zero_steps_returns_normalized_state():
    x = uniform_grid(n=1024)
    psi = np.exp(-(x / 0.2e-9) ** 2)
    out = split_step_propagate(psi, x, np.zeros_like(x), 1e-18, 0)
    assert probability_norm(out, x) == pytest.approx(1.0, rel=1e-12)


def test_split_step_preserves_norm():
    x = np.linspace(-2e-7, 2e-7, 4096)
    psi = free_gaussian_wavefunction(x, 0.0, M_E, 8e-9, mean_momentum_kg_m_s=M_E * 2e5)
    out = split_step_propagate(psi, x, np.zeros_like(x), 2e-16, 100)
    assert probability_norm(out, x) == pytest.approx(1.0, rel=2e-8)


def test_split_step_constant_potential_changes_only_phase():
    x = np.linspace(-2e-7, 2e-7, 2048)
    psi = free_gaussian_wavefunction(x, 0.0, M_E, 8e-9)
    zero = split_step_propagate(psi, x, np.zeros_like(x), 1e-16, 20)
    const = split_step_propagate(psi, x, np.full_like(x, 0.3 * E_CHARGE), 1e-16, 20)
    assert np.allclose(probability_density(zero), probability_density(const), rtol=1e-10, atol=1e-10)


def test_continuity_residual_small_for_short_free_step():
    x = np.linspace(-3e-7, 3e-7, 4096)
    dt = 1e-18
    psi0 = free_gaussian_wavefunction(x, 0.0, M_E, 20e-9, mean_momentum_kg_m_s=M_E * 1e5)
    psi1 = split_step_propagate(psi0, x, np.zeros_like(x), dt, 1)
    residual = continuity_residual(psi0, psi1, x, dt, M_E)
    scale = np.max(np.abs((probability_density(psi1) - probability_density(psi0)) / dt))
    assert np.sqrt(np.mean(residual[20:-20] ** 2)) / scale < 0.02


def test_invalid_inputs_raise():
    x = np.array([0.0, 1.0, 1.5])
    with pytest.raises(ValueError):
        probability_norm(np.ones(3), x)
    with pytest.raises(ValueError):
        infinite_well_energy(0, 1.0)
    with pytest.raises(ValueError):
        barrier_transmission(1.0, -1.0, 1.0)
