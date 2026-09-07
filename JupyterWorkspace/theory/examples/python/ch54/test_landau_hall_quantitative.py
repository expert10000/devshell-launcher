#!/usr/bin/env python3
from __future__ import annotations
import numpy as np
import pytest

from landau_hall_quantitative import (
    TWOPI,
    clean_hall_diagnostics,
    disorder_plateau_diagnostics,
    hofstadter_torus,
    inverse_participation_ratio,
    occupied_subspace_chern,
    strip_hamiltonian,
    strip_spectrum,
    twisted_eigensystem,
    magnetic_bloch_hamiltonian,
    kubo_band_chern_numbers,
    streda_lowest_gap_counting,
    laughlin_flux_pump,
    lll_form_factor,
    lll_interaction_filter,
    coulomb_pseudopotential,
    coulomb_pseudopotentials,
    interaction_cyclotron_ratio,
    laughlin_sphere_flux,
    sphere_pair_projector,
    sphere_fermion_basis,
    sphere_manybody_projector,
    v1_sphere_spectrum,
    finite_size_v1_gaps,
    quasihole_zero_mode_diagnostics,
    sphere_coulomb_hamiltonian,
    v1_coulomb_spectral_flow,
    pair_amplitude_diagnostics,
    torus_lowest_band_orbitals,
    torus_projected_nn_hamiltonian,
    torus_momentum_sector_diagnostics,
    torus_embedded_ground_frame,
    nonabelian_ground_bundle_chern,
    torus_twist_spectral_flow,
    quasiparticle_charge_diagnostics,
    torus_finite_size_scaling,
    torus_shape_scan,
    generalized_exclusion_count,
    particle_entanglement_spectrum,
    pinned_quasihole_density_diagnostics,
    disordered_ground_bundle_chern,
    torus_disorder_robustness,
)


def test_01_torus_hamiltonian_is_hermitian():
    h, _ = hofstadter_torus(6, 6, 1 / 3, theta_x=0.3, theta_y=-0.4)
    assert np.allclose(h, h.conj().T)


def test_02_x_twist_is_two_pi_periodic():
    h0, _ = hofstadter_torus(6, 6, 1 / 3, theta_x=0.17)
    h1, _ = hofstadter_torus(6, 6, 1 / 3, theta_x=0.17 + TWOPI)
    assert np.allclose(h0, h1)


def test_03_y_twist_is_two_pi_periodic():
    h0, _ = hofstadter_torus(6, 6, 1 / 3, theta_y=-0.27)
    h1, _ = hofstadter_torus(6, 6, 1 / 3, theta_y=-0.27 + TWOPI)
    assert np.allclose(h0, h1)


def test_04_clean_first_magnetic_gap_is_open():
    d = clean_hall_diagnostics()
    assert d["gap1"] > 1.0


def test_05_clean_second_magnetic_gap_is_open():
    d = clean_hall_diagnostics()
    assert d["gap2"] > 1.0


def test_06_first_filled_band_has_integer_chern():
    d = clean_hall_diagnostics()
    assert d["cumulative_chern"][0] == pytest.approx(-1.0, abs=1e-10)


def test_07_two_filled_bands_have_integer_chern():
    d = clean_hall_diagnostics()
    assert d["cumulative_chern"][1] == pytest.approx(1.0, abs=1e-10)


def test_08_all_bands_have_zero_total_chern():
    d = clean_hall_diagnostics()
    assert d["cumulative_chern"][2] == pytest.approx(0.0, abs=1e-10)


def test_09_band_chern_numbers_sum_to_zero():
    d = clean_hall_diagnostics()
    assert np.sum(d["band_chern"]) == pytest.approx(0.0, abs=1e-10)


def test_10_strip_hamiltonian_is_hermitian():
    h = strip_hamiltonian(48, 0.41, 1 / 8)
    assert np.allclose(h, h.conj().T)


def test_11_strip_spectrum_is_periodic_in_ky():
    e0 = np.linalg.eigvalsh(strip_hamiltonian(48, -0.63, 1 / 8))
    e1 = np.linalg.eigvalsh(strip_hamiltonian(48, -0.63 + TWOPI, 1 / 8))
    assert np.allclose(e0, e1)


