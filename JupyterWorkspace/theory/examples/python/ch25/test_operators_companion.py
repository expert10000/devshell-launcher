import numpy as np
import pytest

from operators_companion import (
    anticommutator, bloch_density, bloch_vector, commutator, dephase,
    density_expectation, density_from_ensemble, density_from_pure, expectation,
    is_hermitian, nearest_physical_qubit, partial_trace, pauli_matrices,
    project_state, projective_probabilities, projectors_from_operator, purity,
    robertson_bound, schrodinger_bound_squared, sequential_probability,
    spectral_decomposition, validate_density, variance, von_neumann_entropy,
)

sx, sy, sz = pauli_matrices()
plus_z = np.array([1, 0], complex)
minus_z = np.array([0, 1], complex)
plus_x = np.array([1, 1], complex) / np.sqrt(2)
PZ = np.outer(plus_z, plus_z.conj())
PX = np.outer(plus_x, plus_x.conj())


def test_pauli_are_hermitian():
    assert all(is_hermitian(s) for s in (sx, sy, sz))


def test_commutator_pauli():
    assert np.allclose(commutator(sx, sy), 2j * sz)


def test_anticommutator_distinct_pauli_zero():
    assert np.allclose(anticommutator(sx, sy), 0)


def test_expectation_pauli_z():
    assert expectation(plus_z, sz) == pytest.approx(1)


def test_variance_eigenstate_zero():
    assert variance(plus_z, sz) == pytest.approx(0)


def test_variance_plus_x_for_z():
    assert variance(plus_x, sz) == pytest.approx(1)


def test_robertson_bound_saturated_for_z_state():
    assert robertson_bound(plus_z, sx, sy) == pytest.approx(1)
    assert np.sqrt(variance(plus_z, sx) * variance(plus_z, sy)) == pytest.approx(1)


def test_schrodinger_bound_nonnegative():
    assert schrodinger_bound_squared(plus_x, sy, sz) >= 0


def test_spectral_decomposition_reconstructs():
    a = np.array([[2, 1j], [-1j, 3]], complex)
    spec = spectral_decomposition(a)
    rebuilt = spec.vectors @ np.diag(spec.values) @ spec.vectors.conj().T
    assert np.allclose(rebuilt, a)


def test_nonhermitian_spectrum_rejected():
    with pytest.raises(ValueError):
        spectral_decomposition(np.array([[0, 1], [0, 0]], complex))


def test_degenerate_projector_grouping():
    a = np.diag([1, 1, 2])
    values, projectors = projectors_from_operator(a)
    assert np.allclose(values, [1, 2])
    assert np.trace(projectors[0]) == pytest.approx(2)


def test_projective_probabilities_sum():
    probs = projective_probabilities(plus_x, [PZ, np.eye(2) - PZ])
    assert probs.sum() == pytest.approx(1)


def test_project_state_probability_and_normalization():
    p, state = project_state(plus_x, PZ)
    assert p == pytest.approx(0.5)
    assert np.vdot(state, state).real == pytest.approx(1)


def test_zero_probability_projection_rejected():
    with pytest.raises(ValueError):
        project_state(minus_z, PZ)


def test_sequential_order_effect():
    assert sequential_probability(plus_z, PZ, PX) == pytest.approx(0.5)
    assert sequential_probability(plus_z, PX, PZ) == pytest.approx(0.25)


def test_pure_density_valid_and_pure():
    rho = density_from_pure(plus_x)
    assert validate_density(rho)
    assert purity(rho) == pytest.approx(1)


def test_equal_z_mixture_is_maximally_mixed():
    rho = density_from_ensemble([plus_z, minus_z], [0.5, 0.5])
    assert np.allclose(rho, np.eye(2) / 2)
    assert purity(rho) == pytest.approx(0.5)


def test_invalid_weights_rejected():
    with pytest.raises(ValueError):
        density_from_ensemble([plus_z, minus_z], [0.3, 0.3])


def test_density_expectation_matches_pure_rule():
    rho = density_from_pure(plus_x)
    assert density_expectation(rho, sx) == pytest.approx(expectation(plus_x, sx))


def test_entropy_pure_zero():
    assert von_neumann_entropy(density_from_pure(plus_x)) == pytest.approx(0)


def test_entropy_maximally_mixed_one_bit():
    assert von_neumann_entropy(np.eye(2) / 2) == pytest.approx(1)


def test_bloch_round_trip():
    vector = np.array([0.2, -0.3, 0.4])
    assert np.allclose(bloch_vector(bloch_density(vector)), vector)


def test_invalid_bloch_vector_rejected():
    with pytest.raises(ValueError):
        bloch_density([1, 1, 0])


def test_nearest_physical_qubit_projects_to_ball():
    rho = nearest_physical_qubit([0.8, 0.8, 0.2])
    assert validate_density(rho)
    assert np.linalg.norm(bloch_vector(rho)) == pytest.approx(1)


def test_dephase_preserves_diagonal_and_trace():
    rho = density_from_pure(plus_x)
    out = dephase(rho, 0.25)
    assert np.allclose(np.diag(out), np.diag(rho))
    assert np.trace(out) == pytest.approx(1)
    assert out[0, 1] == pytest.approx(0.25 * rho[0, 1])


def test_dephase_reduces_purity():
    rho = density_from_pure(plus_x)
    assert purity(dephase(rho, 0.2)) < purity(rho)


def test_partial_trace_bell_pair():
    bell = np.array([1, 0, 0, 1], complex) / np.sqrt(2)
    rho = density_from_pure(bell)
    assert np.allclose(partial_trace(rho, (2, 2), 0), np.eye(2) / 2)
    assert np.allclose(partial_trace(rho, (2, 2), 1), np.eye(2) / 2)


def test_partial_trace_product_state():
    product = np.kron(plus_x, minus_z)
    reduced = partial_trace(density_from_pure(product), (2, 2), 1)
    assert np.allclose(reduced, density_from_pure(plus_x))


def test_invalid_density_detected():
    assert not validate_density(np.array([[1.2, 0], [0, -0.2]], complex))


def test_dimension_mismatch_rejected():
    with pytest.raises(ValueError):
        expectation(np.ones(3), sx)
