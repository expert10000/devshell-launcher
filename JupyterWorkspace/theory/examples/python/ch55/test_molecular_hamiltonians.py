import math
import numpy as np
import pytest

from molecular_hamiltonians import (
    bo_velocity_ratio,
    generalized_residual,
    harmonic_angular_frequency_from_curvature,
    hellmann_feynman_finite_difference,
    isotope_frequency_ratio,
    lcao_normalizations,
    morse_curvature,
    morse_local_angular_frequency,
    morse_potential,
    reduced_mass,
    two_center_lcao_energies,
    two_center_matrices,
)


def test_equal_mass_reduced_mass_is_half():
    assert reduced_mass(2.0, 2.0) == 1.0


def test_reduced_mass_is_symmetric():
    assert reduced_mass(3.0, 7.0) == reduced_mass(7.0, 3.0)


def test_invalid_mass_rejected():
    with pytest.raises(ValueError):
        reduced_mass(0.0, 1.0)


def test_bo_ratio_has_inverse_sqrt_scaling():
    assert np.isclose(bo_velocity_ratio(400.0), 0.05)
    assert np.isclose(bo_velocity_ratio(1600.0), 0.025)


def test_morse_minimum_is_minus_de():
    assert np.isclose(morse_potential(2.0, 5.0, 1.2, 2.0), -5.0)


def test_morse_dissociation_tends_to_zero():
    assert abs(float(morse_potential(30.0, 5.0, 1.2, 2.0))) < 1e-10


def test_morse_curvature_formula():
    assert np.isclose(morse_curvature(5.0, 1.2), 14.4)


def test_morse_frequency_matches_curvature_route():
    w1 = morse_local_angular_frequency(5.0, 1.2, 3.0)
    w2 = harmonic_angular_frequency_from_curvature(14.4, 3.0)
    assert np.isclose(w1, w2)


def test_heavier_isotope_has_lower_frequency():
    assert isotope_frequency_ratio(1.0, 4.0) == 0.5


def test_lcao_normalizations_are_positive():
    ng, nu = lcao_normalizations(0.2)
    assert ng > 0 and nu > 0
    assert ng < nu


def test_lcao_zero_overlap_reduces_to_sqrt2():
    ng, nu = lcao_normalizations(0.0)
    assert np.isclose(ng, 1 / math.sqrt(2))
    assert np.isclose(nu, 1 / math.sqrt(2))


def test_lcao_energies_at_zero_overlap():
    eg, eu = two_center_lcao_energies(-1.0, -0.2, 0.0)
    assert np.isclose(eg, -1.2)
    assert np.isclose(eu, -0.8)


def test_typical_negative_beta_places_bonding_lower():
    eg, eu = two_center_lcao_energies(-1.0, -0.25, 0.15)
    assert eg < eu


def test_generalized_eigen_residuals_vanish():
    assert generalized_residual(-1.0, -0.25, 0.15, "g") < 1e-12
    assert generalized_residual(-1.0, -0.25, 0.15, "u") < 1e-12


def test_overlap_matrix_positive_definite_for_valid_overlap():
    _, s = two_center_matrices(-1.0, -0.2, 0.4)
    assert np.all(np.linalg.eigvalsh(s) > 0)


def test_invalid_overlap_rejected():
    with pytest.raises(ValueError):
        lcao_normalizations(1.0)
    with pytest.raises(ValueError):
        two_center_lcao_energies(-1.0, -0.2, -1.0)


def test_finite_difference_recovers_quadratic_slope():
    r = np.array([0.0, 1.0, 2.0])
    e = r**2
    assert np.isclose(hellmann_feynman_finite_difference(e, r, 1), 2.0)


def test_finite_difference_requires_interior_point():
    with pytest.raises(ValueError):
        hellmann_feynman_finite_difference([0, 1, 4], [0, 1, 2], 0)

from molecular_hamiltonians import (
    bond_order,
    diatomic_orbital_family,
    generalized_eigensystem,
    generalized_eigen_residuals,
    heitler_london_normalizations,
    heteronuclear_two_center,
    minimal_ci_ground,
    mulliken_populations,
)


def test_generalized_identity_metric_matches_ordinary_eigenproblem():
    h = np.array([[-1.0, -0.2], [-0.2, -0.4]])
    e, _ = generalized_eigensystem(h, np.eye(2))
    assert np.allclose(e, np.linalg.eigvalsh(h))


def test_generalized_solver_residuals_vanish():
    e, c, h, s = heteronuclear_two_center(-1.1, -0.7, -0.2, 0.15)
    assert np.max(generalized_eigen_residuals(h, s, e, c)) < 1e-12


def test_generalized_vectors_are_s_orthonormal():
    e, c, _, s = heteronuclear_two_center(-1.1, -0.7, -0.2, 0.2)
    assert e[0] < e[1]
    assert np.allclose(c.T @ s @ c, np.eye(2), atol=1e-12)


def test_generalized_solver_rejects_singular_metric():
    with pytest.raises(ValueError):
        generalized_eigensystem(np.eye(2), np.array([[1.0, 1.0], [1.0, 1.0]]))