def test_12_edge_weights_are_probabilities():
    d = strip_spectrum(nky=41)
    assert np.min(d["edge_weight"]) >= -1e-12
    assert np.max(d["edge_weight"]) <= 1.0 + 1e-12


def test_13_strong_edge_states_cross_first_bulk_gap():
    d = strip_spectrum(nky=81)
    mask = (
        (d["energies"] > -3.24)
        & (d["energies"] < -2.06)
        & (d["edge_weight"] > 0.5)
    )
    assert mask.sum() > 20


def test_14_disorder_seed_is_reproducible():
    h0, w0 = hofstadter_torus(8, 8, 1 / 4, disorder_strength=2.5, seed=0)
    h1, w1 = hofstadter_torus(8, 8, 1 / 4, disorder_strength=2.5, seed=0)
    assert np.array_equal(w0, w1)
    assert np.array_equal(h0, h1)


def test_15_disorder_broadens_first_magnetic_band():
    d = disorder_plateau_diagnostics()
    assert d["disorder_first_band_width"] > 3.0 * d["clean_first_band_width"]


def test_16_ipr_bounds_hold_for_normalized_states():
    _, v = np.linalg.eigh(hofstadter_torus(8, 8, 1 / 4, disorder_strength=2.5, seed=0)[0])
    ipr = inverse_participation_ratio(v)
    assert np.min(ipr) >= 1.0 / 64.0 - 1e-12
    assert np.max(ipr) <= 1.0 + 1e-12


def test_17_localized_tail_is_more_concentrated_than_chern_carrying_state():
    d = disorder_plateau_diagnostics()
    assert d["ipr"][0] > 4.0 * d["ipr"][11]


def test_18_hall_chern_changes_at_reproducible_mobility_region():
    d = disorder_plateau_diagnostics()
    assert d["chern"][10] == pytest.approx(0.0, abs=1e-10)   # N=11
    assert d["chern"][11] == pytest.approx(-1.0, abs=1e-10)  # N=12


def test_19_integer_response_stays_fixed_while_states_are_added():
    d = disorder_plateau_diagnostics()
    # N=12,...,16: no large spectral gap is crossed, but cumulative C remains -1.
    assert np.allclose(d["chern"][11:16], -1.0, atol=1e-10)


def test_20_plateau_segment_is_not_a_clean_spectral_gap():
    d = disorder_plateau_diagnostics()
    # Consecutive levels 12--16 remain inside a broadened band; the largest spacing is small.
    e = d["energies"]
    assert np.max(np.diff(e[11:16])) < 0.15



def test_21_magnetic_bloch_hamiltonian_is_hermitian():
    h = magnetic_bloch_hamiltonian(3, 0.37, -0.81)
    assert np.allclose(h, h.conj().T)


def test_22_kubo_lowest_band_chern_is_minus_one():
    c = kubo_band_chern_numbers(3, 41)
    assert c[0] == pytest.approx(-1.0, abs=2e-6)


def test_23_kubo_middle_band_chern_is_plus_two():
    c = kubo_band_chern_numbers(3, 41)
    assert c[1] == pytest.approx(2.0, abs=2e-6)


def test_24_kubo_total_chern_closes_to_zero():
    c = kubo_band_chern_numbers(3, 41)
    assert np.sum(c) == pytest.approx(0.0, abs=2e-6)


def test_25_kubo_cumulative_response_matches_twist_chern():
    kubo = np.cumsum(kubo_band_chern_numbers(3, 41))
    twist = clean_hall_diagnostics()["cumulative_chern"]
    assert np.allclose(kubo, twist, atol=2e-6)


def test_26_streda_lowest_gap_density_slope_is_one():
    d = streda_lowest_gap_counting()
    assert d["slope"] == pytest.approx(1.0, abs=1e-12)
    assert d["intercept"] == pytest.approx(0.0, abs=1e-12)


def test_27_streda_electron_sign_matches_lowest_kubo_band():
    # For q=-e and alpha=|q|Ba^2/h, sigma_xy/(e^2/h)=-d(na^2)/dalpha.
    slope = streda_lowest_gap_counting()["slope"]
    c = kubo_band_chern_numbers(3, 41)[0]
    assert -slope == pytest.approx(c, abs=2e-6)


def test_28_wilson_loop_flux_pump_winds_once():
    d = laughlin_flux_pump(3, nkx=61, nky=91)
    assert d["winding"] == pytest.approx(-1.0, abs=2e-5)


