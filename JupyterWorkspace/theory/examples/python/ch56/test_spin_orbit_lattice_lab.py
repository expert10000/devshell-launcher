import numpy as np
import pytest

from spin_orbit_lattice_lab import (
    adiabatic_rashba_gap_path,
    bulk_time_reversal_error,
    cell_structure_factor,
    critical_staggered_mass,
    edge_state_summary,
    intrinsic_bulk_gap,
    intrinsic_form_factor,
    kane_mele_bands,
    kane_mele_bloch_hamiltonian,
    kramers_pair_splitting,
    minimum_direct_gap,
    occupied_subspace_chern,
    pauli_spin,
    phase_from_masses,
    rashba_offdiagonal_cell,
    reference_summary,
    spin_block_berry_curvature,
    spin_block_hamiltonian,
    spin_chern_number,
    spin_chern_pair,
    spin_conservation_commutator_norm,
    spinful_edge_weight,
    spinful_ribbon_spectrum,
    spinful_ribbon_time_reversal_error,
    spinful_zigzag_ribbon_hamiltonian,
    spin_z_expectation,
    valley_mass_table,
    z2_spin_conserving,
)
from two_dimensional_sublattice_lab import honeycomb_geometry, zigzag_ribbon_hamiltonian


def test_pauli_spin_matrices_are_two_by_two():
    assert all(m.shape == (2, 2) for m in pauli_spin())


def test_pauli_spin_matrices_are_hermitian():
    sx, sy, sz, s0 = pauli_spin()
    assert all(np.allclose(m, m.conjugate().T) for m in (sx, sy, sz, s0))


def test_cell_structure_factor_vanishes_at_K():
    g = honeycomb_geometry()
    assert abs(cell_structure_factor(*g.k)) < 1e-12


def test_intrinsic_form_factor_at_K_is_three_sqrt_three():
    g = honeycomb_geometry()
    assert intrinsic_form_factor(*g.k) == pytest.approx(3.0 * np.sqrt(3.0), abs=1e-12)


def test_intrinsic_form_factor_changes_sign_at_Kprime():
    g = honeycomb_geometry()
    assert intrinsic_form_factor(*g.kp) == pytest.approx(-3.0 * np.sqrt(3.0), abs=1e-12)


def test_rashba_offdiagonal_is_two_by_two():
    assert rashba_offdiagonal_cell(0.3, -0.2, 0.04).shape == (2, 2)


def test_full_kane_mele_matrix_is_four_by_four():
    assert kane_mele_bloch_hamiltonian(0.2, 0.4).shape == (4, 4)


def test_full_kane_mele_matrix_is_hermitian_with_rashba():
    h = kane_mele_bloch_hamiltonian(0.2, 0.4, lambda_so=0.06, lambda_r=0.04, delta=0.11)
    assert np.allclose(h, h.conjugate().T, atol=1e-12)


def test_bulk_time_reversal_is_exact_without_rashba():
    assert bulk_time_reversal_error(0.31, -0.27, lambda_so=0.06, lambda_r=0.0) < 1e-12


def test_bulk_time_reversal_is_exact_with_rashba():
    assert bulk_time_reversal_error(0.31, -0.27, lambda_so=0.06, lambda_r=0.04) < 1e-12


def test_valley_mass_table_has_opposite_spin_masses_at_zero_delta():
    m = valley_mass_table(0.06, 0.0)
    assert m["K_up"] == pytest.approx(-m["K_down"])
    assert m["Kprime_up"] == pytest.approx(-m["Kprime_down"])


def test_valley_mass_table_swaps_between_valleys():
    m = valley_mass_table(0.06, 0.0)
    assert m["K_up"] == pytest.approx(m["Kprime_down"])
    assert m["K_down"] == pytest.approx(m["Kprime_up"])


def test_critical_staggered_mass_reference():
    assert critical_staggered_mass(0.06) == pytest.approx(0.3117691453623979, rel=1e-13)


def test_intrinsic_bulk_gap_reference():
    assert intrinsic_bulk_gap(0.06, 0.0) == pytest.approx(0.6235382907247958, rel=1e-13)


def test_intrinsic_bulk_gap_closes_at_mass_boundary():
    dc = critical_staggered_mass(0.06)
    assert intrinsic_bulk_gap(0.06, dc) < 1e-12