def test_heteronuclear_equal_centers_reduce_to_homonuclear_energies():
    e, _, _, _ = heteronuclear_two_center(-1.0, -1.0, -0.25, 0.15)
    eg, eu = two_center_lcao_energies(-1.0, -0.25, 0.15)
    assert np.allclose(e, sorted([eg, eu]))


def test_heteronuclear_lower_orbital_favors_lower_parent_level():
    _, c, _, s = heteronuclear_two_center(-1.3, -0.4, -0.12, 0.0)
    p = mulliken_populations(c[:, 0], s)
    assert p[0] > p[1]


def test_mulliken_populations_sum_to_one():
    _, c, _, s = heteronuclear_two_center(-1.0, -0.6, -0.2, 0.25)
    p = mulliken_populations(c[:, 0], s)
    assert np.isclose(np.sum(p), 1.0)


def test_mulliken_populations_ignore_global_orbital_sign():
    _, c, _, s = heteronuclear_two_center(-1.0, -0.6, -0.2, 0.1)
    assert np.allclose(mulliken_populations(c[:, 0], s), mulliken_populations(-c[:, 0], s))


def test_bond_order_two_bonding_electrons_is_one():
    assert bond_order(2, 0) == 1.0


def test_bond_order_equal_bonding_and_antibonding_is_zero():
    assert bond_order(2, 2) == 0.0


def test_bond_order_rejects_negative_occupation():
    with pytest.raises(ValueError):
        bond_order(-1, 0)


def test_diatomic_orbital_family_sigma_pi_delta():
    assert diatomic_orbital_family(0) == "sigma"
    assert diatomic_orbital_family(1) == "pi"
    assert diatomic_orbital_family(2) == "delta"


def test_heitler_london_normalizations_at_zero_overlap():
    ns, nt = heitler_london_normalizations(0.0)
    assert np.isclose(ns, 1 / math.sqrt(2))
    assert np.isclose(nt, 1 / math.sqrt(2))


def test_heitler_london_singlet_and_triplet_norms_move_oppositely():
    ns0, nt0 = heitler_london_normalizations(0.0)
    ns, nt = heitler_london_normalizations(0.4)
    assert ns < ns0
    assert nt > nt0


def test_heitler_london_rejects_unit_overlap():
    with pytest.raises(ValueError):
        heitler_london_normalizations(1.0)


def test_minimal_ci_without_coupling_returns_lower_configuration():
    e, c = minimal_ci_ground(-2.0, -1.0, 0.0)
    assert np.isclose(e, -2.0)
    assert np.allclose(np.abs(c), [1.0, 0.0])


def test_minimal_ci_coupling_lowers_energy_variationally():
    e, _ = minimal_ci_ground(-2.0, -1.0, 0.25)
    assert e < -2.0


def test_minimal_ci_vector_is_normalized():
    _, c = minimal_ci_ground(-2.0, -1.1, 0.3)
    assert np.isclose(c @ c, 1.0)

from molecular_hamiltonians import (
    dissociation_energy_from_ground,
    duschinsky_transform,
    harmonic_levels,
    harmonic_zero_point_energy,
    mass_weighted_hessian,
    mode_overlap_matrix,
    mode_participation_ratio,
    morse_bound_energies,
    morse_bound_state_count,
    normal_modes,
    vibrational_mode_count,
)


def test_mass_weighted_hessian_diagonal_scaling():
    f = mass_weighted_hessian(np.diag([4.0, 9.0]), [1.0, 9.0])
    assert np.allclose(f, np.diag([4.0, 1.0]))


def test_mass_weighted_hessian_rejects_nonpositive_mass():
    with pytest.raises(ValueError):
        mass_weighted_hessian(np.eye(2), [1.0, 0.0])


def test_normal_modes_recover_simple_frequencies():
    omega, l, cart = normal_modes(np.diag([4.0, 9.0]), [1.0, 1.0])
    assert np.allclose(omega, [2.0, 3.0])
    assert np.allclose(l.T @ l, np.eye(2))
    assert cart.shape == (2, 2)


def test_normal_modes_keep_small_numerical_zero():
    omega, _, _ = normal_modes(np.diag([-1e-12, 4.0]), [1.0, 1.0], negative_tolerance=1e-10)
    assert np.isclose(omega[0], 0.0)
    assert np.isclose(omega[1], 2.0)


def test_normal_modes_reject_genuine_instability():
    with pytest.raises(ValueError):
        normal_modes(np.diag([-0.01, 1.0]), [1.0, 1.0])


def test_vibrational_mode_counts_linear_and_nonlinear():
    assert vibrational_mode_count(2, True) == 1
    assert vibrational_mode_count(3, True) == 4
    assert vibrational_mode_count(3, False) == 3


def test_vibrational_mode_count_rejects_nonlinear_diatomic():
    with pytest.raises(ValueError):
        vibrational_mode_count(2, False)


def test_harmonic_levels_are_equally_spaced():
    e = harmonic_levels(2.5, 5)
    assert np.allclose(np.diff(e), 2.5)
    assert np.isclose(e[0], 1.25)


def test_harmonic_zero_point_energy_sums_modes_and_ignores_zeros():
    assert np.isclose(harmonic_zero_point_energy([0.0, 2.0, 4.0]), 3.0)


