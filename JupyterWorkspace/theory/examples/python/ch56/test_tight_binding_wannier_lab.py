import numpy as np
import pytest

from tight_binding_wannier_lab import (
    bloch_matrix,
    dimerized_bands,
    dimerized_bloch_hamiltonian,
    dimerized_chain_hamiltonian,
    dimerized_direct_gap,
    fit_scalar_hopping_range,
    hopping_coefficients_from_sampled_band,
    hopping_truncation_error,
    hopping_truncation_error_bound,
    open_nn_analytic_spectrum,
    periodic_dimerized_bloch_spectrum,
    periodic_scalar_bloch_spectrum,
    reconstruct_sampled_band_from_hoppings,
    sampled_periodic_momenta,
    scalar_bloch_band,
    scalar_chain_hamiltonian,
    wannier_coefficients_from_gauge,
    wannier_ipr,
    wannier_peak_cell,
)


def test_scalar_nn_band_center_and_edge():
    assert scalar_bloch_band(0.0, 0.3, {1: 0.7}) == pytest.approx(-1.1)
    assert scalar_bloch_band(np.pi, 0.3, {1: 0.7}) == pytest.approx(1.7)


def test_scalar_multirange_band_is_even():
    hs = {1: 0.7, 2: 0.12, 3: 0.03}
    assert scalar_bloch_band(0.43, 0.2, hs) == pytest.approx(scalar_bloch_band(-0.43, 0.2, hs))


def test_scalar_chain_dimension():
    assert scalar_chain_hamiltonian(12, hoppings={1: 0.7}).shape == (12, 12)


def test_scalar_open_chain_is_hermitian():
    h = scalar_chain_hamiltonian(11, 0.1, {1: 0.7, 2: -0.08})
    assert np.allclose(h, h.T)


def test_scalar_periodic_spectrum_matches_sampled_bloch_dispersion():
    n = 14
    hs = {1: 0.7, 2: 0.12}
    real_space = np.linalg.eigvalsh(scalar_chain_hamiltonian(n, 0.3, hs, periodic=True))
    bloch = periodic_scalar_bloch_spectrum(n, 0.3, hs)
    assert np.allclose(real_space, bloch, atol=1e-12)


def test_open_nn_chain_matches_exact_sine_quantization():
    n = 13
    got = np.linalg.eigvalsh(scalar_chain_hamiltonian(n, 0.3, {1: 0.7}, periodic=False))
    expected = open_nn_analytic_spectrum(n, 0.3, 0.7)
    assert np.allclose(got, expected, atol=1e-12)


def test_hopping_truncation_bound_reference_values():
    hs = {1: 0.7, 2: 0.12, 3: 0.03}
    assert hopping_truncation_error_bound(hs, 1) == pytest.approx(0.30)
    assert hopping_truncation_error_bound(hs, 2) == pytest.approx(0.06)


def test_hopping_truncation_actual_error_saturates_bound_for_positive_reference_hoppings():
    hs = {1: 0.7, 2: 0.12, 3: 0.03}
    assert hopping_truncation_error(hs, 1) == pytest.approx(0.30, abs=1e-12)
    assert hopping_truncation_error(hs, 2) == pytest.approx(0.06, abs=1e-12)


def test_exact_range_three_fit_recovers_reference_hoppings():
    q = np.linspace(-np.pi, np.pi, 101)
    e = scalar_bloch_band(q, 0.3, {1: 0.7, 2: 0.12, 3: 0.03})
    fit = fit_scalar_hopping_range(q, e, 3)
    assert fit.onsite == pytest.approx(0.3, abs=1e-12)
    assert fit.hoppings == pytest.approx((0.7, 0.12, 0.03), abs=1e-12)
    assert fit.rms_residual < 1e-12


def test_hopping_fit_rejects_too_few_samples():
    with pytest.raises(ValueError):
        fit_scalar_hopping_range([0.0, 1.0, 2.0], [0.0, 1.0, 2.0], 2)