def test_K_spectrum_matches_intrinsic_mass_reference():
    g = honeycomb_geometry()
    e = kane_mele_bands(*g.k, lambda_so=0.06, lambda_r=0.0, delta=0.0)
    assert np.allclose(e, [-0.3117691453623979] * 2 + [0.3117691453623979] * 2, atol=1e-12)


def test_K_spectrum_with_rashba_reference():
    g = honeycomb_geometry()
    e = kane_mele_bands(*g.k, lambda_so=0.06, lambda_r=0.04, delta=0.0)
    assert np.allclose(e, [-0.4317691453623979, -0.1917691453623979, 0.3117691453623979, 0.3117691453623979], atol=1e-12)


def test_minimum_direct_gap_matches_intrinsic_reference_on_mesh_divisible_by_three():
    assert minimum_direct_gap(30, lambda_so=0.06, lambda_r=0.0, delta=0.0) == pytest.approx(0.6235382907247957, rel=1e-12)


def test_rashba_reference_gap_remains_open():
    assert minimum_direct_gap(30, lambda_so=0.06, lambda_r=0.04, delta=0.0) == pytest.approx(0.5035382907247955, rel=1e-12)


def test_spin_block_matrix_is_two_by_two_and_hermitian():
    h = spin_block_hamiltonian(0.2, -0.3, +1, lambda_so=0.06)
    assert h.shape == (2, 2)
    assert np.allclose(h, h.conjugate().T, atol=1e-12)


def test_spin_blocks_reconstruct_full_intrinsic_spectrum():
    kx, ky = 0.41, -0.32
    full = kane_mele_bands(kx, ky, lambda_so=0.06, lambda_r=0.0, delta=0.08)
    blocks = np.sort(np.concatenate([
        np.linalg.eigvalsh(spin_block_hamiltonian(kx, ky, +1, lambda_so=0.06, delta=0.08)),
        np.linalg.eigvalsh(spin_block_hamiltonian(kx, ky, -1, lambda_so=0.06, delta=0.08)),
    ]))
    assert np.allclose(full, blocks, atol=1e-12)


def test_spin_up_berry_curvature_at_K_reference():
    g = honeycomb_geometry()
    assert spin_block_berry_curvature(*g.k, +1, lambda_so=0.06) == pytest.approx(-11.5740740484, rel=2e-9)


def test_spin_down_berry_curvature_opposes_spin_up_at_K():
    g = honeycomb_geometry()
    up = spin_block_berry_curvature(*g.k, +1, lambda_so=0.06)
    dn = spin_block_berry_curvature(*g.k, -1, lambda_so=0.06)
    assert dn == pytest.approx(-up, rel=2e-9)


def test_spin_up_curvature_has_same_sign_at_two_valleys_in_topological_phase():
    g = honeycomb_geometry()
    k = spin_block_berry_curvature(*g.k, +1, lambda_so=0.06)
    kp = spin_block_berry_curvature(*g.kp, +1, lambda_so=0.06)
    assert kp == pytest.approx(k, rel=2e-9)


def test_spin_up_chern_is_minus_one_in_topological_phase():
    assert spin_chern_number(+1, mesh=30, lambda_so=0.06, delta=0.0) == pytest.approx(-1.0, abs=2e-12)


def test_spin_down_chern_is_plus_one_in_topological_phase():
    assert spin_chern_number(-1, mesh=30, lambda_so=0.06, delta=0.0) == pytest.approx(1.0, abs=2e-12)


def test_spin_chern_pair_is_opposite():
    cup, cdn = spin_chern_pair(mesh=30, lambda_so=0.06, delta=0.0)
    assert cup == pytest.approx(-cdn, abs=2e-12)


def test_z2_spin_conserving_is_one_in_topological_phase():
    assert z2_spin_conserving(mesh=30, lambda_so=0.06, delta=0.0) == 1


def test_spin_chern_is_zero_in_trivial_staggered_phase():
    cup, cdn = spin_chern_pair(mesh=30, lambda_so=0.06, delta=0.40)
    assert abs(cup) < 1e-10 and abs(cdn) < 1e-10


def test_z2_spin_conserving_is_zero_in_trivial_phase():
    assert z2_spin_conserving(mesh=30, lambda_so=0.06, delta=0.40) == 0


def test_phase_classifier_topological():
    assert phase_from_masses(0.06, 0.10) == "topological"


def test_phase_classifier_trivial():
    assert phase_from_masses(0.06, 0.40) == "trivial"