def test_harmonic_zero_point_rejects_negative_frequency():
    with pytest.raises(ValueError):
        harmonic_zero_point_energy([1.0, -0.2])


def test_morse_bound_state_count_is_finite():
    n = morse_bound_state_count(de=8.0, a=1.0, mu=2.0)
    assert n == 6


def test_morse_bound_energies_are_below_dissociation_and_increasing():
    e = morse_bound_energies(de=8.0, a=1.0, mu=2.0)
    assert len(e) == 6
    assert np.all(np.diff(e) > 0)
    assert np.all(e < 8.0)


def test_morse_level_spacings_compress_upward():
    e = morse_bound_energies(de=8.0, a=1.0, mu=2.0)
    spacings = np.diff(e)
    assert np.all(np.diff(spacings) < 0)


def test_morse_lowest_spacing_approaches_local_harmonic_scale():
    de, a, mu = 200.0, 0.25, 10.0
    e = morse_bound_energies(de, a, mu)
    omega = morse_local_angular_frequency(de, a, mu)
    assert np.isclose(e[1] - e[0], omega - a * a / mu, rtol=1e-12)


def test_d0_is_smaller_than_de_by_zero_point_energy():
    assert np.isclose(dissociation_energy_from_ground(5.0, 0.4), 4.6)


def test_participation_ratio_one_coordinate_is_one():
    assert np.isclose(mode_participation_ratio([1.0, 0.0, 0.0]), 1.0)


def test_participation_ratio_uniform_four_coordinate_mode_is_four():
    assert np.isclose(mode_participation_ratio([1.0, 1.0, 1.0, 1.0]), 4.0)


def test_mode_overlap_identity_for_same_basis():
    q, _ = np.linalg.qr(np.array([[1.0, 2.0], [3.0, 1.0]]))
    assert np.allclose(mode_overlap_matrix(q, q), np.eye(2))


def test_mode_overlap_detects_rotation():
    theta = 0.3
    j = np.array([[math.cos(theta), -math.sin(theta)], [math.sin(theta), math.cos(theta)]])
    assert np.allclose(mode_overlap_matrix(np.eye(2), j), j)


def test_duschinsky_rotation_and_displacement():
    theta = math.pi / 2
    j = np.array([[math.cos(theta), -math.sin(theta)], [math.sin(theta), math.cos(theta)]])
    qp = duschinsky_transform([1.0, 0.0], j, [0.5, -0.5])
    assert np.allclose(qp, [0.5, 0.5])

from molecular_hamiltonians import (
    centrifugal_distorted_levels,
    diatomic_moment_of_inertia,
    diatomic_pr_branch_positions,
    rigid_rotor_levels,
    rotational_constant,
    rotational_degeneracy,
    rotational_isotope_ratio,
    rovibrational_term_value,
    symmetric_top_energy,
    vibration_dependent_rotational_constant,
)


def test_diatomic_moment_of_inertia_uses_reduced_mass():
    assert np.isclose(diatomic_moment_of_inertia(2.0, 2.0, 3.0), 9.0)


def test_rotational_constant_inverse_inertia():
    assert np.isclose(rotational_constant(2.0), 0.25)
    assert rotational_constant(4.0) < rotational_constant(2.0)


def test_rotational_constant_rejects_nonpositive_inertia():
    with pytest.raises(ValueError):
        rotational_constant(0.0)


def test_rigid_rotor_levels_follow_j_jplus1():
    assert np.allclose(rigid_rotor_levels(1.5, 3), [0.0, 3.0, 9.0, 18.0])


def test_rigid_rotor_adjacent_gaps_grow_linearly():
    e = rigid_rotor_levels(2.0, 4)
    assert np.allclose(np.diff(e), [4.0, 8.0, 12.0, 16.0])


def test_rotational_degeneracy_is_two_j_plus_one():
    assert [rotational_degeneracy(j) for j in range(4)] == [1, 3, 5, 7]


def test_rotational_degeneracy_rejects_negative_j():
    with pytest.raises(ValueError):
        rotational_degeneracy(-1)


def test_heavier_isotope_has_smaller_rotational_constant():
    assert np.isclose(rotational_isotope_ratio(1.0, 2.0), 0.5)


def test_rotational_isotope_ratio_includes_bond_length_change():
    assert np.isclose(rotational_isotope_ratio(1.0, 2.0, 1.0, 2.0), 0.125)


def test_symmetric_top_k_zero_reduces_to_bj_jplus1():
    assert np.isclose(symmetric_top_energy(5.0, 2.0, 3, 0), 24.0)


def test_prolate_symmetric_top_energy_rises_with_abs_k_when_a_gt_b():
    e0 = symmetric_top_energy(5.0, 2.0, 3, 0)
    e2 = symmetric_top_energy(5.0, 2.0, 3, 2)
    assert e2 > e0


def test_symmetric_top_rejects_abs_k_gt_j():
    with pytest.raises(ValueError):
        symmetric_top_energy(5.0, 2.0, 2, 3)


def test_centrifugal_distortion_lowers_high_j_levels():
    rigid = rigid_rotor_levels(1.0, 5)
    nonrigid = centrifugal_distorted_levels(1.0, 1e-3, 5)
    assert np.isclose(nonrigid[0], rigid[0])
    assert nonrigid[-1] < rigid[-1]


