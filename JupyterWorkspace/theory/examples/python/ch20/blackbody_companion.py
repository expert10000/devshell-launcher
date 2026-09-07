"""Numerically stable blackbody-radiation utilities for Chapter 20.

All public functions accept SI units. The module intentionally separates
spectral densities per unit frequency from those per unit wavelength.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import pi
from typing import Callable

import numpy as np

H = 6.62607015e-34
HBAR = H / (2.0 * pi)
C = 299_792_458.0
KB = 1.380649e-23
SIGMA = 5.670374419e-8
A_RAD = 4.0 * SIGMA / C
WIEN_B = 2.897771955e-3
ZETA3 = 1.202056903159594


def _positive_array(x: np.ndarray | float, name: str) -> np.ndarray:
    arr = np.asarray(x, dtype=float)
    if np.any(~np.isfinite(arr)) or np.any(arr <= 0.0):
        raise ValueError(f"{name} must contain finite positive values")
    return arr


def dimensionless_frequency(nu: np.ndarray | float, temperature: float) -> np.ndarray:
    nu_arr = _positive_array(nu, "frequency")
    if not np.isfinite(temperature) or temperature <= 0.0:
        raise ValueError("temperature must be finite and positive")
    return H * nu_arr / (KB * temperature)


def dimensionless_wavelength(wavelength: np.ndarray | float, temperature: float) -> np.ndarray:
    lam = _positive_array(wavelength, "wavelength")
    if not np.isfinite(temperature) or temperature <= 0.0:
        raise ValueError("temperature must be finite and positive")
    return H * C / (lam * KB * temperature)


def planck_frequency(nu: np.ndarray | float, temperature: float) -> np.ndarray:
    """Spectral energy density u_nu in J m^-3 Hz^-1."""
    nu_arr = _positive_array(nu, "frequency")
    x = dimensionless_frequency(nu_arr, temperature)
    prefactor = 8.0 * pi * H * nu_arr**3 / C**3
    result = np.zeros_like(x)
    safe = x < 700.0
    result[safe] = prefactor[safe] / np.expm1(x[safe])
    return result


def planck_wavelength(wavelength: np.ndarray | float, temperature: float) -> np.ndarray:
    """Spectral energy density u_lambda in J m^-4."""
    lam = _positive_array(wavelength, "wavelength")
    x = dimensionless_wavelength(lam, temperature)
    prefactor = 8.0 * pi * H * C / lam**5
    result = np.zeros_like(x)
    safe = x < 700.0
    result[safe] = prefactor[safe] / np.expm1(x[safe])
    return result


def spectral_radiance_wavelength(wavelength: np.ndarray | float, temperature: float) -> np.ndarray:
    """Blackbody spectral radiance B_lambda in W m^-3 sr^-1."""
    return C * planck_wavelength(wavelength, temperature) / (4.0 * pi)


def spectral_exitance_wavelength(wavelength: np.ndarray | float, temperature: float) -> np.ndarray:
    """Blackbody spectral exitance M_lambda in W m^-3."""
    return C * planck_wavelength(wavelength, temperature) / 4.0


def rayleigh_jeans_frequency(nu: np.ndarray | float, temperature: float) -> np.ndarray:
    nu_arr = _positive_array(nu, "frequency")
    if temperature <= 0.0:
        raise ValueError("temperature must be positive")
    return 8.0 * pi * nu_arr**2 * KB * temperature / C**3


def wien_frequency(nu: np.ndarray | float, temperature: float) -> np.ndarray:
    nu_arr = _positive_array(nu, "frequency")
    x = dimensionless_frequency(nu_arr, temperature)
    return 8.0 * pi * H * nu_arr**3 * np.exp(-x) / C**3


def total_energy_density(temperature: float) -> float:
    if temperature <= 0.0:
        raise ValueError("temperature must be positive")
    return A_RAD * temperature**4


def total_exitance(temperature: float) -> float:
    if temperature <= 0.0:
        raise ValueError("temperature must be positive")
    return SIGMA * temperature**4


def photon_number_density(temperature: float) -> float:
    if temperature <= 0.0:
        raise ValueError("temperature must be positive")
    return 16.0 * pi * ZETA3 * (KB * temperature) ** 3 / (H**3 * C**3)


def mean_photon_energy(temperature: float) -> float:
    return total_energy_density(temperature) / photon_number_density(temperature)


def cavity_mode_count(volume: float, nu1: float, nu2: float) -> float:
    if volume <= 0.0 or nu1 < 0.0 or nu2 <= nu1:
        raise ValueError("require volume > 0 and 0 <= nu1 < nu2")
    return 8.0 * pi * volume * (nu2**3 - nu1**3) / (3.0 * C**3)


def integrate_spectrum(wavelength: np.ndarray, spectral_values: np.ndarray) -> float:
    lam = _positive_array(wavelength, "wavelength")
    y = np.asarray(spectral_values, dtype=float)
    if y.shape != lam.shape or np.any(~np.isfinite(y)) or np.any(y < 0.0):
        raise ValueError("spectral_values must be finite, nonnegative, and match wavelength")
    if np.any(np.diff(lam) <= 0.0):
        raise ValueError("wavelength must be strictly increasing")
    return float(np.trapezoid(y, lam))


def band_fraction(temperature: float, lam_min: float, lam_max: float, points: int = 6000) -> float:
    if not (0.0 < lam_min < lam_max) or points < 100:
        raise ValueError("invalid band or insufficient integration points")
    lam = np.geomspace(lam_min, lam_max, points)
    band = integrate_spectrum(lam, spectral_exitance_wavelength(lam, temperature))
    return band / total_exitance(temperature)


def brightness_temperature(wavelength: np.ndarray | float, radiance: np.ndarray | float) -> np.ndarray:
    """Invert B_lambda exactly for positive radiance."""
    lam = _positive_array(wavelength, "wavelength")
    b = _positive_array(radiance, "radiance")
    if lam.shape != b.shape and lam.ndim and b.ndim:
        raise ValueError("wavelength and radiance shapes must match")
    argument = 1.0 + 2.0 * H * C**2 / (lam**5 * b)
    return H * C / (lam * KB * np.log(argument))


def normalized_gaussian_response(wavelength: np.ndarray, center: float, fwhm: float) -> np.ndarray:
    lam = _positive_array(wavelength, "wavelength")
    if center <= 0.0 or fwhm <= 0.0:
        raise ValueError("center and fwhm must be positive")
    sigma = fwhm / (2.0 * np.sqrt(2.0 * np.log(2.0)))
    response = np.exp(-0.5 * ((lam - center) / sigma) ** 2)
    norm = np.trapezoid(response, lam)
    if norm <= 0.0:
        raise ValueError("response does not overlap the wavelength grid")
    return response / norm


def band_signal(wavelength: np.ndarray, temperature: float, response: np.ndarray,
                emissivity: np.ndarray | float = 1.0) -> float:
    lam = _positive_array(wavelength, "wavelength")
    r = np.asarray(response, dtype=float)
    eps = np.asarray(emissivity, dtype=float)
    if r.shape != lam.shape or np.any(r < 0.0):
        raise ValueError("response must be nonnegative and match wavelength")
    if eps.ndim == 0:
        eps = np.full_like(lam, float(eps))
    if eps.shape != lam.shape or np.any((eps < 0.0) | (eps > 1.0)):
        raise ValueError("emissivity must lie in [0,1]")
    return float(np.trapezoid(r * eps * spectral_radiance_wavelength(lam, temperature), lam))


def convolve_gaussian(wavelength: np.ndarray, values: np.ndarray, fwhm: float) -> np.ndarray:
    lam = _positive_array(wavelength, "wavelength")
    y = np.asarray(values, dtype=float)
    if y.shape != lam.shape or fwhm <= 0.0:
        raise ValueError("invalid values or fwhm")
    spacing = np.diff(lam)
    if np.max(spacing) / np.min(spacing) > 1.02:
        raise ValueError("convolution requires an approximately uniform grid")
    dx = float(np.mean(spacing))
    sigma_px = fwhm / (2.0 * np.sqrt(2.0 * np.log(2.0)) * dx)
    radius = max(3, int(np.ceil(5.0 * sigma_px)))
    x = np.arange(-radius, radius + 1)
    kernel = np.exp(-0.5 * (x / sigma_px) ** 2)
    kernel /= np.sum(kernel)
    padded = np.pad(y, radius, mode="edge")
    return np.convolve(padded, kernel, mode="same")[radius:-radius]


@dataclass(frozen=True)
class FitResult:
    temperature: float
    scale: float
    chi_square: float
    residuals: np.ndarray


def fit_graybody_temperature(wavelength: np.ndarray, measured: np.ndarray,
                             uncertainty: np.ndarray, temperatures: np.ndarray) -> FitResult:
    lam = _positive_array(wavelength, "wavelength")
    y = _positive_array(measured, "measured")
    s = _positive_array(uncertainty, "uncertainty")
    grid = _positive_array(temperatures, "temperatures")
    if not (lam.shape == y.shape == s.shape):
        raise ValueError("measurement arrays must have identical shapes")
    best: FitResult | None = None
    weights = 1.0 / s**2
    for temperature in grid:
        model_shape = spectral_radiance_wavelength(lam, float(temperature))
        scale = float(np.sum(weights * y * model_shape) / np.sum(weights * model_shape**2))
        residuals = y - scale * model_shape
        chi2 = float(np.sum((residuals / s) ** 2))
        candidate = FitResult(float(temperature), scale, chi2, residuals)
        if best is None or candidate.chi_square < best.chi_square:
            best = candidate
    assert best is not None
    return best


def two_color_temperature(lam1: float, lam2: float, ratio: float,
                          t_min: float = 100.0, t_max: float = 20_000.0) -> float:
    if not (0.0 < lam1 < lam2) or ratio <= 0.0 or t_min <= 0.0 or t_max <= t_min:
        raise ValueError("invalid two-color input")

    def predicted(temp: float) -> float:
        b = spectral_radiance_wavelength(np.array([lam1, lam2]), temp)
        return float(b[0] / b[1])

    lo, hi = t_min, t_max
    f_lo, f_hi = predicted(lo) - ratio, predicted(hi) - ratio
    if f_lo * f_hi > 0.0:
        raise ValueError("ratio is outside the temperature bracket")
    for _ in range(100):
        mid = 0.5 * (lo + hi)
        f_mid = predicted(mid) - ratio
        if abs(f_mid) < 1e-12:
            return mid
        if f_lo * f_mid <= 0.0:
            hi = mid
            f_hi = f_mid
        else:
            lo = mid
            f_lo = f_mid
    return 0.5 * (lo + hi)


def finite_difference_log_slope(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    x_arr = _positive_array(x, "x")
    y_arr = _positive_array(y, "y")
    if x_arr.shape != y_arr.shape or x_arr.size < 3:
        raise ValueError("x and y must have matching shapes with at least 3 points")
    return np.gradient(np.log(y_arr), np.log(x_arr))
