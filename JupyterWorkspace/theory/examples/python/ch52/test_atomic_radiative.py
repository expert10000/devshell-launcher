import math
import numpy as np

from atomic_radiative import (
    C,
    E_CHARGE,
    H,
    M_E,
    MU_B_OVER_H_HZ_T,
    absorption_oscillator_strength,
    angular_momentum_matrices,
    branching_fractions,
    e1_rate_from_oscillator_strength,
    e1_spontaneous_rate,
    einstein_b_from_a_angular_density,
    hyperfine_zeeman_spectrum_hz,
    natural_linewidth_hz,
    radiative_lifetime_s,
    trk_captured_fraction,
    two_level_field_map,
)


def test_e1_rate_cubic_frequency_scaling():
    d = E_CHARGE * 5.0e-11
    a1 = e1_spontaneous_rate(1.0e15, d, J_upper=1)
    a2 = e1_spontaneous_rate(2.0e15, d, J_upper=1)
    assert np.isclose(a2 / a1, 8.0)


def test_oscillator_strength_linear_frequency_scaling():
    d = E_CHARGE * 5.0e-11
    f1 = absorption_oscillator_strength(1.0e15, d, J_lower=0)
    f2 = absorption_oscillator_strength(2.0e15, d, J_lower=0)
    assert np.isclose(f2 / f1, 2.0)


def test_A_f_conversion_matches_same_reduced_dipole():
    omega = 2.4e15
    d = E_CHARGE * 4.2e-11
    f = absorption_oscillator_strength(omega, d, J_lower=0)
    a_direct = e1_spontaneous_rate(omega, d, J_upper=1)
    a_from_f = e1_rate_from_oscillator_strength(omega, f, J_lower=0, J_upper=1)
    assert np.isclose(a_direct, a_from_f, rtol=2e-12)


def test_einstein_degeneracy_relation():
    B_ul, B_lu = einstein_b_from_a_angular_density(2.0e7, 3.0e15, g_lower=2, g_upper=4)
    assert np.isclose(2.0 * B_lu, 4.0 * B_ul)


def test_branching_fractions_sum_to_one():
    b = branching_fractions([2.0e7, 3.0e7, 5.0e7])
    assert np.isclose(np.sum(b), 1.0)
    assert np.allclose(b, [0.2, 0.3, 0.5])


def test_lifetime_is_inverse_total_rate():
    assert np.isclose(radiative_lifetime_s([2.0e7, 3.0e7, 5.0e7]), 1.0e-8)


def test_natural_linewidth_relation():
    rate = 4.0e7
    assert np.isclose(natural_linewidth_hz(rate), rate / (2.0 * math.pi))


def test_trk_fraction_and_deficit():
    captured, deficit = trk_captured_fraction([0.55, 0.25, 0.12], electron_count=1)
    assert np.isclose(captured, 0.92)
    assert np.isclose(deficit, 0.08)


def test_angular_momentum_commutator():
    jx, jy, jz = angular_momentum_matrices(1.5)
    assert np.allclose(jx @ jy - jy @ jx, 1j * jz)


def test_hyperfine_zeeman_zero_field_recovers_expected_multiplets():
    A = 100.0e6
    e = hyperfine_zeeman_spectrum_hz(I=1.5, J=0.5, A_hfs_hz=A, B_tesla=0.0, g_J=2.0)
    expected = np.array([-1.25 * A] * 3 + [0.75 * A] * 5)
    assert np.allclose(e, expected)


def test_high_field_trace_is_field_independent_without_nuclear_term():
    e0 = hyperfine_zeeman_spectrum_hz(1.5, 0.5, 100e6, 0.0, 2.0)
    e1 = hyperfine_zeeman_spectrum_hz(1.5, 0.5, 100e6, 0.2, 2.0)
    assert np.isclose(np.sum(e0), np.sum(e1), atol=1e-5)


def test_two_level_field_minimum_gap_is_two_coupling():
    fields = np.linspace(-1.0, 1.0, 401)
    energies, weights = two_level_field_map(fields, 0.0, 0.0, 1.0, -1.0, 0.08)
    gaps = energies[:, 1] - energies[:, 0]
    assert np.isclose(np.min(gaps), 0.16)
    center = len(fields) // 2
    assert np.allclose(weights[center], [0.5, 0.5])