def test_zero_distortion_matches_rigid_rotor():
    assert np.allclose(centrifugal_distorted_levels(1.3, 0.0, 5), rigid_rotor_levels(1.3, 5))


def test_vibrational_excitation_reduces_bv_for_positive_alpha():
    assert vibration_dependent_rotational_constant(10.0, 0.2, 1) < vibration_dependent_rotational_constant(10.0, 0.2, 0)


def test_bv_formula_at_v_zero():
    assert np.isclose(vibration_dependent_rotational_constant(10.0, 0.4, 0), 9.8)


def test_rovibrational_term_value_contains_rotation_and_distortion():
    e = rovibrational_term_value(100.0, 2.0, 2, 0.01)
    assert np.isclose(e, 100.0 + 12.0 - 0.36)


def test_pr_branches_straddle_band_origin_when_constants_equal():
    lines = diatomic_pr_branch_positions(1000.0, 2.0, 2.0, 4)
    assert np.all(lines["P"] < 1000.0)
    assert np.all(lines["R"] > 1000.0)


def test_equal_b_pr_branch_spacing_is_two_b():
    lines = diatomic_pr_branch_positions(1000.0, 2.0, 2.0, 5)
    assert np.allclose(np.diff(lines["P"]), -4.0)
    assert np.allclose(np.diff(lines["R"]), 4.0)


def test_pr_branch_positions_require_positive_jmax():
    with pytest.raises(ValueError):
        diatomic_pr_branch_positions(1000.0, 2.0, 2.0, 0)


# ---------------------------------------------------------------------------
# Commit 607 -- IR/Raman and quantitative rovibrational spectroscopy tests
# ---------------------------------------------------------------------------

from molecular_hamiltonians import (
    vibrational_term_cm,
    vibration_rotation_constant_cm,
    rotational_term_cm,
    pure_rotational_lines_cm,
    rovibrational_pr_lines_cm,
    ir_activity_strength,
    raman_activity_strength,
    honl_london_sigma_sigma,
    rotational_boltzmann_populations,
    rovibrational_stick_spectrum,
    einstein_A_electric_dipole,
    radiative_lifetime_and_branching,
    gaussian_profile,
    lorentzian_profile,
    broaden_stick_spectrum,
)


def test_c607_rotational_ground_term_zero():
    assert rotational_term_cm(0, 1.9) == 0.0


def test_c607_rotational_J1_includes_distortion():
    assert abs(rotational_term_cm(1, 2.0, 0.01) - (4.0 - 0.04)) < 1e-12


def test_c607_pure_rotor_lines_are_2B_spacing_in_rigid_limit():
    lines = pure_rotational_lines_cm(1.5, 3)
    got = [x[2] for x in lines]
    assert all(abs(a-b) < 1e-12 for a,b in zip(got, [3.0, 6.0, 9.0, 12.0]))


def test_c607_vibrational_harmonic_spacing():
    e0 = vibrational_term_cm(0, 1000.0)
    e1 = vibrational_term_cm(1, 1000.0)
    assert abs((e1-e0) - 1000.0) < 1e-12


def test_c607_vibrational_anharmonic_spacing_contracts():
    d01 = vibrational_term_cm(1, 1000.0, 10.0) - vibrational_term_cm(0, 1000.0, 10.0)
    d12 = vibrational_term_cm(2, 1000.0, 10.0) - vibrational_term_cm(1, 1000.0, 10.0)
    assert d12 < d01


def test_c607_Bv_decreases_with_v_for_positive_alpha():
    assert vibration_rotation_constant_cm(2.0, 0.02, 1) < vibration_rotation_constant_cm(2.0, 0.02, 0)


def test_c607_parallel_band_PR_rigid_formulas():
    d = rovibrational_pr_lines_cm(2000.0, 2.0, 2.0, 2)
    p1 = next(x for x in d["P"] if x[0] == 1)[2]
    r1 = next(x for x in d["R"] if x[0] == 1)[2]
    assert abs(p1 - 1996.0) < 1e-12
    assert abs(r1 - 2008.0) < 1e-12


def test_c607_parallel_band_has_no_universal_Q_branch():
    assert set(rovibrational_pr_lines_cm(1000.0, 1.0, 1.0, 2)) == {"P", "R"}


def test_c607_ir_zero_derivative_is_dark():
    assert ir_activity_strength([0.0, 0.0, 0.0]) == 0.0


def test_c607_ir_strength_is_squared_norm():
    assert abs(ir_activity_strength([3.0, 4.0]) - 25.0) < 1e-12


def test_c607_raman_activity_is_positive_tensor_norm():
    assert abs(raman_activity_strength([[1.0, 2.0], [2.0, 0.0]]) - 9.0) < 1e-12


def test_c607_honl_london_PR_factors_sum_to_one():
    for J in range(1, 8):
        assert abs(honl_london_sigma_sigma(J, "P") + honl_london_sigma_sigma(J, "R") - 1.0) < 1e-12