def test_phase_classifier_critical():
    assert phase_from_masses(0.06, critical_staggered_mass(0.06)) == "critical"


def test_total_occupied_chern_vanishes_by_time_reversal_intrinsic_case():
    assert occupied_subspace_chern(mesh=18, lambda_so=0.06, lambda_r=0.0) == pytest.approx(0.0, abs=2e-10)


def test_total_occupied_chern_vanishes_with_rashba():
    assert occupied_subspace_chern(mesh=18, lambda_so=0.06, lambda_r=0.04) == pytest.approx(0.0, abs=2e-10)


def test_intrinsic_soc_conserves_sz():
    assert spin_conservation_commutator_norm(0.31, -0.27, lambda_so=0.06, lambda_r=0.0) < 1e-12


def test_rashba_breaks_sz_conservation():
    assert spin_conservation_commutator_norm(0.31, -0.27, lambda_so=0.06, lambda_r=0.04) > 0.05


def test_adiabatic_rashba_path_stays_gapped_for_reference():
    path = adiabatic_rashba_gap_path(0.04, steps=4, mesh=30, lambda_so=0.06, delta=0.0)
    assert path.minimum_gap == pytest.approx(0.5035382907247955, rel=1e-12)
    assert path.adiabatically_connected


def test_adiabatic_rashba_path_inherits_nontrivial_z2_reference():
    path = adiabatic_rashba_gap_path(0.04, steps=4, mesh=30, lambda_so=0.06, delta=0.0)
    assert path.z2_reference == 1


def test_spinful_ribbon_dimension_and_hermiticity():
    h = spinful_zigzag_ribbon_hamiltonian(0.7, 9, lambda_so=0.06, lambda_r=0.02)
    assert h.shape == (36, 36)
    assert np.allclose(h, h.conjugate().T, atol=1e-12)


def test_spinful_ribbon_reduces_to_doubled_spinless_spectrum_without_soc():
    q, width = 1.7, 10
    es = np.linalg.eigvalsh(zigzag_ribbon_hamiltonian(q, width))
    efull = np.linalg.eigvalsh(spinful_zigzag_ribbon_hamiltonian(q, width, lambda_so=0.0, lambda_r=0.0))
    assert np.allclose(efull, np.repeat(es, 2), atol=2e-12)


def test_spinful_ribbon_time_reversal_is_exact_with_rashba():
    assert spinful_ribbon_time_reversal_error(0.83, 10, lambda_so=0.06, lambda_r=0.03) < 1e-12


def test_kramers_degeneracy_at_ribbon_time_reversal_momenta():
    assert kramers_pair_splitting(0.0, 10, lambda_so=0.06, lambda_r=0.03) < 5e-12
    assert kramers_pair_splitting(np.pi, 10, lambda_so=0.06, lambda_r=0.03) < 5e-12


def test_spinful_ribbon_spectrum_shape():
    q = np.linspace(-np.pi, np.pi, 11)
    assert spinful_ribbon_spectrum(q, 8, lambda_so=0.06).shape == (11, 32)


def test_intrinsic_edge_reference_is_strongly_localized_and_spin_polarized():
    s = edge_state_summary(np.pi - 0.15, 24, lambda_so=0.06, lambda_r=0.0)
    assert s["min_edge_weight"] > 0.98
    assert min(abs(x) for x in s["spin_z"]) > 0.999999


def test_rashba_edge_reference_survives_and_mixes_spin_slightly():
    s = edge_state_summary(np.pi - 0.15, 24, lambda_so=0.06, lambda_r=0.02)
    assert s["min_edge_weight"] > 0.979
    assert max(abs(x) for x in s["spin_z"]) < 0.999


def test_spinful_edge_weight_and_spin_expectation_accept_basis_state():
    width = 4
    v = np.zeros(4 * width, dtype=complex)
    v[0] = 1.0
    assert spinful_edge_weight(v, width) == pytest.approx(1.0)
    assert spin_z_expectation(v, width) == pytest.approx(1.0)


def test_reference_summary_contains_expected_topological_benchmarks():
    s = reference_summary()
    assert s["gK"] == pytest.approx(3.0 * np.sqrt(3.0), abs=1e-12)
    assert s["topological_spin_chern"] == pytest.approx([-1.0, 1.0], abs=2e-12)
    assert s["rashba_path_z2_reference"] == 1
