import numpy as np
import pytest

from bound_engineered_systems import (
    finite_well_state_count,
    finite_well_dimensionless_roots,
    finite_well_energy_ratios,
    rectangular_barrier_transmission,
    wkb_rectangular_transmission,
    propagation_matrix,
    multilayer_transfer_matrix,
    multilayer_transmission,
    finite_difference_hamiltonian,
    finite_difference_spectrum,
    symmetric_square_well_potential,
    density_of_states_shape,
    variable_mass_hamiltonian,
    variable_mass_eigensystem,
    exterior_probability,
    symmetric_double_well_potential,
    double_well_splitting,
)


def test_finite_well_always_has_ground_state():
    assert finite_well_state_count(0.2) == 1


def test_finite_well_threshold_counting():
    assert finite_well_state_count(np.pi / 2) == 1
    assert finite_well_state_count(np.pi / 2 + 1e-6) == 2


def test_finite_well_three_state_regime():
    assert finite_well_state_count(3.3) == 3


def test_finite_well_roots_in_physical_interval():
    z0 = 2.4
    roots = finite_well_dimensionless_roots(z0)
    assert len(roots) == 2
    assert np.all((roots > 0) & (roots < z0))
    assert np.all(np.diff(roots) > 0)


def test_finite_well_energy_ratios_are_bound():
    e = finite_well_energy_ratios(4.0)
    assert np.all(e > -1.0)
    assert np.all(e < 0.0)
    assert np.all(np.diff(e) > 0.0)


def test_zero_width_barrier_is_transparent():
    E = np.array([0.2, 0.8, 1.2])
    T = rectangular_barrier_transmission(E, 1.0, 0.0)
    assert np.allclose(T, 1.0)


def test_barrier_transmission_bounded():
    E = np.linspace(0.05, 1.8, 100)
    T = rectangular_barrier_transmission(E, 1.0, 1.3)
    assert np.all(T >= 0.0)
    assert np.all(T <= 1.0 + 1e-12)


def test_barrier_thicker_means_less_subbarrier_transmission():
    t1 = rectangular_barrier_transmission(0.35, 1.0, 0.8)
    t2 = rectangular_barrier_transmission(0.35, 1.0, 1.6)
    assert float(t2) < float(t1)


def test_wkb_captures_opaque_exponential_order():
    exact = float(rectangular_barrier_transmission(0.2, 1.0, 3.0))
    wkb = float(wkb_rectangular_transmission(0.2, 1.0, 3.0))
    ratio = exact / wkb
    assert 0.1 < ratio < 20.0


def test_propagation_matrix_unit_determinant():
    for V in (0.0, 0.4, 1.5):
        P = propagation_matrix(0.8, V, 0.7)
        assert np.allclose(np.linalg.det(P), 1.0, atol=1e-12)


def test_multilayer_matrix_unit_determinant():
    M = multilayer_transfer_matrix(0.7, [(1.1, 0.4), (0.0, 1.2), (1.1, 0.4)])
    assert np.allclose(np.linalg.det(M), 1.0, atol=1e-11)


def test_transfer_matrix_matches_single_barrier_formula():
    E, V0, width = 0.43, 1.0, 1.1
    exact = float(rectangular_barrier_transmission(E, V0, width))
    transfer = multilayer_transmission(E, [(V0, width)])
    assert np.isclose(transfer, exact, rtol=1e-10, atol=1e-12)


def test_symmetric_double_barrier_has_high_transmission_resonance():
    energies = np.linspace(0.08, 0.95, 1200)
    T = np.array([multilayer_transmission(float(e), [(1.0, 0.55), (0.0, 2.0), (1.0, 0.55)]) for e in energies])
    assert T.max() > 0.9


def test_fd_hamiltonian_is_symmetric():
    x = np.linspace(-4, 4, 81)
    v = symmetric_square_well_potential(x, 1.0, 1.0)
    H = finite_difference_hamiltonian(x, v)
    assert np.allclose(H, H.T)


def test_fd_box_ground_state_approaches_pi_squared_over_8a_squared():
    # Infinite box on [-a,a] via Dirichlet numerical endpoints; hbar=m=1.
    a = 2.0
    x = np.linspace(-a, a, 181)
    v = np.zeros_like(x)
    e0 = finite_difference_spectrum(x, v, levels=1)[0]
    reference = np.pi ** 2 / (8.0 * a * a)
    assert np.isclose(e0, reference, rtol=2e-4)


def test_fd_finite_well_negative_state_count_agrees_with_root_count():
    depth, a = 1.0, 2.4  # z0=a*sqrt(2V0) in hbar=m=1 units
    z0 = a * np.sqrt(2.0 * depth)
    x = np.linspace(-10, 10, 321)
    v = symmetric_square_well_potential(x, depth, a)
    vals = finite_difference_spectrum(x, v, levels=8)
    assert int(np.count_nonzero(vals < 0.0)) == finite_well_state_count(z0)


def test_invalid_grid_rejected():
    x = np.array([0.0, 0.2, 0.5, 1.0])
    with pytest.raises(ValueError):
        finite_difference_hamiltonian(x, np.zeros_like(x))


