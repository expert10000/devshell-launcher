import numpy as np
import pytest

from periodic_band_lab import (
    cosine_plane_wave_hamiltonian,
    cutoff_diagnostic,
    effective_mass_ratio_from_band,
    first_zone_gap,
    fit_first_plane_wave_band_to_tight_binding,
    fit_nearest_neighbour_tight_binding,
    plane_wave_bands,
    plane_wave_eigenvalues,
    plane_wave_indices,
    tight_binding_band,
    tight_binding_bandwidth,
    tight_binding_effective_mass_scale,
)


def test_plane_wave_indices_are_symmetric():
    assert np.array_equal(plane_wave_indices(2), np.array([-2, -1, 0, 1, 2]))


def test_cutoff_zero_has_one_basis_state():
    assert plane_wave_indices(0).size == 1


def test_negative_cutoff_rejected():
    with pytest.raises(ValueError):
        plane_wave_indices(-1)


def test_noninteger_cutoff_rejected():
    with pytest.raises(ValueError):
        plane_wave_indices(1.5)


def test_plane_wave_hamiltonian_dimension():
    assert cosine_plane_wave_hamiltonian(0.2, 0.1, 3).shape == (7, 7)


def test_plane_wave_hamiltonian_is_symmetric():
    h = cosine_plane_wave_hamiltonian(0.37, 0.23, 4, v2=-0.04)
    assert np.allclose(h, h.T)


def test_zero_potential_matches_folded_free_spectrum():
    k = 0.31
    n = plane_wave_indices(3)
    expected = np.sort((k + 2.0 * n) ** 2)
    got = plane_wave_eigenvalues(k, 0.0, 3)
    assert np.allclose(got, expected)


def test_first_band_time_reversal_symmetry():
    ep = plane_wave_eigenvalues(0.43, 0.25, 4, 3)
    em = plane_wave_eigenvalues(-0.43, 0.25, 4, 3)
    assert np.allclose(ep, em, atol=1e-12)


def test_zone_endpoints_have_same_spectrum():
    ep = plane_wave_eigenvalues(+1.0, 0.2, 5, 4)
    em = plane_wave_eigenvalues(-1.0, 0.2, 5, 4)
    assert np.allclose(ep, em, atol=1e-12)


def test_zero_potential_zone_boundary_gap_is_zero():
    assert first_zone_gap(0.0, 3) == pytest.approx(0.0, abs=1e-13)


def test_weak_potential_gap_matches_two_state_result():
    v = 0.05
    assert first_zone_gap(v, 5) == pytest.approx(2.0 * v, rel=8e-5)


def test_gap_is_even_in_fourier_amplitude():
    assert first_zone_gap(+0.17, 5) == pytest.approx(first_zone_gap(-0.17, 5), rel=1e-12)


def test_gap_grows_between_weak_amplitudes():
    assert first_zone_gap(0.2, 5) > first_zone_gap(0.1, 5)


def test_plane_wave_bands_shape():
    b = plane_wave_bands(np.linspace(-1, 1, 9), 0.2, 3, 3)
    assert b.shape == (9, 3)


def test_plane_wave_bands_reject_empty_grid():
    with pytest.raises(ValueError):
        plane_wave_bands([], 0.2, 3, 2)


def test_cutoff_convergence_improves_for_cosine_lattice():
    d1 = cutoff_diagnostic(0.4, 1, num_bands=3, grid_points=41)
    d2 = cutoff_diagnostic(0.4, 2, num_bands=3, grid_points=41)
    assert d2.max_band_error < d1.max_band_error


def test_cutoff_three_is_quantitatively_converged_for_reference_case():
    d = cutoff_diagnostic(0.4, 3, num_bands=3, grid_points=41)
    assert d.max_band_error < 2e-6


def test_free_particle_effective_mass_ratio_is_one():
    assert effective_mass_ratio_from_band(0.0, 3, dkappa=2e-3) == pytest.approx(1.0, rel=2e-8)


def test_weak_lattice_renormalizes_first_band_mass():
    mstar = effective_mass_ratio_from_band(0.3, 5, dkappa=2e-3)
    assert mstar > 1.0


def test_tight_binding_band_is_even():
    assert tight_binding_band(0.37, 0.4) == pytest.approx(tight_binding_band(-0.37, 0.4))


def test_tight_binding_bandwidth_is_four_t():
    assert tight_binding_bandwidth(-0.7) == pytest.approx(2.8)


def test_tight_binding_endpoints_for_positive_hopping():
    t = 0.3
    assert tight_binding_band(0.0, t) == pytest.approx(-2.0 * t)
    assert tight_binding_band(1.0, t) == pytest.approx(+2.0 * t)


def test_exact_tight_binding_fit_recovers_parameters():
    k = np.linspace(-1.0, 1.0, 31)
    e = tight_binding_band(k, 0.27, onsite=1.3)
    fit = fit_nearest_neighbour_tight_binding(k, e)
    assert fit.onsite == pytest.approx(1.3, abs=1e-12)
    assert fit.hopping == pytest.approx(0.27, abs=1e-12)
    assert fit.rms_residual < 1e-12


def test_tight_binding_effective_mass_scale_formula():
    t = 0.2
    assert tight_binding_effective_mass_scale(t) == pytest.approx(1.0 / (np.pi**2 * t))


def test_plane_wave_first_band_has_finite_tight_binding_fit():
    fit = fit_first_plane_wave_band_to_tight_binding(0.4, 4, grid_points=41)
    assert np.isfinite(fit.onsite)
    assert fit.hopping > 0.0
    assert 0.0 < fit.rms_residual < 0.2