def test_sampled_band_fourier_recovers_onsite():
    n = 32
    q = sampled_periodic_momenta(n)
    e = scalar_bloch_band(q, 0.3, {1: 0.7})
    h = hopping_coefficients_from_sampled_band(e)
    assert h[0].real == pytest.approx(0.3, abs=1e-12)
    assert abs(h[0].imag) < 1e-12


def test_sampled_band_fourier_recovers_nearest_neighbor_matrix_elements():
    n = 32
    q = sampled_periodic_momenta(n)
    e = scalar_bloch_band(q, 0.3, {1: 0.7})
    h = hopping_coefficients_from_sampled_band(e)
    assert h[1].real == pytest.approx(-0.7, abs=1e-12)
    assert h[-1].real == pytest.approx(-0.7, abs=1e-12)


def test_sampled_band_fourier_round_trip():
    n = 24
    q = sampled_periodic_momenta(n)
    e = scalar_bloch_band(q, -0.2, {1: 0.5, 2: -0.09, 3: 0.02})
    h = hopping_coefficients_from_sampled_band(e)
    back = reconstruct_sampled_band_from_hoppings(h)
    assert np.allclose(back.real, e, atol=1e-12)
    assert np.max(np.abs(back.imag)) < 1e-12


def test_zero_gauge_wannier_is_one_cell_localized():
    c = wannier_coefficients_from_gauge(np.zeros(16))
    assert wannier_peak_cell(c) == 0
    assert wannier_ipr(c) == pytest.approx(1.0, abs=1e-12)


def test_linear_gauge_shifts_wannier_center_by_integer_cells():
    n = 16
    q = sampled_periodic_momenta(n)
    c = wannier_coefficients_from_gauge(-3.0 * q)
    assert wannier_peak_cell(c) == 3
    assert wannier_ipr(c) == pytest.approx(1.0, abs=1e-12)


def test_nonlinear_gauge_delocalizes_discrete_wannier_state():
    n = 32
    q = sampled_periodic_momenta(n)
    c = wannier_coefficients_from_gauge(0.8 * np.sin(q))
    assert 0.0 < wannier_ipr(c) < 1.0


def test_wannier_transform_preserves_norm():
    n = 27
    q = sampled_periodic_momenta(n)
    c = wannier_coefficients_from_gauge(0.4 * np.sin(q) + 0.2 * np.sin(2 * q))
    assert np.sum(np.abs(c) ** 2) == pytest.approx(1.0, abs=1e-12)


def test_general_bloch_matrix_is_hermitian():
    h0 = np.array([[0.2, 0.1j], [-0.1j, -0.4]])
    t1 = np.array([[-0.5, 0.08], [0.02j, -0.2]])
    h = bloch_matrix(0.37, h0, {1: t1})
    assert np.allclose(h, h.conj().T, atol=1e-12)


def test_general_bloch_matrix_real_model_has_time_reversal_symmetric_spectrum():
    h0 = np.array([[0.2, 0.05], [0.05, -0.4]])
    t1 = np.array([[-0.5, 0.08], [0.02, -0.2]])
    ep = np.linalg.eigvalsh(bloch_matrix(0.63, h0, {1: t1}))
    em = np.linalg.eigvalsh(bloch_matrix(-0.63, h0, {1: t1}))
    assert np.allclose(ep, em, atol=1e-12)


def test_general_bloch_matrix_rejects_shape_mismatch():
    with pytest.raises(ValueError):
        bloch_matrix(0.2, np.eye(2), {1: np.eye(3)})


def test_dimerized_bloch_hamiltonian_is_hermitian():
    h = dimerized_bloch_hamiltonian(0.71, 0.6, 1.0, delta=0.2)
    assert np.allclose(h, h.conj().T, atol=1e-12)