def test_c607_rotational_populations_normalize():
    p = rotational_boltzmann_populations(2.0, 300.0, 30)
    assert abs(sum(p) - 1.0) < 1e-12


def test_c607_higher_temperature_moves_population_peak_upward():
    low = rotational_boltzmann_populations(2.0, 20.0, 30)
    high = rotational_boltzmann_populations(2.0, 300.0, 30)
    assert max(range(len(high)), key=high.__getitem__) > max(range(len(low)), key=low.__getitem__)


def test_c607_einstein_A_has_frequency_cube_scaling():
    a1 = einstein_A_electric_dipole(1.0e12, 1.0e-30)
    a2 = einstein_A_electric_dipole(2.0e12, 1.0e-30)
    assert abs(a2/a1 - 8.0) < 1e-12


def test_c607_branching_normalizes_and_lifetime_is_inverse_total_rate():
    tau, b = radiative_lifetime_and_branching([2.0, 3.0, 5.0])
    assert abs(tau - 0.1) < 1e-12
    assert abs(sum(b) - 1.0) < 1e-12


def test_c607_lorentzian_half_max_at_half_fwhm():
    peak = lorentzian_profile(0.0, 0.0, 2.0)
    half = lorentzian_profile(1.0, 0.0, 2.0)
    assert abs(half/peak - 0.5) < 1e-12


def test_c607_gaussian_numeric_area_is_unity():
    xs = [(-5.0 + 10.0*i/20000.0) for i in range(20001)]
    ys = [gaussian_profile(x, 0.0, 1.0) for x in xs]
    dx = xs[1] - xs[0]
    area = dx * (0.5*ys[0] + sum(ys[1:-1]) + 0.5*ys[-1])
    assert abs(area - 1.0) < 2e-5


def test_c607_synthetic_spectrum_preserves_stick_area_on_wide_grid():
    sticks = [(0.0, 1.0), (3.0, 2.0)]
    xs = [(-10.0 + 25.0*i/25000.0) for i in range(25001)]
    ys = broaden_stick_spectrum(xs, sticks, 0.3, "gaussian")
    dx = xs[1] - xs[0]
    area = dx * (0.5*ys[0] + sum(ys[1:-1]) + 0.5*ys[-1])
    assert abs(area - 3.0) < 2e-4


def test_c607_thermal_rovibrational_sticks_are_nonnegative_and_have_both_branches():
    sticks = rovibrational_stick_spectrum(2000.0, 1.9, 1.87, 300.0, 8)
    assert sticks
    assert all(s >= 0.0 for _, s, _, _ in sticks)
    assert {b for _, _, b, _ in sticks} == {"P", "R"}

# COMMIT608_VIBRONIC_TESTS_BEGIN
import math as _math_commit608
import numpy as _np_commit608
import molecular_hamiltonians as _c608

def test_c608_fc_s_zero_origin_only():
    assert _c608.franck_condon_0n(0, 0.0) == 1.0
    assert _c608.franck_condon_0n(3, 0.0) == 0.0

def test_c608_fc_poisson_value():
    assert _np_commit608.isclose(_c608.franck_condon_0n(2, 2.0), _math_commit608.exp(-2.0)*2.0)

def test_c608_fc_progression_captures_probability():
    p=_c608.franck_condon_progression(1.7,30)
    assert p.shape==(31,)
    assert _np_commit608.isclose(p.sum(),1.0,atol=1e-10)

def test_c608_fc_ratio_rule():
    p=_c608.franck_condon_progression(2.5,8)
    assert _np_commit608.isclose(p[4]/p[3],2.5/4.0)

def test_c608_amplitude_square_is_fc():
    for n in range(6):
        a=_c608.displaced_oscillator_0n_amplitude(n,1.2)
        assert _np_commit608.isclose(abs(a)**2,_c608.franck_condon_0n(n,1.2))

def test_c608_huang_rhys_displacement_roundtrip():
    for dq in (0.0,0.5,2.0):
        S=_c608.huang_rhys_from_dimensionless_displacement(dq)
        assert _np_commit608.isclose(_c608.dimensionless_displacement_from_huang_rhys(S),abs(dq))

def test_c608_multimode_product():
    q=[0,1,2]; S=[0.4,0.7,1.1]
    want=_np_commit608.prod([_c608.franck_condon_0n(n,s) for n,s in zip(q,S)])
    assert _np_commit608.isclose(_c608.multimode_fc_zero_to_state(q,S),want)

def test_c608_multimode_origin_is_exp_minus_sum_S():
    S=_np_commit608.array([0.4,0.7,0.9])
    got=_c608.multimode_fc_zero_to_state([0,0,0],S)
    assert _np_commit608.isclose(got,_math_commit608.exp(-S.sum()))

def test_c608_thermal_populations_geometric_ratio():
    p=_c608.thermal_vibrational_populations(0.8,8)
    assert _np_commit608.isclose(p[3]/p[2],_math_commit608.exp(-0.8))

def test_c608_thermal_population_truncated_below_one():
    p=_c608.thermal_vibrational_populations(0.7,5)
    assert 0.0<p.sum()<1.0

def test_c608_partition_function():
    x=1.3
    assert _np_commit608.isclose(_c608.harmonic_vibrational_partition(x),1.0/(1.0-_math_commit608.exp(-x)))