def test_29_lll_form_factor_has_correct_limits():
    q = np.array([0.0, 1.0, 2.0])
    f = lll_form_factor(q)
    assert f[0] == pytest.approx(1.0)
    assert np.all(np.diff(f) < 0.0)
    assert np.allclose(lll_interaction_filter(q), f * f)


def test_30_coulomb_v0_and_v1_match_closed_form():
    assert coulomb_pseudopotential(0) == pytest.approx(np.sqrt(np.pi) / 2.0, abs=1e-14)
    assert coulomb_pseudopotential(1) == pytest.approx(np.sqrt(np.pi) / 4.0, abs=1e-14)


def test_31_spin_polarized_odd_pseudopotentials_decrease():
    v = coulomb_pseudopotentials(7)
    assert v[1] > v[3] > v[5] > v[7] > 0.0


def test_32_landau_level_mixing_ratio_falls_as_inverse_sqrt_B():
    k1, k4 = interaction_cyclotron_ratio(np.array([1.0, 4.0]))
    assert k1 / k4 == pytest.approx(2.0, rel=2e-12)


def test_33_laughlin_sphere_flux_has_shift_three():
    assert laughlin_sphere_flux(6, 3) == 15
    assert 6 / laughlin_sphere_flux(6, 3) == pytest.approx(0.4)


def test_34_one_added_flux_quantum_creates_quasihole_sector():
    nphi = laughlin_sphere_flux(8, 3)
    assert nphi == 21
    assert (nphi + 1) - nphi == 1

# Commit 590: projected-interaction exact-diagonalization regression tests

def test_35_sphere_pair_projector_is_idempotent():
    _, p = sphere_pair_projector(9, 1)
    assert np.allclose(p @ p, p, atol=1e-12)


def test_36_sphere_pair_projector_has_expected_rank():
    _, p = sphere_pair_projector(9, 1)
    assert np.sum(np.linalg.eigvalsh(p) > 1e-9) == 17  # 2L+1, L=8


def test_37_manybody_v1_hamiltonian_is_hermitian():
    h = sphere_manybody_projector(9, 4, 1)
    assert h.shape == (210, 210)
    assert np.allclose(h, h.T, atol=1e-13)


def test_38_laughlin_shift_has_one_zero_mode_for_three_electrons():
    e, _, nphi = v1_sphere_spectrum(3, 0)
    assert nphi == 6
    assert np.sum(np.abs(e) < 1e-10) == 1


def test_39_laughlin_shift_has_one_zero_mode_for_four_electrons():
    e, _, nphi = v1_sphere_spectrum(4, 0)
    assert nphi == 9
    assert np.sum(np.abs(e) < 1e-10) == 1


def test_40_four_electron_v1_gap_matches_reference():
    e, _, _ = v1_sphere_spectrum(4, 0)
    assert e[1] - e[0] == pytest.approx(0.680604246854534, abs=2e-12)


def test_41_finite_size_v1_gaps_are_positive():
    d = finite_size_v1_gaps()
    assert np.all(d["gap"] > 0.5)
    assert np.all(d["zero_modes"] == 1)


def test_42_one_flux_quasihole_sector_has_five_zero_modes_for_four_electrons():
    d = quasihole_zero_mode_diagnostics()
    assert d["quasihole_zero_modes"][-1] == 5


def test_43_quasihole_zero_mode_count_grows_after_one_flux():
    d = quasihole_zero_mode_diagnostics()
    assert np.all(d["quasihole_zero_modes"] > d["base_zero_modes"])
    assert np.array_equal(d["quasihole_zero_modes"], d["ne"] + 1)


def test_44_quasihole_sector_remains_gapped_above_zero_modes():
    d = quasihole_zero_mode_diagnostics()
    assert np.all(d["quasihole_gap"] > 0.6)


def test_45_laughlin_pair_amplitude_eliminates_m1():
    d = pair_amplitude_diagnostics()
    assert abs(d["laughlin"][0]) < 1e-12


def test_46_pair_amplitudes_obey_exact_pair_count_sum_rule():
    d = pair_amplitude_diagnostics()
    assert d["laughlin_sum"] == pytest.approx(6.0, abs=1e-12)
    assert d["compact_sum"] == pytest.approx(6.0, abs=1e-12)