def test_dimerized_bands_match_closed_form():
    q = 0.37
    t1, t2, d, mean = 0.6, 1.0, 0.2, -0.1
    rad = np.sqrt(d * d + t1 * t1 + t2 * t2 + 2 * t1 * t2 * np.cos(q))
    expected = np.array([mean - rad, mean + rad])
    got = dimerized_bands(q, t1, t2, d, mean)
    assert np.allclose(got, expected, atol=1e-12)


def test_dimerized_direct_gap_reference_is_point_eight():
    assert dimerized_direct_gap(0.6, 1.0, 0.0) == pytest.approx(0.8)


def test_staggered_onsite_term_enlarges_dimerized_direct_gap():
    expected = 2.0 * np.sqrt(0.2**2 + 0.4**2)
    assert dimerized_direct_gap(0.6, 1.0, 0.2) == pytest.approx(expected)


def test_periodic_dimerized_finite_spectrum_matches_bloch_eigenvalues():
    n = 11
    h = dimerized_chain_hamiltonian(n, 0.6, 1.0, delta=0.2, mean_onsite=0.1, periodic=True)
    real_space = np.linalg.eigvalsh(h)
    bloch = periodic_dimerized_bloch_spectrum(n, 0.6, 1.0, delta=0.2, mean_onsite=0.1)
    assert np.allclose(real_space, bloch, atol=1e-12)


def test_open_dimerized_chain_has_two_orbitals_per_cell():
    assert dimerized_chain_hamiltonian(9, 0.6, 1.0).shape == (18, 18)


def test_uniform_dimerized_chain_closes_gap_when_delta_zero():
    assert dimerized_direct_gap(0.8, 0.8, 0.0) == pytest.approx(0.0)


def test_dimerized_band_spectrum_is_even_in_q():
    ep = dimerized_bands(0.52, 0.6, 1.0, delta=0.17)
    em = dimerized_bands(-0.52, 0.6, 1.0, delta=0.17)
    assert np.allclose(ep, em, atol=1e-12)


def test_one_orbital_block_bloch_matrix_agrees_with_scalar_band():
    q = 0.44
    h = bloch_matrix(q, np.array([[0.3]]), {1: np.array([[-0.7]])})
    assert h[0, 0].real == pytest.approx(scalar_bloch_band(q, 0.3, {1: 0.7}))


def test_hopping_range_fit_residual_falls_to_zero_at_true_range():
    q = np.linspace(-np.pi, np.pi, 101)
    e = scalar_bloch_band(q, 0.3, {1: 0.7, 2: 0.12, 3: 0.03})
    f1 = fit_scalar_hopping_range(q, e, 1)
    f2 = fit_scalar_hopping_range(q, e, 2)
    f3 = fit_scalar_hopping_range(q, e, 3)
    assert f2.rms_residual < f1.rms_residual
    assert f3.rms_residual < f2.rms_residual
    assert f3.rms_residual < 1e-12


def test_hopping_truncation_converges_monotonically_for_reference_model():
    hs = {1: 0.7, 2: 0.12, 3: 0.03}
    e0 = hopping_truncation_error(hs, 0)
    e1 = hopping_truncation_error(hs, 1)
    e2 = hopping_truncation_error(hs, 2)
    e3 = hopping_truncation_error(hs, 3)
    assert e0 > e1 > e2 > e3 - 1e-14
    assert e3 < 1e-12


def test_periodic_scalar_trace_is_n_times_onsite():
    n = 15
    h = scalar_chain_hamiltonian(n, onsite=0.3, hoppings={1: 0.7, 2: 0.12}, periodic=True)
    assert np.trace(h) == pytest.approx(n * 0.3)


def test_chiral_dimerized_spectrum_is_symmetric_about_zero():
    h = dimerized_chain_hamiltonian(10, 0.6, 1.0, delta=0.0, mean_onsite=0.0, periodic=False)
    e = np.linalg.eigvalsh(h)
    assert np.allclose(e, -e[::-1], atol=1e-12)