def test_c608_duschinsky_identity():
    q=_np_commit608.array([0.2,-0.3]); K=_np_commit608.array([1.0,2.0])
    assert _np_commit608.allclose(_c608.duschinsky_transform(q,_np_commit608.eye(2),K),q+K)

def test_c608_duschinsky_rotation_inverse():
    th=0.37
    J=_np_commit608.array([[_math_commit608.cos(th),-_math_commit608.sin(th)],
                           [_math_commit608.sin(th), _math_commit608.cos(th)]])
    q=_np_commit608.array([0.4,-1.1]); K=_np_commit608.array([0.2,0.6])
    qp=_c608.duschinsky_transform(q,J,K)
    assert _np_commit608.allclose(_c608.duschinsky_inverse(qp,J,K),q)

def test_c608_duschinsky_orthogonality_error_rotation():
    th=0.51
    J=_np_commit608.array([[_math_commit608.cos(th),-_math_commit608.sin(th)],
                           [_math_commit608.sin(th), _math_commit608.cos(th)]])
    assert _c608.duschinsky_orthogonality_error(J)<1e-12
    assert _c608.is_orthogonal_duschinsky(J)

def test_c608_duschinsky_detects_nonorthogonal():
    J=_np_commit608.array([[1.0,0.2],[0.0,1.0]])
    assert _c608.duschinsky_orthogonality_error(J)>0.1
    assert not _c608.is_orthogonal_duschinsky(J,tol=1e-3)

def test_c608_condon_intensity():
    assert _np_commit608.isclose(_c608.condon_intensity(2.0,0.25),1.0)

def test_c608_herzberg_teller_moment():
    assert _np_commit608.isclose(_c608.herzberg_teller_moment(1.0,0.5,2.0),2.0)

def test_c608_herzberg_teller_interference():
    assert _np_commit608.isclose(_c608.herzberg_teller_intensity(1.0,-0.25,2.0),0.25)

def test_c608_single_mode_stick_positions():
    p,s=_c608.vibronic_stick_spectrum_0n(20000.0,1200.0,1.0,3)
    assert _np_commit608.allclose(p,[20000.,21200.,22400.,23600.])
    assert s.shape==(4,)

def test_c608_single_mode_stick_strengths_are_fc():
    _,s=_c608.vibronic_stick_spectrum_0n(10000.,500.,0.8,6,scale=3.0)
    assert _np_commit608.allclose(s/3.0,_c608.franck_condon_progression(0.8,6))

def test_c608_multimode_stick_count():
    p,s,states=_c608.multimode_vibronic_sticks(15000.,[500.,800.],[0.3,0.6],2)
    assert len(p)==len(s)==len(states)==9

def test_c608_multimode_stick_origin():
    p,s,states=_c608.multimode_vibronic_sticks(15000.,[500.,800.],[0.3,0.6],1)
    idx=_np_commit608.where((states==[0,0]).all(axis=1))[0][0]
    assert _np_commit608.isclose(p[idx],15000.)
    assert _np_commit608.isclose(s[idx],_math_commit608.exp(-0.9))

def test_c608_gaussian_broadening_area():
    x=_np_commit608.linspace(-20.,20.,20001)
    y=_c608.gaussian_broaden_vibronic_spectrum(x,[0.],[2.5],1.3)
    area=_np_commit608.trapezoid(y,x) if hasattr(_np_commit608,"trapezoid") else _np_commit608.trapz(y,x)
    assert _np_commit608.isclose(area,2.5,atol=2e-4)

def test_c608_invalid_inputs_raise():
    import pytest
    with pytest.raises(ValueError): _c608.franck_condon_0n(-1,1.0)
    with pytest.raises(ValueError): _c608.franck_condon_0n(1,-0.1)
    with pytest.raises(ValueError): _c608.duschinsky_transform([1.,2.],_np_commit608.eye(3),[0.,0.])
# COMMIT608_VIBRONIC_TESTS_END

# COMMIT609_NONADIABATIC_TESTS_BEGIN
import math as _math_commit609
import numpy as _np_commit609
import molecular_hamiltonians as _c609

def test_c609_uncoupled_two_state_energies_cross():
    lo,hi=_c609.two_state_adiabatic_energies(-1.0,1.0,0.0)
    assert _np_commit609.isclose(lo,-1.0)
    assert _np_commit609.isclose(hi,1.0)

def test_c609_avoided_crossing_gap():
    lo,hi=_c609.two_state_adiabatic_energies(2.0,2.0,0.35)
    assert _np_commit609.isclose(hi-lo,0.7)
    assert _np_commit609.isclose(_c609.avoided_crossing_min_gap(0.35),0.7)

def test_c609_two_state_energy_symmetry():
    lo1,hi1=_c609.two_state_adiabatic_energies(1.0,3.0,0.4)
    lo2,hi2=_c609.two_state_adiabatic_energies(3.0,1.0,0.4)
    assert _np_commit609.allclose([lo1,hi1],[lo2,hi2])

def test_c609_mixing_angle_at_crossing():
    th=_c609.two_state_mixing_angle(0.0,0.0,1.0)
    assert _np_commit609.isclose(th,_math_commit609.pi/4)

