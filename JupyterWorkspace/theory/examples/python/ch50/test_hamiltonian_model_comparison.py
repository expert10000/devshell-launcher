import numpy as np
import pytest

from hamiltonian_model_comparison import (
    anharmonic_convergence,
    anharmonic_oscillator_hamiltonian,
    anharmonic_spectrum,
    effective_error_sweep,
    effective_model_error,
    effective_two_level_hamiltonian,
    flux_ring_energies,
    flux_ring_ground_state_current,
    flux_ring_ground_state_energy,
    hermitian_eigensystem,
    ladder_operators,
    three_level_hamiltonian,
    two_level_energies,
    two_level_ground_character,
    two_level_hamiltonian,
)


def test_two_level_matrix_is_hermitian():
    h = two_level_hamiltonian(0.7, 0.3)
    assert np.allclose(h, h.T)


def test_two_level_exact_gap_at_resonance():
    e = two_level_energies(0.0, 0.8)
    assert np.isclose(e[1] - e[0], 0.8)


def test_two_level_matrix_matches_analytic_eigenvalues():
    for detuning in (-3.0, -0.2, 0.0, 1.7):
        values, _ = hermitian_eigensystem(two_level_hamiltonian(detuning, 0.6))
        assert np.allclose(values, two_level_energies(detuning, 0.6))


def test_two_level_character_reverses_across_resonance():
    left = two_level_ground_character(-20.0, 1.0)
    right = two_level_ground_character(20.0, 1.0)
    assert left > 0.99
    assert right < -0.99


def test_two_level_uncoupled_zero_is_undefined_character():
    with pytest.raises(ValueError):
        two_level_ground_character(0.0, 0.0)


def test_hermitian_solver_rejects_nonhermitian_input():
    with pytest.raises(ValueError):
        hermitian_eigensystem(np.array([[0.0, 1.0], [0.0, 0.0]]))


def test_ladder_operator_commutator_is_correct_away_from_truncation_edge():
    a, adag = ladder_operators(12)
    comm = a @ adag - adag @ a
    assert np.allclose(np.diag(comm)[:-1], 1.0)


def test_anharmonic_zero_strength_recovers_oscillator_levels():
    values = anharmonic_spectrum(20, 0.0, 5)
    assert np.allclose(values, np.arange(5) + 0.5, atol=1e-12)


def test_positive_quartic_term_raises_ground_energy():
    e0 = anharmonic_spectrum(32, 0.0, 1)[0]
    e1 = anharmonic_spectrum(32, 0.1, 1)[0]
    assert e1 > e0


def test_anharmonic_hamiltonian_is_symmetric():
    h = anharmonic_oscillator_hamiltonian(18, 0.07)
    assert np.allclose(h, h.T)


def test_anharmonic_basis_convergence_improves():
    dims, errors = anharmonic_convergence([8, 12, 16, 24, 32], 0.1, levels=4)
    assert dims[-1] == 32
    assert errors[-1] < errors[0]
    assert errors[-1] < 1e-7


def test_flux_ring_spectrum_is_periodic_as_a_set():
    n = np.arange(-6, 7)
    e0 = np.sort(flux_ring_energies(0.23, n))[:8]
    e1 = np.sort(flux_ring_energies(1.23, n))[:8]
    assert np.allclose(e0, e1)


def test_flux_ring_ground_state_energy_is_flux_periodic():
    phi = np.linspace(-0.4, 0.4, 31)
    assert np.allclose(
        flux_ring_ground_state_energy(phi),
        flux_ring_ground_state_energy(phi + 1.0),
    )


def test_flux_ring_ground_current_is_zero_at_integer_flux():
    assert np.isclose(flux_ring_ground_state_current(0.0), 0.0)
    assert np.isclose(flux_ring_ground_state_current(1.0), 0.0)


def test_three_level_and_effective_models_are_hermitian():
    assert np.allclose(three_level_hamiltonian(10.0), three_level_hamiltonian(10.0).T)
    assert np.allclose(
        effective_two_level_hamiltonian(10.0),
        effective_two_level_hamiltonian(10.0).T,
    )


def test_effective_model_improves_with_gap():
    assert effective_model_error(30.0) < effective_model_error(5.0)


def test_effective_model_has_second_order_asymptotic_error():
    gaps, errors = effective_error_sweep(np.geomspace(10.0, 80.0, 12))
    slope = np.polyfit(np.log(gaps), np.log(errors), 1)[0]
    assert -2.2 < slope < -1.8


def test_invalid_model_parameters_are_rejected():
    with pytest.raises(ValueError):
        anharmonic_oscillator_hamiltonian(8, -0.1)
    with pytest.raises(ValueError):
        three_level_hamiltonian(0.0)