def test_invalid_barrier_energy_rejected():
    with pytest.raises(ValueError):
        rectangular_barrier_transmission(-0.1, 1.0, 1.0)



def test_dos_2d_is_constant_above_edge():
    e = np.array([0.2, 0.4, 0.8])
    assert np.allclose(density_of_states_shape(e, 0.1, 2), 1.0)


def test_dos_3d_grows_with_sqrt_energy():
    vals = density_of_states_shape(np.array([0.2, 0.5, 1.0]), 0.1, 3)
    assert np.all(np.diff(vals) > 0)


def test_dos_1d_decreases_away_from_edge():
    vals = density_of_states_shape(np.array([0.11, 0.2, 0.8]), 0.1, 1)
    assert np.all(np.diff(vals) < 0)


def test_variable_mass_reduces_to_constant_mass_matrix():
    x = np.linspace(-3, 3, 91)
    v = np.zeros_like(x)
    m = np.full_like(x, 1.7)
    hv = variable_mass_hamiltonian(x, v, m)
    hc = finite_difference_hamiltonian(x, v, mass=1.7)
    assert np.allclose(hv, hc, atol=1e-12)


def test_variable_mass_hamiltonian_is_symmetric():
    x = np.linspace(-4, 4, 101)
    v = symmetric_square_well_potential(x, 1.0, 1.0)
    m = np.where(np.abs(x) < 1.0, 1.0, 2.0)
    H = variable_mass_hamiltonian(x, v, m)
    assert np.allclose(H, H.T)


def test_heavier_barrier_reduces_ground_state_leakage():
    x = np.linspace(-7, 7, 241)
    v = symmetric_square_well_potential(x, 1.0, 1.2)
    m1 = np.ones_like(x)
    m2 = np.where(np.abs(x) < 1.2, 1.0, 3.0)
    _, vec1 = variable_mass_eigensystem(x, v, m1, levels=1)
    _, vec2 = variable_mass_eigensystem(x, v, m2, levels=1)
    assert exterior_probability(x, vec2[:,0], 1.2) < exterior_probability(x, vec1[:,0], 1.2)


def test_double_well_splitting_decreases_with_higher_central_barrier():
    x = np.linspace(-6, 6, 241)
    v0 = symmetric_double_well_potential(x, central_barrier=0.0)
    v1 = symmetric_double_well_potential(x, central_barrier=1.5)
    assert double_well_splitting(x, v1) < double_well_splitting(x, v0)


def test_invalid_dimension_rejected():
    with pytest.raises(ValueError):
        density_of_states_shape(np.array([1.0]), 0.0, 4)

from bound_engineered_systems import (
    tilted_potential,
    position_expectation,
    two_level_energies,
    two_level_polarization,
    lorentzian_transmission,
    fermi_function,
    landauer_conductance_dimensionless,
    landauer_current_dimensionless,
    poisson_dirichlet_1d,
)


def test_tilted_potential_adds_linear_energy_gradient():
    x = np.linspace(-1, 1, 7)
    base = np.full_like(x, 0.4)
    assert np.allclose(tilted_potential(x, base, 0.3), base + 0.3*x)


def test_position_expectation_respects_symmetric_state():
    x = np.linspace(-2, 2, 101)
    xi = x[1:-1]
    psi = np.exp(-xi**2)
    assert abs(position_expectation(x, psi)) < 1e-14


def test_two_level_minimum_gap_is_two_t():
    t = 0.17
    vals = two_level_energies(0.0, t)
    assert np.isclose(vals[1] - vals[0], 2*t)


def test_two_level_polarization_is_odd_and_bounded():
    d = np.array([-3.0, -0.4, 0.4, 3.0])
    p = two_level_polarization(d, 0.2)
    assert np.all(np.abs(p) <= 1.0)
    assert np.allclose(p, -p[::-1])


def test_lorentzian_linewidth_is_fwhm():
    gamma = 0.24
    vals = lorentzian_transmission(np.array([-gamma/2, 0.0, gamma/2]), 0.0, gamma)
    assert np.allclose(vals, [0.5, 1.0, 0.5])


def test_zero_temperature_landauer_recovers_transmission_at_mu():
    e = np.linspace(-2, 2, 1001)
    T = lorentzian_transmission(e, 0.2, 0.4, peak=0.8)
    g = landauer_conductance_dimensionless(e, T, 0.2, 0.0, degeneracy=2)
    assert np.isclose(g, 1.6, rtol=1e-5)


def test_landauer_current_reverses_with_bias():
    e = np.linspace(-3, 3, 2001)
    T = lorentzian_transmission(e, 0.0, 0.5)
    i1 = landauer_current_dimensionless(e, T, 0.4, -0.4, 0.05)
    i2 = landauer_current_dimensionless(e, T, -0.4, 0.4, 0.05)
    assert i1 > 0 and np.isclose(i1, -i2, rtol=1e-12)


def test_poisson_uniform_charge_matches_parabola():
    x = np.linspace(-1, 1, 101)
    rho = np.full_like(x, 2.0)
    phi = poisson_dirichlet_1d(x, rho, permittivity=1.0)
    reference = 1.0 - x*x
    assert np.max(np.abs(phi-reference)) < 2e-12