def test_47_compact_slater_has_large_short_range_pair_weight():
    d = pair_amplitude_diagnostics()
    assert d["compact_slater"][0] > 3.0


def test_48_projected_coulomb_hamiltonian_is_hermitian():
    h = sphere_coulomb_hamiltonian(9, 4)
    assert np.allclose(h, h.T, atol=1e-13)


def test_49_v1_to_coulomb_spectral_flow_keeps_gap_open():
    d = v1_coulomb_spectral_flow()
    assert d["min_gap"] > 0.09
    assert d["gap"][-1] == pytest.approx(0.0928995814001248, abs=2e-12)


def test_50_v1_to_coulomb_ground_state_overlap_remains_large():
    d = v1_coulomb_spectral_flow()
    assert d["endpoint_overlap_sq"] > 0.9999


# Commit 591: torus momentum sectors, many-body ground bundle, fractional charge

def test_51_torus_lowest_band_orbitals_are_orthonormal():
    p, labels = torus_lowest_band_orbitals(3, 1, 9)
    assert p.shape == (27, 9)
    assert len(labels) == 9
    assert np.allclose(p.conj().T @ p, np.eye(9), atol=2e-13)


def test_52_projected_torus_manybody_hamiltonian_is_hermitian():
    h, _, _, states = torus_projected_nn_hamiltonian()
    assert h.shape == (84, 84)
    assert len(states) == 84
    assert np.allclose(h, h.conj().T, atol=2e-13)


def test_53_zero_twist_hamiltonian_respects_manybody_momentum_sectors():
    d = torus_momentum_sector_diagnostics()
    assert d["off_block_max"] < 1e-12


def test_54_fractional_torus_has_three_low_energy_ground_sectors():
    d = torus_momentum_sector_diagnostics()
    assert sorted(d["ground_sectors"]) == [(0, 0), (0, 3), (0, 6)]


def test_55_ground_multiplet_is_separated_from_fourth_state():
    d = torus_momentum_sector_diagnostics()
    assert d["gap_above_multiplet"] > 0.025
    assert d["gap_above_multiplet"] > 5.0 * d["multiplet_splitting"]


def test_56_embedded_ground_frame_is_orthonormal():
    _, g = torus_embedded_ground_frame(0.37, -0.52)
    assert g.shape == (2925, 3)
    assert np.allclose(g.conj().T @ g, np.eye(3), atol=2e-12)


def test_57_nonabelian_ground_bundle_chern_is_minus_one():
    d = nonabelian_ground_bundle_chern(5)
    assert d["chern"] == pytest.approx(-1.0, abs=1e-10)


def test_58_nonabelian_wilson_loop_has_unit_winding():
    d = nonabelian_ground_bundle_chern(5)
    assert d["wilson_winding"] == pytest.approx(-1.0, abs=1e-10)


def test_59_ground_bundle_stays_isolated_over_twist_torus():
    d = nonabelian_ground_bundle_chern(5)
    assert d["minimum_gap"] > 0.026


def test_60_nonabelian_link_overlaps_stay_nonsingular():
    d = nonabelian_ground_bundle_chern(5)
    assert d["minimum_overlap_det"] > 0.3


def test_61_twist_spectral_flow_closes_after_two_pi():
    d = torus_twist_spectral_flow(13)
    assert d["cycle_closure"] < 1e-12


def test_62_twist_flow_keeps_direct_gap_above_ground_multiplet_open():
    d = torus_twist_spectral_flow(13)
    assert d["minimum_direct_gap"] > 0.027


def test_63_flux_counting_gives_one_third_quasihole_charge():
    d = quasiparticle_charge_diagnostics()
    assert d["quasihole_charge_over_e"] == pytest.approx(1.0 / 3.0, abs=1e-15)


def test_64_chern_per_ground_state_gives_fractional_pumped_charge():
    d = quasiparticle_charge_diagnostics(ground_bundle_chern=-1.0, ground_multiplet=3)
    assert d["chern_per_ground_state"] == pytest.approx(-1.0 / 3.0, abs=1e-15)
    assert d["pumped_charge_magnitude_over_e"] == pytest.approx(1.0 / 3.0, abs=1e-15)


