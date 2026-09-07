"""Auditable diagnostics for Chapter 19: The Crisis of Classical Physics.

The routines compare model forms and scales.  They do not implement a complete
quantum theory.  All public functions validate their domains and use SI units.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable

import numpy as np

K_B = 1.380649e-23
H = 6.62607015e-34
C = 299_792_458.0
E_CHARGE = 1.602176634e-19
M_E = 9.1093837015e-31


def _positive(name: str, value: float) -> float:
    value = float(value)
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be finite and positive")
    return value


def rayleigh_jeans_density(frequency_hz: np.ndarray | float, temperature_k: float) -> np.ndarray:
    """Classical spectral energy density u(nu,T) in J m^-3 Hz^-1."""
    temperature_k = _positive("temperature_k", temperature_k)
    nu = np.asarray(frequency_hz, dtype=float)
    if np.any(~np.isfinite(nu)) or np.any(nu < 0):
        raise ValueError("frequency_hz must be finite and nonnegative")
    return 8.0 * np.pi * nu**2 * K_B * temperature_k / C**3


def rayleigh_jeans_integrated(cutoff_hz: np.ndarray | float, temperature_k: float) -> np.ndarray:
    """Integral of the Rayleigh-Jeans density from zero to cutoff."""
    temperature_k = _positive("temperature_k", temperature_k)
    cutoff = np.asarray(cutoff_hz, dtype=float)
    if np.any(~np.isfinite(cutoff)) or np.any(cutoff < 0):
        raise ValueError("cutoff_hz must be finite and nonnegative")
    return 8.0 * np.pi * K_B * temperature_k * cutoff**3 / (3.0 * C**3)


def activation_ratio(delta_energy_j: float, temperature_k: float) -> float:
    """Dimensionless thermal activation ratio k_B T / Delta E."""
    delta_energy_j = _positive("delta_energy_j", delta_energy_j)
    temperature_k = _positive("temperature_k", temperature_k)
    return K_B * temperature_k / delta_energy_j


def diagnostic_activation_fraction(delta_energy_j: float, temperature_k: np.ndarray | float) -> np.ndarray:
    """Smooth diagnostic fraction exp[-Delta E/(k_B T)].

    This is a scale diagnostic, not the Einstein or Debye heat-capacity law.
    """
    delta_energy_j = _positive("delta_energy_j", delta_energy_j)
    temp = np.asarray(temperature_k, dtype=float)
    if np.any(~np.isfinite(temp)) or np.any(temp <= 0):
        raise ValueError("temperature_k must be finite and positive")
    return np.exp(-delta_energy_j / (K_B * temp))


def empirical_stopping_potential(frequency_hz: np.ndarray | float, work_function_j: float) -> np.ndarray:
    """Empirical photoelectric stopping potential max[(h nu-phi)/e,0]."""
    work_function_j = _positive("work_function_j", work_function_j)
    nu = np.asarray(frequency_hz, dtype=float)
    if np.any(~np.isfinite(nu)) or np.any(nu < 0):
        raise ValueError("frequency_hz must be finite and nonnegative")
    return np.maximum((H * nu - work_function_j) / E_CHARGE, 0.0)


def compton_shift(theta_rad: np.ndarray | float) -> np.ndarray:
    """Photon wavelength shift h/(m_e c) (1-cos theta)."""
    theta = np.asarray(theta_rad, dtype=float)
    if np.any(~np.isfinite(theta)):
        raise ValueError("theta_rad must be finite")
    return H * (1.0 - np.cos(theta)) / (M_E * C)


def de_broglie_wavelength_from_energy(kinetic_energy_j: np.ndarray | float) -> np.ndarray:
    """Nonrelativistic electron wavelength h/sqrt(2 m_e K)."""
    energy = np.asarray(kinetic_energy_j, dtype=float)
    if np.any(~np.isfinite(energy)) or np.any(energy <= 0):
        raise ValueError("kinetic_energy_j must be finite and positive")
    return H / np.sqrt(2.0 * M_E * energy)


def weighted_chi_square(observed: Iterable[float], predicted: Iterable[float], sigma: Iterable[float]) -> float:
    """Return sum[((observed-predicted)/sigma)^2]."""
    obs = np.asarray(list(observed), dtype=float)
    pred = np.asarray(list(predicted), dtype=float)
    err = np.asarray(list(sigma), dtype=float)
    if obs.shape != pred.shape or obs.shape != err.shape or obs.size == 0:
        raise ValueError("observed, predicted, and sigma must have the same nonzero shape")
    if np.any(~np.isfinite(obs)) or np.any(~np.isfinite(pred)) or np.any(~np.isfinite(err)) or np.any(err <= 0):
        raise ValueError("all values must be finite and sigma must be positive")
    return float(np.sum(((obs - pred) / err) ** 2))


def fit_origin_slope(x: Iterable[float], y: Iterable[float], sigma: Iterable[float] | None = None) -> float:
    """Weighted least-squares slope for y=a x through the origin."""
    xa = np.asarray(list(x), dtype=float)
    ya = np.asarray(list(y), dtype=float)
    if xa.shape != ya.shape or xa.size == 0 or np.any(~np.isfinite(xa)) or np.any(~np.isfinite(ya)):
        raise ValueError("x and y must have the same nonzero finite shape")
    if sigma is None:
        weights = np.ones_like(xa)
    else:
        sa = np.asarray(list(sigma), dtype=float)
        if sa.shape != xa.shape or np.any(~np.isfinite(sa)) or np.any(sa <= 0):
            raise ValueError("sigma must match x and be positive")
        weights = 1.0 / sa**2
    denominator = float(np.sum(weights * xa**2))
    if denominator == 0:
        raise ValueError("x values cannot all be zero")
    return float(np.sum(weights * xa * ya) / denominator)


def gaussian_line_spectrum(axis: np.ndarray, centers: Iterable[float], amplitudes: Iterable[float], sigma: float) -> np.ndarray:
    """Sum of area-normalized Gaussian lines on a supplied axis."""
    sigma = _positive("sigma", sigma)
    x = np.asarray(axis, dtype=float)
    c = np.asarray(list(centers), dtype=float)
    a = np.asarray(list(amplitudes), dtype=float)
    if x.ndim != 1 or c.shape != a.shape or c.size == 0:
        raise ValueError("axis must be 1-D and centers/amplitudes must match")
    if np.any(~np.isfinite(x)) or np.any(~np.isfinite(c)) or np.any(~np.isfinite(a)):
        raise ValueError("inputs must be finite")
    norm = sigma * math.sqrt(2.0 * math.pi)
    out = np.zeros_like(x)
    for center, amp in zip(c, a):
        out += amp * np.exp(-0.5 * ((x - center) / sigma) ** 2) / norm
    return out


def quadratic_relative_spacing(n: np.ndarray | float) -> np.ndarray:
    """Relative adjacent spacing for E_n proportional to n^2."""
    n_arr = np.asarray(n, dtype=float)
    if np.any(~np.isfinite(n_arr)) or np.any(n_arr <= 0):
        raise ValueError("n must be finite and positive")
    return (2.0 * n_arr + 1.0) / n_arr**2


@dataclass(frozen=True)
class DiagnosticDashboard:
    activation: float
    resolution_ratio: float
    action_ratio: float
    reduced_residual: float

    def as_array(self) -> np.ndarray:
        values = np.asarray([self.activation, self.resolution_ratio, self.action_ratio, self.reduced_residual], dtype=float)
        if np.any(~np.isfinite(values)) or np.any(values < 0):
            raise ValueError("dashboard values must be finite and nonnegative")
        return values
