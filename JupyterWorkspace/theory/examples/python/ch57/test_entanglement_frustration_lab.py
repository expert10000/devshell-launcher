import numpy as np
import entanglement_frustration_lab as lab

# 1-3
def test_pauli_hermitian_x():
    assert np.allclose(lab.SX, lab.SX.conj().T)
def test_pauli_hermitian_y():
    assert np.allclose(lab.SY, lab.SY.conj().T)
def test_pauli_hermitian_z():
    assert np.allclose(lab.SZ, lab.SZ.conj().T)

# 4-6
def test_pauli_square_identity_x():
    assert np.allclose(lab.SX @ lab.SX, lab.I2)
def test_pauli_square_identity_y():
    assert np.allclose(lab.SY @ lab.SY, lab.I2)
def test_pauli_square_identity_z():
    assert np.allclose(lab.SZ @ lab.SZ, lab.I2)

# 7-10
def test_singlet_normalized():
    s = lab.singlet_state()
    assert np.isclose(np.vdot(s, s), 1.0)
def test_triplet_zero_normalized():
    t = lab.triplet_zero_state()
    assert np.isclose(np.vdot(t, t), 1.0)
def test_triplet_plus_normalized():
    t = lab.triplet_plus_state()
    assert np.isclose(np.vdot(t, t), 1.0)
def test_product_state_normalized():
    p = lab.product_updown_state()
    assert np.isclose(np.vdot(p, p), 1.0)

# 11-15
def test_reduced_density_trace_singlet_keep0():
    rho = lab.reduced_density_matrix(lab.singlet_state(), [0], [2, 2])
    assert np.isclose(np.trace(rho), 1.0)
def test_reduced_density_trace_singlet_keep1():
    rho = lab.reduced_density_matrix(lab.singlet_state(), [1], [2, 2])
    assert np.isclose(np.trace(rho), 1.0)
def test_reduced_density_trace_product_keep0():
    rho = lab.reduced_density_matrix(lab.product_updown_state(), [0], [2, 2])
    assert np.isclose(np.trace(rho), 1.0)
def test_reduced_density_trace_product_keep1():
    rho = lab.reduced_density_matrix(lab.product_updown_state(), [1], [2, 2])
    assert np.isclose(np.trace(rho), 1.0)
def test_reduced_density_singlet_is_half_identity():
    rho = lab.reduced_density_matrix(lab.singlet_state(), [0], [2, 2])
    assert np.allclose(rho, 0.5 * np.eye(2))

# 16-21
def test_singlet_entropy_one():
    rho = lab.reduced_density_matrix(lab.singlet_state(), [0], [2, 2])
    assert abs(lab.von_neumann_entropy(rho) - 1.0) < 1e-12
def test_triplet_zero_entropy_one():
    rho = lab.reduced_density_matrix(lab.triplet_zero_state(), [0], [2, 2])
    assert abs(lab.von_neumann_entropy(rho) - 1.0) < 1e-12
def test_triplet_plus_entropy_zero():
    rho = lab.reduced_density_matrix(lab.triplet_plus_state(), [0], [2, 2])
    assert abs(lab.von_neumann_entropy(rho)) < 1e-12
def test_product_entropy_zero():
    rho = lab.reduced_density_matrix(lab.product_updown_state(), [0], [2, 2])
    assert abs(lab.von_neumann_entropy(rho)) < 1e-12
def test_singlet_concurrence_one():
    rho = np.outer(lab.singlet_state(), lab.singlet_state().conj())
    assert abs(lab.concurrence(rho) - 1.0) < 1e-12
def test_triplet_zero_concurrence_one():
    rho = np.outer(lab.triplet_zero_state(), lab.triplet_zero_state().conj())
    assert abs(lab.concurrence(rho) - 1.0) < 1e-12

# 22-26
def test_triplet_plus_concurrence_zero():
    rho = np.outer(lab.triplet_plus_state(), lab.triplet_plus_state().conj())
    assert abs(lab.concurrence(rho)) < 1e-12
def test_product_concurrence_zero():
    rho = np.outer(lab.product_updown_state(), lab.product_updown_state().conj())
    assert abs(lab.concurrence(rho)) < 1e-12
