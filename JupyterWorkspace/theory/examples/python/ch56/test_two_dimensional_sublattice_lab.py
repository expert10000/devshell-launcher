import numpy as np
import pytest

from two_dimensional_sublattice_lab import (
    berry_phase_from_winding,
    edge_weight,
    fermi_velocity,
    graphene_band_gap,
    graphene_bands,
    graphene_bloch_hamiltonian,
    graphene_d_vector,
    graphene_structure_factor,
    honeycomb_geometry,
    intrinsic_soc_dirac_gap,
    lattice_dirac_spectrum_error,
    pauli_matrices,
    pseudospin_direction,
    pseudospin_winding,
    reciprocal_dot_matrix,
    ribbon_edge_state_summary,
    ribbon_near_zero_states,
    spinful_dirac_hamiltonian,
    spinful_time_reversal_error,
    time_reversal_matrix_spin,
    zigzag_ribbon_hamiltonian,
    zigzag_ribbon_spectrum,
)


def test_honeycomb_has_three_nearest_neighbor_vectors():
    assert honeycomb_geometry().delta.shape == (3, 2)


def test_honeycomb_nearest_neighbor_lengths_are_equal():
    g = honeycomb_geometry(1.7)
    assert np.allclose(np.linalg.norm(g.delta, axis=1), 1.7, atol=1e-12)


def test_honeycomb_primitive_cell_area_reference():
    g = honeycomb_geometry()
    area = abs(np.linalg.det(np.column_stack([g.a1, g.a2])))
    assert area == pytest.approx(3.0 * np.sqrt(3.0) / 2.0)


def test_reciprocal_vectors_satisfy_duality():
    assert np.allclose(reciprocal_dot_matrix(), 2.0 * np.pi * np.eye(2), atol=2e-12)


def test_honeycomb_rejects_nonpositive_bond_length():
    with pytest.raises(ValueError):
        honeycomb_geometry(0.0)


def test_graphene_structure_factor_gamma_equals_three():
    assert graphene_structure_factor(0.0, 0.0) == pytest.approx(3.0 + 0.0j)


def test_graphene_structure_factor_vanishes_at_K():
    g = honeycomb_geometry()
    assert abs(graphene_structure_factor(*g.k)) < 1e-12


def test_graphene_structure_factor_vanishes_at_Kprime():
    g = honeycomb_geometry()
    assert abs(graphene_structure_factor(*g.kp)) < 1e-12


def test_graphene_structure_factor_has_unit_modulus_at_M():
    g = honeycomb_geometry()
    assert abs(graphene_structure_factor(*g.m)) == pytest.approx(1.0, abs=1e-12)


def test_graphene_hamiltonian_is_hermitian():
    h = graphene_bloch_hamiltonian(0.47, -0.28, t=1.2, delta=0.13)
    assert np.allclose(h, h.conjugate().T, atol=1e-12)


def test_graphene_gamma_band_energies_are_plus_minus_3t():
    assert np.allclose(graphene_bands(0.0, 0.0, t=1.3), [-3.9, 3.9], atol=1e-12)


def test_graphene_M_band_energies_are_plus_minus_t():
    g = honeycomb_geometry()
    assert np.allclose(graphene_bands(*g.m, t=1.3), [-1.3, 1.3], atol=1e-12)


def test_graphene_massless_bands_touch_at_K():
    g = honeycomb_geometry()
    assert np.max(np.abs(graphene_bands(*g.k))) < 1e-12


def test_graphene_staggered_mass_opens_gap_two_delta():
    g = honeycomb_geometry()
    assert np.allclose(graphene_bands(*g.k, delta=0.2), [-0.2, 0.2], atol=1e-12)
    assert graphene_band_gap(0.2) == pytest.approx(0.4)


def test_graphene_d_vector_reconstructs_band_radius():
    kx, ky = 0.31, 0.27
    d = graphene_d_vector(kx, ky, t=0.9, delta=0.17)
    e = graphene_bands(kx, ky, t=0.9, delta=0.17)
    assert np.linalg.norm(d) == pytest.approx(e[1], abs=1e-12)


def test_pseudospin_direction_is_unit_vector():
    n = pseudospin_direction(0.37, 0.22, t=1.0, delta=0.1)
    assert np.linalg.norm(n) == pytest.approx(1.0, abs=1e-12)