def test_c609_rotation_is_orthogonal():
    U=_c609.rotation_matrix_2state(0.37)
    assert _c609.unitary_error(U)<1e-12

def test_c609_adiabatic_to_diabatic_preserves_eigenvalues():
    H=_c609.adiabatic_to_diabatic_potential(-0.8,1.7,0.43)
    vals=_np_commit609.linalg.eigvalsh(H)
    assert _np_commit609.allclose(vals,[-0.8,1.7])

def test_c609_diagonalize_real_two_state():
    vals,vecs=_c609.diagonalize_real_two_state(0.0,0.0,0.5)
    assert _np_commit609.allclose(vals,[-0.5,0.5])
    assert _np_commit609.allclose(vecs.T@vecs,_np_commit609.eye(2))

def test_c609_derivative_coupling_peaks_at_crossing():
    R=_np_commit609.array([0.0,1.0,2.0])
    d=_np_commit609.abs(_c609.derivative_coupling_linear_crossing(R,1.0,0.2))
    assert d[0]>d[1]>d[2]

def test_c609_derivative_coupling_crossing_value():
    got=_c609.derivative_coupling_linear_crossing(0.0,2.0,0.5)
    assert _np_commit609.isclose(got,-1.0)

def test_c609_gradient_identity_inverse_gap():
    d1=_c609.derivative_coupling_from_hamiltonian_gradient(0.2,1.0)
    d2=_c609.derivative_coupling_from_hamiltonian_gradient(0.2,0.5)
    assert _np_commit609.isclose(d2,2*d1)

def test_c609_lz_gamma():
    assert _np_commit609.isclose(_c609.landau_zener_gamma(2.0,8.0,hbar=1.0),0.5)

def test_c609_lz_probability_limits_weak_coupling():
    p=_c609.landau_zener_diabatic_survival(1e-6,1.0)
    assert p>0.999999999

def test_c609_lz_probability_strong_slow():
    p=_c609.landau_zener_diabatic_survival(2.0,0.2)
    assert p<1e-20

def test_c609_lz_complement():
    pd=_c609.landau_zener_diabatic_survival(0.4,1.2)
    pa=_c609.landau_zener_adiabatic_following(0.4,1.2)
    assert _np_commit609.isclose(pd+pa,1.0)

def test_c609_lz_sweep_rate():
    assert _np_commit609.isclose(_c609.landau_zener_sweep_rate(-3.0,-2.0),6.0)

def test_c609_ci_degenerate_at_origin():
    lo,hi=_c609.conical_intersection_energies(0.0,0.0,E0=1.7)
    assert _np_commit609.isclose(lo,1.7)
    assert _np_commit609.isclose(hi,1.7)

def test_c609_ci_gap_radial_isotropic():
    g=_c609.conical_intersection_gap(3.0,4.0)
    assert _np_commit609.isclose(g,10.0)

def test_c609_ci_anisotropic_gap():
    g=_c609.conical_intersection_gap(1.0,1.0,kappa=2.0,lam=3.0)
    assert _np_commit609.isclose(g,2*_math_commit609.sqrt(13.0))

def test_c609_winding_once_counterclockwise():
    t=_np_commit609.linspace(0,2*_math_commit609.pi,101)
    pts=_np_commit609.column_stack([_np_commit609.cos(t),_np_commit609.sin(t)])
    assert _c609.winding_number_xy(pts)==1

def test_c609_winding_clockwise():
    t=_np_commit609.linspace(0,-2*_math_commit609.pi,101)
    pts=_np_commit609.column_stack([_np_commit609.cos(t),_np_commit609.sin(t)])
    assert _c609.winding_number_xy(pts)==-1

def test_c609_berry_phase_pi_for_one_winding():
    t=_np_commit609.linspace(0,2*_math_commit609.pi,101)
    pts=_np_commit609.column_stack([_np_commit609.cos(t),_np_commit609.sin(t)])
    assert _np_commit609.isclose(_c609.conical_intersection_berry_phase(pts),_math_commit609.pi)

def test_c609_state_populations_normalize():
    p=_c609.two_state_populations([1+1j,2-1j])
    assert _np_commit609.isclose(p.sum(),1.0)

def test_c609_basis_transform_preserves_norm_for_rotation():
    U=_c609.rotation_matrix_2state(0.8)
    psi=_np_commit609.array([1+0.2j,-0.4+0.7j])
    out=_c609.transform_state_basis(psi,U)
    assert _np_commit609.isclose(_np_commit609.linalg.norm(out),_np_commit609.linalg.norm(psi))

def test_c609_adiabaticity_labels():
    assert _c609.adiabaticity_regime(0.01,1.0)[1]=="diabatic"
    assert _c609.adiabaticity_regime(2.0,1.0)[1]=="adiabatic"
# COMMIT609_NONADIABATIC_TESTS_END

# COMMIT610_MOLECULAR_INTEGRATION_TESTS_BEGIN
import math as _math_commit610
import numpy as _np_commit610
import molecular_hamiltonians as _c610

def test_c610_lambda_letters():
    assert [_c610.molecular_lambda_letter(i) for i in range(4)]==["Sigma","Pi","Delta","Phi"]

