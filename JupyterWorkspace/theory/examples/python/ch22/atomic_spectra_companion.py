"""Computational companion for Chapter 22: Atomic Spectra and Old Quantum Theory.

The module uses SI units unless a function name explicitly states electronvolts,
nanometres, or inverse metres.  It provides transparent, dependency-light
implementations for hydrogenic spectra, reduced-mass corrections, Ritz term
reconstruction, line broadening, and simple spectroscopy diagnostics.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import pi
from typing import Iterable

import numpy as np

H = 6.62607015e-34
HBAR = H / (2.0 * pi)
C = 299_792_458.0
E_CHARGE = 1.602176634e-19
M_E = 9.1093837139e-31
M_P = 1.67262192369e-27
M_D = 3.3435837724e-27
EPSILON_0 = 8.8541878128e-12
K_B = 1.380649e-23
ALPHA = 7.2973525693e-3
R_INF = 10_973_731.568160
A0 = 5.29177210903e-11
RYDBERG_EV = 13.605693122994
MU_B = 9.2740100657e-24


def _finite_array(value: np.ndarray | float, name: str) -> np.ndarray:
    arr = np.asarray(value, dtype=float)
    if np.any(~np.isfinite(arr)):
        raise ValueError(f"{name} must contain finite values")
    return arr


def _positive_array(value: np.ndarray | float, name: str) -> np.ndarray:
    arr = _finite_array(value, name)
    if np.any(arr <= 0.0):
        raise ValueError(f"{name} must contain positive values")
    return arr


def photon_energy_ev_from_wavelength(wavelength_m: np.ndarray | float) -> np.ndarray:
    wavelength = _positive_array(wavelength_m, "wavelength_m")
    return H * C / (wavelength * E_CHARGE)


def wavelength_from_photon_energy_ev(energy_ev: np.ndarray | float) -> np.ndarray:
    energy = _positive_array(energy_ev, "energy_ev")
    return H * C / (energy * E_CHARGE)


def reduced_mass(electron_mass: float = M_E, nuclear_mass: float = M_P) -> float:
    if electron_mass <= 0.0 or nuclear_mass <= 0.0:
        raise ValueError("masses must be positive")
    return electron_mass * nuclear_mass / (electron_mass + nuclear_mass)


def finite_mass_rydberg(nuclear_mass: float, nuclear_charge: int = 1) -> float:
    if nuclear_mass <= 0.0 or nuclear_charge < 1:
        raise ValueError("nuclear_mass must be positive and nuclear_charge >= 1")
    return R_INF * reduced_mass(M_E, nuclear_mass) / M_E * nuclear_charge**2


def rydberg_wavenumber(
    n_lower: int,
    n_upper: int,
    rydberg_constant: float = R_INF,
    nuclear_charge: int = 1,
) -> float:
    if not (1 <= n_lower < n_upper):
        raise ValueError("require 1 <= n_lower < n_upper")
    if rydberg_constant <= 0.0 or nuclear_charge < 1:
        raise ValueError("invalid Rydberg constant or nuclear charge")
    return rydberg_constant * nuclear_charge**2 * (1.0 / n_lower**2 - 1.0 / n_upper**2)


def series_wavelength_m(
    n_lower: int,
    n_upper: int,
    rydberg_constant: float = R_INF,
    nuclear_charge: int = 1,
) -> float:
    return 1.0 / rydberg_wavenumber(n_lower, n_upper, rydberg_constant, nuclear_charge)


def series_limit_wavelength_m(
    n_lower: int,
    rydberg_constant: float = R_INF,
    nuclear_charge: int = 1,
) -> float:
    if n_lower < 1:
        raise ValueError("n_lower must be positive")
    return n_lower**2 / (rydberg_constant * nuclear_charge**2)


def bohr_energy_ev(n: int, nuclear_charge: int = 1, nuclear_mass: float | None = None) -> float:
    if n < 1 or nuclear_charge < 1:
        raise ValueError("n and nuclear_charge must be positive integers")
    mass_factor = 1.0 if nuclear_mass is None else reduced_mass(M_E, nuclear_mass) / M_E
    return -RYDBERG_EV * mass_factor * nuclear_charge**2 / n**2


def transition_energy_ev(n_lower: int, n_upper: int, nuclear_charge: int = 1, nuclear_mass: float | None = None) -> float:
    if not (1 <= n_lower < n_upper):
        raise ValueError("require 1 <= n_lower < n_upper")
    return bohr_energy_ev(n_upper, nuclear_charge, nuclear_mass) - bohr_energy_ev(n_lower, nuclear_charge, nuclear_mass)


def bohr_radius_m(n: int, nuclear_charge: int = 1, nuclear_mass: float | None = None) -> float:
    if n < 1 or nuclear_charge < 1:
        raise ValueError("n and nuclear_charge must be positive")
    mass_factor = 1.0 if nuclear_mass is None else M_E / reduced_mass(M_E, nuclear_mass)
    return A0 * mass_factor * n**2 / nuclear_charge


def bohr_speed_m_s(n: int, nuclear_charge: int = 1) -> float:
    if n < 1 or nuclear_charge < 1:
        raise ValueError("n and nuclear_charge must be positive")
    return ALPHA * C * nuclear_charge / n


def adjacent_transition_frequency_hz(n: int, nuclear_charge: int = 1) -> float:
    if n < 2:
        raise ValueError("n must be at least 2")
    return transition_energy_ev(n - 1, n, nuclear_charge) * E_CHARGE / H


def classical_orbital_frequency_hz(n: int, nuclear_charge: int = 1) -> float:
    radius = bohr_radius_m(n, nuclear_charge)
    speed = bohr_speed_m_s(n, nuclear_charge)
    return speed / (2.0 * pi * radius)


def isotope_shift_wavelength_m(n_lower: int, n_upper: int) -> float:
    lambda_h = series_wavelength_m(n_lower, n_upper, finite_mass_rydberg(M_P, 1), 1)
    lambda_d = series_wavelength_m(n_lower, n_upper, finite_mass_rydberg(M_D, 1), 1)
    return lambda_d - lambda_h


def zeeman_frequency_shift_hz(m_delta: int, magnetic_field_t: float, lande_g: float = 1.0) -> float:
    if not np.isfinite(magnetic_field_t) or not np.isfinite(lande_g):
        raise ValueError("field and g factor must be finite")
    return lande_g * m_delta * MU_B * magnetic_field_t / H


def fine_structure_scale_ev(n: int, nuclear_charge: int = 1) -> float:
    if n < 1 or nuclear_charge < 1:
        raise ValueError("n and nuclear_charge must be positive")
    return RYDBERG_EV * (nuclear_charge * ALPHA) ** 2 * nuclear_charge**2 / n**3


def resolving_power(wavelength_m: float, separation_m: float) -> float:
    if wavelength_m <= 0.0 or separation_m <= 0.0:
        raise ValueError("wavelength and separation must be positive")
    return wavelength_m / separation_m


def gaussian_profile(x: np.ndarray, center: float, sigma: float, area: float = 1.0) -> np.ndarray:
    grid = _finite_array(x, "x")
    if grid.ndim != 1 or np.any(np.diff(grid) <= 0.0):
        raise ValueError("x must be a strictly increasing one-dimensional grid")
    if sigma <= 0.0 or area < 0.0:
        raise ValueError("sigma must be positive and area nonnegative")
    profile = np.exp(-0.5 * ((grid - center) / sigma) ** 2)
    norm = np.trapezoid(profile, grid)
    return area * profile / norm


def doppler_fwhm_frequency_hz(frequency_hz: float, temperature_k: float, emitter_mass_kg: float) -> float:
    if frequency_hz <= 0.0 or temperature_k <= 0.0 or emitter_mass_kg <= 0.0:
        raise ValueError("frequency, temperature, and mass must be positive")
    return frequency_hz * np.sqrt(8.0 * K_B * temperature_k * np.log(2.0) / (emitter_mass_kg * C**2))


def synthetic_line_spectrum(
    wavelength_grid_m: np.ndarray,
    centers_m: Iterable[float],
    sigma_m: float,
    areas: Iterable[float] | None = None,
) -> np.ndarray:
    centers = np.asarray(list(centers_m), dtype=float)
    if centers.size == 0 or np.any(centers <= 0.0):
        raise ValueError("at least one positive center is required")
    if areas is None:
        weights = np.ones_like(centers)
    else:
        weights = np.asarray(list(areas), dtype=float)
        if weights.shape != centers.shape or np.any(weights < 0.0):
            raise ValueError("areas must match centers and be nonnegative")
    spectrum = np.zeros_like(_finite_array(wavelength_grid_m, "wavelength_grid_m"))
    for center, weight in zip(centers, weights, strict=True):
        spectrum += gaussian_profile(wavelength_grid_m, center, sigma_m, weight)
    return spectrum


@dataclass(frozen=True)
class RitzFit:
    term_values_m_inv: np.ndarray
    covariance: np.ndarray
    residuals_m_inv: np.ndarray
    chi_square: float


def reconstruct_ritz_terms(
    lower_indices: np.ndarray,
    upper_indices: np.ndarray,
    wavenumbers_m_inv: np.ndarray,
    sigma_m_inv: np.ndarray,
    number_of_terms: int,
    reference_index: int = 0,
) -> RitzFit:
    """Recover term values from measured differences T_lower - T_upper.

    One term is fixed to zero to remove the additive gauge freedom.
    """
    lo = np.asarray(lower_indices, dtype=int)
    up = np.asarray(upper_indices, dtype=int)
    y = _finite_array(wavenumbers_m_inv, "wavenumbers_m_inv")
    sigma = _positive_array(sigma_m_inv, "sigma_m_inv")
    if lo.shape != up.shape or lo.shape != y.shape or y.shape != sigma.shape:
        raise ValueError("transition arrays must have matching shapes")
    if number_of_terms < 2 or not (0 <= reference_index < number_of_terms):
        raise ValueError("invalid term count or reference index")
    if np.any(lo < 0) or np.any(up < 0) or np.any(lo >= number_of_terms) or np.any(up >= number_of_terms):
        raise ValueError("term indices out of range")
    free = [i for i in range(number_of_terms) if i != reference_index]
    column = {term: j for j, term in enumerate(free)}
    design = np.zeros((y.size, len(free)), dtype=float)
    for row, (lidx, uidx) in enumerate(zip(lo, up, strict=True)):
        if lidx != reference_index:
            design[row, column[int(lidx)]] += 1.0
        if uidx != reference_index:
            design[row, column[int(uidx)]] -= 1.0
    weight = np.diag(1.0 / sigma**2)
    normal = design.T @ weight @ design
    covariance_free = np.linalg.inv(normal)
    beta = covariance_free @ design.T @ weight @ y
    residuals = y - design @ beta
    terms = np.zeros(number_of_terms, dtype=float)
    covariance = np.zeros((number_of_terms, number_of_terms), dtype=float)
    terms[free] = beta
    covariance[np.ix_(free, free)] = covariance_free
    chi2 = float(residuals.T @ weight @ residuals)
    return RitzFit(terms, covariance, residuals, chi2)
