import numpy as np
import pytest

from atomic_metrology import (
    ATOMIC_FIELD_V_M,
    ac_stark_shift_hartree,
    ac_stark_shift_hz,
    bbr_clock_shift_hz,
    blackbody_mean_square_field_v2_m2,
    core_polarization_potential_au,
    differential_polarizability_dynamic_au,
    effective_quantum_number,
    find_magic_photon_energy_au,
    fractional_frequency_shift,
    intensity_to_field_amplitude_v_m,
    quality_factor,
    quantum_defect_binding_hartree,
    ritz_quantum_defect,
    scalar_polarizability_dynamic_au,
    scalar_polarizability_static_au,
    uncertainty_quadrature,
)

LOWER = ([0.080, 0.135, 0.210], [2.20, 1.10, 0.55], 0.0)
UPPER = ([0.065, 0.160, 0.235], [1.45, 2.00, 0.45], 0.0)
MAGIC_BRACKET = (0.050, 0.055)


def test_effective_quantum_number():
    assert np.isclose(effective_quantum_number(10, 1.25), 8.75)


def test_quantum_defect_increases_binding_magnitude():
    e0 = quantum_defect_binding_hartree(10, 0.0)
    ed = quantum_defect_binding_hartree(10, 1.0)
    assert ed < e0 < 0.0


def test_rydberg_limit_approaches_threshold():
    assert abs(quantum_defect_binding_hartree(50, 1.0)) < abs(quantum_defect_binding_hartree(10, 1.0))


def test_ritz_defect_tends_to_delta0():
    assert abs(ritz_quantum_defect(1000, 1.3, 0.2, -0.1) - 1.3) < 1e-6


def test_core_polarization_recovers_long_range_tail():
    r = 30.0
    alpha = 4.0
    v = float(core_polarization_potential_au(r, alpha, 1.5))
    expected = -alpha / (2.0 * r**4)
    assert np.isclose(v, expected, rtol=1e-10)


def test_core_polarization_is_regularized_near_origin():
    v = float(core_polarization_potential_au(1e-4, 4.0, 1.5))
    assert np.isfinite(v)
    assert abs(v) < 1e-6


def test_dynamic_zero_equals_static():
    de, d, j = LOWER
    a0 = scalar_polarizability_static_au(de, d, j)
    ad = scalar_polarizability_dynamic_au(0.0, de, d, j)
    assert np.isclose(a0, ad, rtol=1e-14, atol=1e-14)


def test_dynamic_polarizability_rejects_resonance():
    de, d, j = LOWER
    with pytest.raises(ValueError):
        scalar_polarizability_dynamic_au(de[0], de, d, j)


def test_magic_root_closes_differential_polarizability():
    root = find_magic_photon_energy_au(MAGIC_BRACKET, LOWER, UPPER)
    assert MAGIC_BRACKET[0] < root < MAGIC_BRACKET[1]
    assert abs(differential_polarizability_dynamic_au(root, LOWER, UPPER)) < 1e-9


def test_ac_stark_shift_scales_with_field_squared():
    s1 = ac_stark_shift_hartree(100.0, 1e-5)
    s2 = ac_stark_shift_hartree(100.0, 2e-5)
    assert np.isclose(s2 / s1, 4.0)


def test_zero_polarizability_has_zero_stark_shift():
    assert ac_stark_shift_hz(0.0, 2.0e4) == 0.0


def test_intensity_field_round_trip_definition():
    intensity = 2.5e6
    e0 = intensity_to_field_amplitude_v_m(intensity)
    assert e0 > 0.0
    assert e0 / ATOMIC_FIELD_V_M < 1.0


def test_blackbody_mean_square_field_scales_as_t4():
    e2_300 = blackbody_mean_square_field_v2_m2(300.0)
    e2_600 = blackbody_mean_square_field_v2_m2(600.0)
    assert np.isclose(e2_600 / e2_300, 16.0, rtol=1e-12)


def test_bbr_shift_scales_as_t4_in_static_approximation():
    s300 = bbr_clock_shift_hz(25.0, 300.0)
    s600 = bbr_clock_shift_hz(25.0, 600.0)
    assert np.isclose(s600 / s300, 16.0, rtol=1e-12)


def test_fractional_shift_and_quality_factor():
    assert np.isclose(fractional_frequency_shift(0.5, 5e14), 1e-15)
    assert np.isclose(quality_factor(5e14, 0.5), 1e15)


def test_uncertainty_quadrature():
    assert np.isclose(uncertainty_quadrature([3.0, 4.0]), 5.0)