def test_pseudospin_is_undefined_exactly_at_massless_dirac_point():
    g = honeycomb_geometry()
    with pytest.raises(ValueError):
        pseudospin_direction(*g.k)


def test_fermi_velocity_reference_is_three_halves():
    assert fermi_velocity(t=1.0, a_nn=1.0, hbar=1.0) == pytest.approx(1.5)


def test_fermi_velocity_scales_with_t_and_bond_length():
    assert fermi_velocity(t=2.0, a_nn=0.5, hbar=1.0) == pytest.approx(1.5)


def test_dirac_linearization_error_decreases_quadratically_with_radius():
    e1 = lattice_dirac_spectrum_error(0.05)
    e2 = lattice_dirac_spectrum_error(0.025)
    assert e2 < 0.30 * e1


def test_dirac_linearization_reference_error_at_radius_point_zero_five():
    assert lattice_dirac_spectrum_error(0.05) == pytest.approx(0.000960788827613, rel=2e-10)


def test_pseudospin_winding_at_K_is_plus_one():
    g = honeycomb_geometry()
    assert pseudospin_winding(g.k, 0.05) == pytest.approx(1.0, abs=2e-10)


def test_pseudospin_winding_at_Kprime_is_minus_one():
    g = honeycomb_geometry()
    assert pseudospin_winding(g.kp, 0.05) == pytest.approx(-1.0, abs=2e-10)


def test_berry_phase_from_unit_winding_is_pi():
    assert berry_phase_from_winding(1.0) == pytest.approx(np.pi)


def test_zigzag_ribbon_dimension_is_two_times_width():
    assert zigzag_ribbon_hamiltonian(0.4, 11).shape == (22, 22)


def test_zigzag_ribbon_hamiltonian_is_hermitian():
    h = zigzag_ribbon_hamiltonian(1.9, 12, t=1.2, delta=0.07)
    assert np.allclose(h, h.conjugate().T, atol=1e-12)


def test_zigzag_ribbon_rejects_width_one():
    with pytest.raises(ValueError):
        zigzag_ribbon_hamiltonian(0.0, 1)


def test_zigzag_ribbon_spectrum_has_expected_shape():
    q = np.linspace(-np.pi, np.pi, 17)
    assert zigzag_ribbon_spectrum(q, 8).shape == (17, 16)


def test_zigzag_ribbon_has_exact_zero_edge_states_at_zone_edge():
    e, _ = ribbon_near_zero_states(np.pi, 16)
    assert np.max(np.abs(e)) < 1e-12


def test_zigzag_zone_edge_states_are_fully_edge_localized():
    summary = ribbon_edge_state_summary(np.pi, 16)
    assert summary["min_edge_weight"] == pytest.approx(1.0, abs=1e-12)


def test_zigzag_reference_edge_mode_is_exponentially_near_zero():
    summary = ribbon_edge_state_summary(0.9 * np.pi, 20)
    assert summary["max_abs_energy"] == pytest.approx(7.28634599222e-11, rel=2e-8)
    assert summary["min_edge_weight"] > 0.90


def test_zigzag_gamma_near_zero_states_are_not_edge_localized():
    summary = ribbon_edge_state_summary(0.0, 20)
    assert summary["max_abs_energy"] > 1.0
    assert summary["mean_edge_weight"] < 0.02


def test_edge_weight_is_normalization_independent():
    v = np.zeros(12, dtype=complex)
    v[0] = 2.0
    assert edge_weight(v, width=6) == pytest.approx(1.0)


def test_spinful_dirac_hamiltonian_is_four_by_four_and_hermitian():
    h = spinful_dirac_hamiltonian(0.1, -0.04, +1, lambda_so=0.2, lambda_r=0.03)
    assert h.shape == (4, 4)
    assert np.allclose(h, h.conjugate().T, atol=1e-12)


def test_intrinsic_soc_reference_gap_is_twice_lambda_so():
    assert intrinsic_soc_dirac_gap(0.2, delta=0.0) == pytest.approx(0.4)


def test_spinful_dirac_time_reversal_maps_valleys_exactly():
    assert spinful_time_reversal_error(0.07, -0.03, lambda_so=0.2, lambda_r=0.05) < 1e-12