def test_triangle_hamiltonian_hermitian():
    H = lab.heisenberg_triangle(1.0)
    assert np.allclose(H, H.conj().T)
def test_xxz_dimer_hermitian():
    H = lab.xxz_dimer(1.0, 1.5)
    assert np.allclose(H, H.conj().T)
def test_xyz_dimer_hermitian():
    H = lab.xyz_dimer(1.0, 0.8, 1.3)
    assert np.allclose(H, H.conj().T)

# 27-31
def test_triangle_ground_energy_exact():
    e0, _ = lab.ground_state(lab.heisenberg_triangle(1.0))
    assert abs(e0 + 0.75) < 1e-12
def test_triangle_total_spin_half_sector():
    _, psi = lab.ground_state(lab.heisenberg_triangle(1.0))
    assert abs(np.real(lab.expectation(psi, lab.total_spin_squared(3))) - 0.75) < 1e-12
def test_triangle_bond_correlation_01():
    H = lab.heisenberg_triangle(1.0)
    assert abs(lab.groundspace_expectation(H, lab.two_site_term(3, 0, 1)) + 0.25) < 1e-12
def test_triangle_bond_correlation_12():
    H = lab.heisenberg_triangle(1.0)
    assert abs(lab.groundspace_expectation(H, lab.two_site_term(3, 1, 2)) + 0.25) < 1e-12
def test_triangle_bond_correlation_20():
    H = lab.heisenberg_triangle(1.0)
    assert abs(lab.groundspace_expectation(H, lab.two_site_term(3, 2, 0)) + 0.25) < 1e-12

# 32-36
def test_xxz_reference_spectrum():
    vals = np.sort(np.real(np.linalg.eigvalsh(lab.xxz_dimer(1.0, 1.5))))
    assert np.allclose(vals, [-0.875, 0.125, 0.375, 0.375])
def test_xxz_isotropic_triplet_degeneracy_when_Jz_eq_Jxy():
    vals = np.sort(np.real(np.linalg.eigvalsh(lab.xxz_dimer(1.0, 1.0))))
    assert np.allclose(vals, [-0.75, 0.25, 0.25, 0.25])
def test_xyz_breaks_full_triplet_degeneracy():
    vals = np.sort(np.real(np.linalg.eigvalsh(lab.xyz_dimer(1.0, 0.8, 1.3))))
    assert len({round(float(v), 12) for v in vals}) == 4
def test_mg_chain_ground_energy_exact():
    vals = np.sort(np.real(np.linalg.eigvalsh(lab.j1j2_chain(4, 1.0, 0.5, pbc=True))))
    assert abs(vals[0] + 1.75) < 1e-12
def test_mg_chain_twofold_ground_degeneracy():
    vals = np.sort(np.real(np.linalg.eigvalsh(lab.j1j2_chain(4, 1.0, 0.5, pbc=True))))
    assert abs(vals[1] + 0.75) < 1e-12

# 37-42
def test_mg_state_A_is_ground_state():
    A, _ = lab.mg_states_N4()
    H = lab.j1j2_chain(4, 1.0, 0.5, pbc=True)
    e = np.real(np.vdot(A, H @ A))
    assert abs(e + 1.5) < 1e-12
def test_mg_state_B_is_ground_state():
    _, B = lab.mg_states_N4()
    H = lab.j1j2_chain(4, 1.0, 0.5, pbc=True)
    e = np.real(np.vdot(B, H @ B))
    assert abs(e + 1.5) < 1e-12
def test_mg_states_are_normalized():
    A, B = lab.mg_states_N4()
    assert np.isclose(np.vdot(A, A), 1.0)
    assert np.isclose(np.vdot(B, B), 1.0)
def test_mg_states_not_identical():
    A, B = lab.mg_states_N4()
    assert abs(np.vdot(A, B)) < 0.6
def test_dimerized_chain_ground_energy_exact():
    e0, _ = lab.ground_state(lab.dimerized_open_chain(4, 1.0, 0.0))
    assert abs(e0 + 1.5) < 1e-12