def test_c610_omega_projection():
    assert _np_commit610.isclose(_c610.omega_projection(1,0.5),1.5)
    assert _np_commit610.isclose(_c610.omega_projection(1,-1.5),0.5)

def test_c610_spin_orbit_shift():
    assert _np_commit610.isclose(_c610.spin_orbit_case_a_shift(100.0,1,0.5),50.0)

def test_c610_spin_rotation_shift():
    got=_c610.spin_rotation_shift(2.0,1.5,1.0,0.5)
    want=1.0*(1.5*2.5-1*2-0.5*1.5)
    assert _np_commit610.isclose(got,want)

def test_c610_hund_indicator_grows_with_spin_orbit():
    assert _c610.hund_case_indicator(100.0,2.0,5)>_c610.hund_case_indicator(10.0,2.0,5)

def test_c610_lambda_doubling_scaling():
    assert _np_commit610.isclose(_c610.lambda_doubling_splitting(0.1,2),0.6)

def test_c610_lambda_doublet_center():
    lo,hi=_c610.lambda_doublet_levels(20.0,0.2,1)
    assert _np_commit610.isclose((lo+hi)/2,20.0)

def test_c610_stark_doublet_zero_field():
    lo,hi=_c610.stark_parity_doublet_levels(0.8,2.0,0.0,center=5.0)
    assert _np_commit610.allclose([lo,hi],[4.6,5.4])

def test_c610_stark_doublet_gap_increases_with_field():
    a=_c610.stark_parity_doublet_levels(0.8,1.0,0.1)
    b=_c610.stark_parity_doublet_levels(0.8,1.0,1.0)
    assert (b[1]-b[0])>(a[1]-a[0])

def test_c610_zeeman_linear_sign():
    assert _c610.zeeman_shift_linear(2.0,-1.5,3.0,mu_B=1.0)==-9.0

def test_c610_spin_half_subspaces_are_three_and_one():
    assert _c610.nuclear_spin_subspace_dimensions(0.5)==(3,1)

def test_c610_spin_one_subspaces_are_six_and_three():
    assert _c610.nuclear_spin_subspace_dimensions(1)==(6,3)

def test_c610_required_spin_weight():
    assert _c610.required_nuclear_spin_weight(0.5,1)==3
    assert _c610.required_nuclear_spin_weight(0.5,-1)==1

def test_c610_asymmetric_top_matrix_symmetric():
    K,H=_c610.asymmetric_top_matrix(3,10.0,6.0,4.0)
    assert _np_commit610.allclose(H,H.T)
    assert len(K)==7

def test_c610_asymmetric_top_couples_delta_K_two_only():
    K,H=_c610.asymmetric_top_matrix(3,10.0,6.0,4.0)
    nz=_np_commit610.argwhere(_np_commit610.abs(H)>1e-12)
    for i,j in nz:
        if i!=j:
            assert abs(K[i]-K[j])==2

def test_c610_symmetric_top_limit_matches_diagonal_formula():
    J=2; A=10.0; B=4.0
    K,H=_c610.asymmetric_top_matrix(J,A,B,B)
    assert _np_commit610.allclose(H,_np_commit610.diag(_np_commit610.diag(H)))
    expected=[_c610.symmetric_top_energy(A,B,J,int(k)) for k in K]
    assert _np_commit610.allclose(_np_commit610.diag(H),expected)

def test_c610_spherical_top_degeneracy():
    vals=_c610.asymmetric_top_levels(3,5.0,5.0,5.0)
    assert _np_commit610.allclose(vals,_c610.spherical_top_energy(3,5.0))

def test_c610_asymmetric_top_trace_is_basis_invariant():
    _,H=_c610.asymmetric_top_matrix(2,9.0,5.0,3.0)
    vals=_c610.asymmetric_top_levels(2,9.0,5.0,3.0)
    assert _np_commit610.isclose(_np_commit610.trace(H),vals.sum())

def test_c610_fermi_resonance_exact_resonance_gap():
    lo,hi=_c610.fermi_resonance_levels(1000.0,1000.0,12.0)
    assert _np_commit610.isclose(hi-lo,24.0)

def test_c610_fermi_splitting_formula():
    got=_c610.fermi_resonance_splitting(1000.0,1010.0,3.0)
    assert _np_commit610.isclose(got,_math_commit610.sqrt(136.0))

def test_c610_fermi_mixing_at_resonance():
    th=_c610.fermi_mixing_angle(1000.0,1000.0,5.0)
    assert _np_commit610.isclose(abs(th),_math_commit610.pi/4)

def test_c610_coriolis_shift_sign():
    assert _c610.coriolis_diagonal_shift(2.0,0.5,1,1)==-2.0

def test_c610_field_mixing_limits():
    assert _c610.field_mixing_fraction(10.0,0.0)==0.0
    assert _c610.field_mixing_fraction(0.0,2.0)==0.5

def test_c610_dependency_chain_order():
    chain=_c610.molecular_dependency_order()
    assert chain[0]=="electronic"
    assert chain[-1]=="nonadiabatic"
    assert len(chain)==7
# COMMIT610_MOLECULAR_INTEGRATION_TESTS_END
