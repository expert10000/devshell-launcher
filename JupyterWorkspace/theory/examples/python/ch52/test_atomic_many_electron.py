import numpy as np
import pytest

from atomic_many_electron import (
    HELIUM_HF_REFERENCE,
    HELIUM_NONREL_REFERENCE,
    correlation_energy,
    helium_approximation_ladder,
    helium_coulomb_integral_exponential,
    helium_optimal_zeta,
    helium_restricted_scf,
    helium_variational_energy,
    helium_variational_minimum,
    hydrogenic_1s_mean_radius,
    hydrogenic_1s_radial_probability,
    spherical_direct_potential,
)


def test_helium_optimal_zeta_is_27_over_16():
    assert np.isclose(helium_optimal_zeta(), 27.0 / 16.0)


def test_variational_stationary_point_is_minimum():
    z = helium_optimal_zeta()
    eps = 1e-4
    e0 = helium_variational_energy(z)
    assert helium_variational_energy(z - eps) > e0
    assert helium_variational_energy(z + eps) > e0


def test_variational_minimum_value():
    assert np.isclose(helium_variational_minimum(), -(27.0 / 16.0) ** 2)


def test_bare_hydrogenic_full_expectation_is_minus_2p75():
    assert np.isclose(helium_variational_energy(2.0), -2.75)


def test_coulomb_integral_is_five_zeta_over_eight():
    assert np.isclose(helium_coulomb_integral_exponential(1.7), 5.0 * 1.7 / 8.0)


def test_radial_probability_normalizes():
    r = np.linspace(0.0, 20.0, 20001)
    p = hydrogenic_1s_radial_probability(r, 1.8)
    assert np.isclose(np.trapezoid(p, r), 1.0, atol=2e-7)


def test_mean_radius_formula():
    zeta = 1.6
    r = np.linspace(0.0, 30.0, 30001)
    p = hydrogenic_1s_radial_probability(r, zeta)
    mean = np.trapezoid(r * p, r)
    assert np.isclose(mean, hydrogenic_1s_mean_radius(zeta), rtol=2e-7)


def test_screening_expands_simple_helium_orbital():
    assert hydrogenic_1s_mean_radius(helium_optimal_zeta()) > hydrogenic_1s_mean_radius(2.0)


def test_direct_potential_has_unit_charge_far_tail():
    r = np.linspace(0.01, 30.0, 3000)
    dr = r[1] - r[0]
    u = r * np.exp(-1.7 * r)
    u = u / np.sqrt(np.sum(u * u) * dr)
    vh = spherical_direct_potential(u, r)
    assert np.isclose(r[-1] * vh[-1], 1.0, rtol=2e-3)


def test_direct_potential_is_positive():
    r = np.linspace(0.01, 15.0, 1200)
    dr = r[1] - r[0]
    u = r * np.exp(-2.0 * r)
    u /= np.sqrt(np.sum(u * u) * dr)
    assert np.all(spherical_direct_potential(u, r) > 0.0)


def test_scf_converges_from_bare_orbital():
    res = helium_restricted_scf(n_grid=1200, r_max=22.0, tolerance=2e-9)
    assert res.converged
    assert res.iterations < 100


def test_scf_energy_near_hf_limit():
    res = helium_restricted_scf(n_grid=1800, r_max=24.0, tolerance=1e-9)
    assert abs(res.energy - HELIUM_HF_REFERENCE) < 0.003


def test_scf_lowers_one_parameter_variational_energy():
    res = helium_restricted_scf(n_grid=1200, r_max=22.0, tolerance=2e-9)
    assert res.energy < helium_variational_minimum()


def test_scf_double_counting_identity():
    res = helium_restricted_scf(n_grid=1000, r_max=20.0, tolerance=3e-9)
    assert np.isclose(res.energy, 2.0 * res.orbital_energy - res.direct_energy, atol=2e-10)


def test_approximation_ladder_is_variationally_ordered():
    d = helium_approximation_ladder()
    assert d["fixed_1s_full_expectation"] > d["optimized_exponential"]
    assert d["optimized_exponential"] > d["hartree_fock_limit"]
    assert d["hartree_fock_limit"] > d["correlated_nonrelativistic"]


def test_correlation_energy_is_negative():
    assert correlation_energy() < 0.0
    assert np.isclose(correlation_energy(), HELIUM_NONREL_REFERENCE - HELIUM_HF_REFERENCE)


def test_invalid_variational_exponent_rejected():
    with pytest.raises(ValueError):
        helium_variational_energy(-0.1)


def test_invalid_scf_grid_rejected():
    with pytest.raises(ValueError):
        helium_restricted_scf(n_grid=40)