def test_dimerized_chain_block_entropy_zero_for_pair_cut():
    _, psi = lab.ground_state(lab.dimerized_open_chain(4, 1.0, 0.0))
    rho = lab.reduced_density_matrix(psi, [0, 1], [2, 2, 2, 2])
    assert abs(lab.von_neumann_entropy(rho)) < 1e-12

# 43-48
def test_dimerized_chain_single_spin_entropy_one():
    _, psi = lab.ground_state(lab.dimerized_open_chain(4, 1.0, 0.0))
    rho = lab.reduced_density_matrix(psi, [0], [2, 2, 2, 2])
    assert abs(lab.von_neumann_entropy(rho) - 1.0) < 1e-12
def test_chain6_ground_gap_positive():
    H = lab.j1j2_chain(6, 1.0, 0.0, pbc=False)
    assert lab.gap(H) > 0.0
def test_chain6_szz_pi_positive():
    _, psi = lab.ground_state(lab.j1j2_chain(6, 1.0, 0.0, pbc=False))
    assert lab.structure_factor_zz(psi, 6, np.pi) > 0.0
def test_connected_zz_symmetry():
    _, psi = lab.ground_state(lab.j1j2_chain(6, 1.0, 0.0, pbc=False))
    assert abs(lab.connected_zz(psi, 6, 1, 4) - lab.connected_zz(psi, 6, 4, 1)) < 1e-12
def test_dimer_indicator_is_real():
    _, psi = lab.ground_state(lab.j1j2_chain(6, 1.0, 0.0, pbc=False))
    val = lab.dimer_indicator(psi, 6)
    assert np.isfinite(val)
def test_structure_factor_zero_momentum_nonnegative():
    _, psi = lab.ground_state(lab.j1j2_chain(6, 1.0, 0.0, pbc=False))
    assert lab.structure_factor_zz(psi, 6, 0.0) >= -1e-12

# 49-54
def test_bond_correlation_symmetry_for_dot_product():
    _, psi = lab.ground_state(lab.heisenberg_triangle(1.0))
    assert abs(lab.bond_correlation(psi, 3, 0, 1) - lab.bond_correlation(psi, 3, 1, 0)) < 1e-12
def test_total_spin_squared_two_spins_singlet():
    s = lab.singlet_state()
    assert abs(np.real(lab.expectation(s, lab.total_spin_squared(2)))) < 1e-12
def test_total_spin_squared_two_spins_triplet():
    t = lab.triplet_zero_state()
    assert abs(np.real(lab.expectation(t, lab.total_spin_squared(2))) - 2.0) < 1e-12
def test_two_site_term_shape():
    assert lab.two_site_term(5, 1, 3).shape == (32, 32)
def test_local_operator_shape():
    assert lab.local_operator(5, 2, lab.SZ).shape == (32, 32)
def test_ground_state_vector_normalized():
    _, psi = lab.ground_state(lab.j1j2_chain(4, 1.0, 0.5, pbc=True))
    assert np.isclose(np.vdot(psi, psi), 1.0)

# 55-60
def test_reference_summary_singlet_values():
    r = lab.reference_summary()
    assert abs(r['singlet_entropy'] - 1.0) < 1e-12
    assert abs(r['singlet_concurrence'] - 1.0) < 1e-12
def test_reference_summary_triangle_values():
    r = lab.reference_summary()
    assert abs(r['triangle_ground_energy'] + 0.75) < 1e-12
    assert abs(r['triangle_bond_corr_01'] + 0.25) < 1e-12
def test_reference_summary_mg_values():
    r = lab.reference_summary()
    assert abs(r['mg_ground_energy'] + 1.75) < 1e-12
    assert abs(r['mg_first_excited_energy'] + 0.75) < 1e-12
def test_reference_summary_dimer_values():
    r = lab.reference_summary()
    assert abs(r['dimer_block_entropy_12']) < 1e-12
    assert abs(r['dimer_single_entropy_1'] - 1.0) < 1e-12
def test_reference_summary_chain6_values():
    r = lab.reference_summary()
    assert r['chain6_gap'] > 0.0
    assert r['chain6_Szz_pi'] > 0.0
def test_reference_summary_xxz_values():
    r = lab.reference_summary()
    assert np.allclose(r['xxz_eigenvalues'], [-0.875, 0.125, 0.375, 0.375])