def test_65_flux_counting_and_chern_charge_diagnostics_agree():
    d = quasiparticle_charge_diagnostics(ground_bundle_chern=-1.0, ground_multiplet=3)
    assert d["consistency_error"] < 1e-15


def test_66_torus_projected_hamiltonian_is_periodic_in_boundary_twist():
    h0, _, _, _ = torus_projected_nn_hamiltonian(theta_x=0.23, theta_y=-0.41)
    h1, _, _, _ = torus_projected_nn_hamiltonian(theta_x=0.23 + TWOPI, theta_y=-0.41)
    # The projected-band basis is cyclically relabeled after a 2pi twist, so
    # spectra rather than raw matrix entries are the gauge-invariant closure test.
    assert np.allclose(np.linalg.eigvalsh(h0), np.linalg.eigvalsh(h1), atol=2e-12)


# Commit 592: finite-size/shape scaling, entanglement counting, local charge,
# and disorder robustness of the fractional ground-state bundle


def test_67_torus_finite_size_sequence_has_expected_hilbert_dimensions():
    d = torus_finite_size_scaling()
    assert np.array_equal(d["hilbert_dim"], [15, 84, 495])


def test_68_torus_finite_size_sequence_keeps_positive_gap_above_triplet():
    d = torus_finite_size_scaling()
    assert np.all(d["gap"] > 0.028)


def test_69_compact_ne4_shape_has_robust_triplet_gap():
    d = torus_shape_scan()
    i = d["geometry"].index((3, 4))
    assert d["gap"][i] > 0.063
    assert d["gap_to_split_ratio"][i] > 35.0


def test_70_thin_ne4_shape_exposes_finite_size_gap_collapse():
    d = torus_shape_scan()
    i = d["geometry"].index((6, 2))
    assert d["gap"][i] < 1.0e-4
    assert d["gap_to_split_ratio"][i] < 1.0


def test_71_generalized_13_exclusion_count_is_42_for_two_of_twelve():
    assert generalized_exclusion_count(12, 2, 3) == 42


def test_72_particle_entanglement_density_matrix_is_normalized():
    d = particle_entanglement_spectrum()
    assert d["rho_trace"] == pytest.approx(1.0, abs=1e-12)


def test_73_particle_entanglement_low_count_matches_13_exclusion_counting():
    d = particle_entanglement_spectrum()
    assert d["low_level_count"] == d["admissible_13_count"] == 42


def test_74_particle_entanglement_gap_is_large_in_compact_ne4_geometry():
    d = particle_entanglement_spectrum()
    assert d["entanglement_gap"] > 4.0


def test_75_one_added_flux_has_ten_state_quasihole_manifold():
    d = pinned_quasihole_density_diagnostics()
    assert d["nphi"] == 10
    assert d["quasihole_manifold"] == 10


def test_76_quasihole_manifold_is_gapped_from_higher_states():
    d = pinned_quasihole_density_diagnostics()
    assert d["quasihole_gap"] > 0.031


def test_77_weak_pin_localizes_one_third_charge_in_first_shell():
    d = pinned_quasihole_density_diagnostics()
    assert d["first_shell_charge_over_e"] == pytest.approx(1.0 / 3.0, abs=0.005)


def test_78_pinned_density_redistribution_conserves_total_particle_number():
    d = pinned_quasihole_density_diagnostics()
    assert d["total_deficit"] == pytest.approx(0.0, abs=1e-12)


def test_79_disordered_ground_bundle_chern_stays_minus_one_at_moderate_disorder():
    d = disordered_ground_bundle_chern(0.04, seed=7, ntheta=5)
    assert d["chern"] == pytest.approx(-1.0, abs=1e-10)


def test_80_disordered_ground_bundle_keeps_open_direct_gap_at_moderate_disorder():
    d = disordered_ground_bundle_chern(0.04, seed=7, ntheta=5)
    assert d["minimum_gap"] > 0.011


def test_81_disorder_scan_keeps_quantized_bundle_chern_through_stress_window():
    d = torus_disorder_robustness()
    assert np.allclose(d["chern"], -1.0, atol=1e-10)


def test_82_disorder_degrades_ground_manifold_isolation_before_chern_changes():
    d = torus_disorder_robustness()
    assert d["isolation_ratio"][0] > 2.0
    assert d["isolation_ratio"][-1] < 0.5

