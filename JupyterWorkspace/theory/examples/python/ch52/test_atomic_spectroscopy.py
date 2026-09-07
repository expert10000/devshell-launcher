import numpy as np
import pytest

from atomic_spectroscopy import (
    SpectroscopicLine,
    allowed_total_j,
    ci_gap,
    ci_two_configuration,
    electric_dipole_allowed,
    fit_ls_spin_orbit,
    hyperfine_energy,
    hyperfine_multiplet,
    isotope_shift_model,
    lande_g_factor,
    ls_spin_orbit_energy,
    ls_term_energies,
    normal_mass_isotope_shift,
    reduced_mass_scale,
    statistical_centroid,
    transition_wavenumber,
    wavenumber_to_wavelength_nm,
)


def test_angular_momentum_addition_integer():
    assert np.array_equal(allowed_total_j(1, 1), np.array([0.0, 1.0, 2.0]))


def test_angular_momentum_addition_half_integer():
    assert np.array_equal(allowed_total_j(1.5, 0.5), np.array([1.0, 2.0]))


def test_ci_eigenvalues_at_degeneracy():
    vals, _ = ci_two_configuration(0.0, 0.0, 0.2)
    assert np.allclose(vals, [-0.2, 0.2])


def test_ci_minimum_gap_is_two_v():
    assert np.isclose(ci_gap(1.5, 1.5, 0.17), 0.34)


def test_ci_trace_is_preserved():
    vals, _ = ci_two_configuration(-0.7, 1.2, 0.3)
    assert np.isclose(np.sum(vals), 0.5)


def test_triplet_p_lande_interval_rule():
    js, es = ls_term_energies(2.0, L=1, S=1)
    assert np.array_equal(js, [0.0, 1.0, 2.0])
    assert np.allclose(np.diff(es), [2.0, 4.0])


def test_ls_weighted_centroid_is_input_centroid():
    js, es = ls_term_energies(1.7, L=2, S=1, centroid=123.4)
    assert np.isclose(statistical_centroid(js, es), 123.4)


def test_ls_fit_recovers_A_and_centroid():
    js, es = ls_term_energies(3.25, L=2, S=1, centroid=15000.0)
    fit = fit_ls_spin_orbit(js, es, L=2, S=1)
    assert np.isclose(fit["A"], 3.25)
    assert np.isclose(fit["centroid"], 15000.0)
    assert fit["rms"] < 1e-9


def test_lande_g_for_s_state_is_spin_g():
    g = lande_g_factor(L=0, S=0.5, J=0.5)
    assert np.isclose(g, 2.00231930436)


def test_j_zero_lande_g_defined_zero():
    assert lande_g_factor(1, 1, 0) == 0.0


def test_hyperfine_s12_interval():
    fs, es = hyperfine_multiplet(A=100.0, I=1.5, J=0.5)
    assert np.array_equal(fs, [1.0, 2.0])
    assert np.isclose(es[1] - es[0], 200.0)


def test_hyperfine_quadrupole_term_is_finite():
    e = hyperfine_energy(A=1.0, B=0.2, I=1.5, J=1.5, F=2)
    assert np.isfinite(e)


def test_reduced_mass_scale_increases_with_nuclear_mass():
    assert reduced_mass_scale(2.0) > reduced_mass_scale(1.0)
    assert reduced_mass_scale(100.0) < 1.0


def test_normal_mass_heavier_isotope_blueshifts():
    assert normal_mass_isotope_shift(1.0e15, 1.0, 2.0) > 0.0


def test_isotope_shift_linear_model():
    y = isotope_shift_model(np.array([0.1, 0.2]), np.array([0.3, -0.1]), 4.0, 2.0)
    assert np.allclose(y, [1.0, 0.6])


def test_wavenumber_wavelength_round_trip_value():
    assert np.isclose(wavenumber_to_wavelength_nm(20000.0), 500.0)
    assert np.isclose(transition_wavenumber(25000.0, 5000.0), 20000.0)


def test_e1_selection_rule():
    assert electric_dipole_allowed(1, 2, True)
    assert not electric_dipole_allowed(0, 0, True)
    assert not electric_dipole_allowed(1, 1, False)


def test_spectroscopic_line_properties():
    line = SpectroscopicLine(lower_cm1=5000.0, upper_cm1=25000.0)
    assert np.isclose(line.wavenumber_cm1, 20000.0)
    assert np.isclose(line.wavelength_nm, 500.0)


def test_invalid_total_j_rejected():
    with pytest.raises(ValueError):
        ls_spin_orbit_energy(1.0, L=1, S=0.5, J=3.0)


def test_negative_wavenumber_rejected():
    with pytest.raises(ValueError):
        wavenumber_to_wavelength_nm(-1.0)
