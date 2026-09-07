"""Computational companion for Chapter 21.

The module implements transparent SI-unit models for photoelectric stopping
potentials, retarding-current curves, Compton kinematics, detector calibration,
response folding, covariance propagation, and model comparison.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import erf, pi
from typing import Callable

import numpy as np

H = 6.62607015e-34
C = 299_792_458.0
E_CHARGE = 1.602176634e-19
M_E = 9.1093837139e-31
M_E_C2_EV = M_E * C**2 / E_CHARGE
LAMBDA_C = H / (M_E * C)


def _finite_array(x: np.ndarray | float, name: str) -> np.ndarray:
    arr = np.asarray(x, dtype=float)
    if np.any(~np.isfinite(arr)):
        raise ValueError(f"{name} must contain finite values")
    return arr


def _positive_array(x: np.ndarray | float, name: str) -> np.ndarray:
    arr = _finite_array(x, name)
    if np.any(arr <= 0.0):
        raise ValueError(f"{name} must contain positive values")
    return arr


def photon_energy_ev(frequency: np.ndarray | float) -> np.ndarray:
    nu = _positive_array(frequency, "frequency")
    return H * nu / E_CHARGE


def photoelectric_stopping_potential(
    frequency: np.ndarray | float,
    work_function_ev: float,
    contact_potential_v: float = 0.0,
) -> np.ndarray:
    """Measured stopping potential in volts under the chapter convention."""
    if not np.isfinite(work_function_ev) or work_function_ev <= 0.0:
        raise ValueError("work_function_ev must be finite and positive")
    if not np.isfinite(contact_potential_v):
        raise ValueError("contact_potential_v must be finite")
    return photon_energy_ev(frequency) - work_function_ev + contact_potential_v


def threshold_frequency(work_function_ev: float) -> float:
    if work_function_ev <= 0.0 or not np.isfinite(work_function_ev):
        raise ValueError("work_function_ev must be finite and positive")
    return work_function_ev * E_CHARGE / H


def threshold_wavelength(work_function_ev: float) -> float:
    return C / threshold_frequency(work_function_ev)


def quantum_efficiency(current_a: float, optical_power_w: float, frequency_hz: float) -> float:
    if current_a < 0.0 or optical_power_w <= 0.0 or frequency_hz <= 0.0:
        raise ValueError("require current >= 0, power > 0, and frequency > 0")
    electron_rate = current_a / E_CHARGE
    photon_rate = optical_power_w / (H * frequency_hz)
    return electron_rate / photon_rate


def retarding_current(
    voltage_v: np.ndarray | float,
    stopping_potential_v: float,
    saturation_current_a: float = 1.0,
    resolution_v: float = 0.03,
    dark_current_a: float = 0.0,
) -> np.ndarray:
    """Smooth retarding edge using a Gaussian-resolution error function."""
    v = _finite_array(voltage_v, "voltage_v")
    if stopping_potential_v <= 0.0 or saturation_current_a < 0.0 or resolution_v <= 0.0:
        raise ValueError("invalid retarding-current parameters")
    z = (v + stopping_potential_v) / (np.sqrt(2.0) * resolution_v)
    erf_vec = np.vectorize(erf, otypes=[float])
    collection = 0.5 * (1.0 + erf_vec(z))
    return dark_current_a + saturation_current_a * collection


@dataclass(frozen=True)
class LinearFit:
    slope: float
    intercept: float
    covariance: np.ndarray
    chi_square: float
    residuals: np.ndarray


def generalized_linear_fit(
    x: np.ndarray,
    y: np.ndarray,
    covariance: np.ndarray,
) -> LinearFit:
    x_arr = _finite_array(x, "x")
    y_arr = _finite_array(y, "y")
    cov = np.asarray(covariance, dtype=float)
    if x_arr.ndim != 1 or y_arr.shape != x_arr.shape:
        raise ValueError("x and y must be one-dimensional arrays of equal length")
    if cov.shape != (x_arr.size, x_arr.size):
        raise ValueError("covariance shape does not match data")
    if not np.allclose(cov, cov.T, atol=1e-14):
        raise ValueError("covariance must be symmetric")
    inv = np.linalg.inv(cov)
    design = np.column_stack((x_arr, np.ones_like(x_arr)))
    normal = design.T @ inv @ design
    parameter_covariance = np.linalg.inv(normal)
    beta = parameter_covariance @ design.T @ inv @ y_arr
    residuals = y_arr - design @ beta
    chi2 = float(residuals.T @ inv @ residuals)
    return LinearFit(float(beta[0]), float(beta[1]), parameter_covariance, chi2, residuals)


def common_mode_covariance(independent_sigma: np.ndarray | float, common_sigma: float) -> np.ndarray:
    sigma = _positive_array(independent_sigma, "independent_sigma")
    if sigma.ndim == 0:
        sigma = sigma.reshape(1)
    if common_sigma < 0.0 or not np.isfinite(common_sigma):
        raise ValueError("common_sigma must be finite and nonnegative")
    return np.diag(sigma**2) + common_sigma**2 * np.ones((sigma.size, sigma.size))


def compton_shift(angle_rad: np.ndarray | float, scatterer_mass_kg: float = M_E) -> np.ndarray:
    angle = _finite_array(angle_rad, "angle_rad")
    if np.any((angle < 0.0) | (angle > pi)):
        raise ValueError("angle must lie in [0, pi]")
    if scatterer_mass_kg <= 0.0 or not np.isfinite(scatterer_mass_kg):
        raise ValueError("scatterer_mass_kg must be finite and positive")
    return H * (1.0 - np.cos(angle)) / (scatterer_mass_kg * C)


def compton_scattered_energy_ev(incident_energy_ev: np.ndarray | float, angle_rad: np.ndarray | float) -> np.ndarray:
    energy = _positive_array(incident_energy_ev, "incident_energy_ev")
    angle = _finite_array(angle_rad, "angle_rad")
    if np.any((angle < 0.0) | (angle > pi)):
        raise ValueError("angle must lie in [0, pi]")
    return energy / (1.0 + (energy / M_E_C2_EV) * (1.0 - np.cos(angle)))


def compton_recoil_energy_ev(incident_energy_ev: np.ndarray | float, angle_rad: np.ndarray | float) -> np.ndarray:
    energy = _positive_array(incident_energy_ev, "incident_energy_ev")
    return energy - compton_scattered_energy_ev(energy, angle_rad)


def recoil_electron_angle_rad(incident_energy_ev: float, angle_rad: float) -> float:
    if incident_energy_ev <= 0.0 or not (0.0 <= angle_rad <= pi):
        raise ValueError("invalid energy or angle")
    scattered = float(compton_scattered_energy_ev(incident_energy_ev, angle_rad))
    numerator = scattered * np.sin(angle_rad)
    denominator = incident_energy_ev - scattered * np.cos(angle_rad)
    return float(np.arctan2(numerator, denominator))


def compton_edge_ev(incident_energy_ev: float) -> float:
    return float(compton_recoil_energy_ev(incident_energy_ev, pi))


def infer_scatterer_mass(angle_rad: np.ndarray, shifts_m: np.ndarray, covariance: np.ndarray) -> tuple[float, float]:
    angle = _finite_array(angle_rad, "angle_rad")
    shifts = _positive_array(shifts_m, "shifts_m")
    if angle.shape != shifts.shape:
        raise ValueError("angle and shifts must match")
    x = 1.0 - np.cos(angle)
    fit = generalized_linear_fit(x, shifts, covariance)
    if fit.slope <= 0.0:
        raise ValueError("fitted Compton scale must be positive")
    mass = H / (C * fit.slope)
    slope_sigma = np.sqrt(fit.covariance[0, 0])
    mass_sigma = mass * slope_sigma / fit.slope
    return float(mass), float(mass_sigma)


def polynomial_energy_calibration(channels: np.ndarray, energies_ev: np.ndarray, degree: int = 2) -> np.ndarray:
    ch = _finite_array(channels, "channels")
    en = _positive_array(energies_ev, "energies_ev")
    if ch.shape != en.shape or ch.ndim != 1 or ch.size <= degree:
        raise ValueError("insufficient or mismatched calibration data")
    if degree not in (1, 2):
        raise ValueError("degree must be 1 or 2")
    return np.polynomial.polynomial.polyfit(ch, en, degree)


def evaluate_calibration(channels: np.ndarray | float, coefficients: np.ndarray) -> np.ndarray:
    ch = _finite_array(channels, "channels")
    coeff = _finite_array(coefficients, "coefficients")
    return np.polynomial.polynomial.polyval(ch, coeff)


def gaussian_response(energy_grid: np.ndarray, center: float, sigma: float, area: float = 1.0) -> np.ndarray:
    grid = _finite_array(energy_grid, "energy_grid")
    if grid.ndim != 1 or np.any(np.diff(grid) <= 0.0):
        raise ValueError("energy_grid must be strictly increasing")
    if sigma <= 0.0 or area < 0.0:
        raise ValueError("sigma must be positive and area nonnegative")
    density = np.exp(-0.5 * ((grid - center) / sigma) ** 2)
    norm = np.trapezoid(density, grid)
    return area * density / norm


def synthetic_compton_spectrum(
    energy_grid: np.ndarray,
    shifted_center: float,
    unshifted_center: float,
    resolution_sigma: float,
    shifted_area: float = 1.0,
    unshifted_area: float = 0.35,
    background_level: float = 0.02,
) -> np.ndarray:
    grid = _finite_array(energy_grid, "energy_grid")
    if background_level < 0.0:
        raise ValueError("background_level must be nonnegative")
    shifted = gaussian_response(grid, shifted_center, resolution_sigma, shifted_area)
    unshifted = gaussian_response(grid, unshifted_center, 0.75 * resolution_sigma, unshifted_area)
    background = background_level * (1.0 + 0.25 * (grid - grid.min()) / (grid.max() - grid.min()))
    return shifted + unshifted + background


def chi_square(data: np.ndarray, model: np.ndarray, covariance: np.ndarray) -> float:
    y = _finite_array(data, "data")
    f = _finite_array(model, "model")
    cov = np.asarray(covariance, dtype=float)
    if y.shape != f.shape or cov.shape != (y.size, y.size):
        raise ValueError("incompatible data, model, and covariance")
    residual = y - f
    return float(residual.T @ np.linalg.inv(cov) @ residual)


def finite_difference_jacobian(function: Callable[[np.ndarray], np.ndarray], x: np.ndarray, step: np.ndarray | float) -> np.ndarray:
    point = _finite_array(x, "x")
    h = _positive_array(step, "step")
    if h.ndim == 0:
        h = np.full_like(point, float(h))
    if h.shape != point.shape:
        raise ValueError("step must be scalar or match x")
    baseline = np.asarray(function(point), dtype=float)
    jac = np.empty((baseline.size, point.size), dtype=float)
    for j in range(point.size):
        xp = point.copy(); xm = point.copy()
        xp[j] += h[j]; xm[j] -= h[j]
        jac[:, j] = (np.ravel(function(xp)) - np.ravel(function(xm))) / (2.0 * h[j])
    return jac


def propagate_covariance(function: Callable[[np.ndarray], np.ndarray], x: np.ndarray, covariance: np.ndarray, step: np.ndarray | float) -> np.ndarray:
    point = _finite_array(x, "x")
    cov = np.asarray(covariance, dtype=float)
    if cov.shape != (point.size, point.size):
        raise ValueError("covariance shape does not match x")
    jac = finite_difference_jacobian(function, point, step)
    return jac @ cov @ jac.T
