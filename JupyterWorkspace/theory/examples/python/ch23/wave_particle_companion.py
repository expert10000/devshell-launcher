"""Computational companion for Chapter 23: Wave--Particle Duality.

All public functions use SI units unless the name states otherwise.  The module
keeps the empirical boundary of Chapter 23: it computes de Broglie kinematics,
diffraction geometry, Fourier-limited packets, coherence, interference, and
visibility diagnostics without assuming the Schrödinger equation developed in
Chapter 24.
"""
from __future__ import annotations

from math import asin, pi, sqrt
from typing import Iterable

import numpy as np

H = 6.62607015e-34
HBAR = H / (2.0 * pi)
C = 299_792_458.0
E_CHARGE = 1.602176634e-19
M_E = 9.1093837139e-31
M_N = 1.67492749804e-27
M_C60 = 720.0 * 1.66053906660e-27


def _finite(value: np.ndarray | float, name: str) -> np.ndarray:
    arr = np.asarray(value, dtype=float)
    if np.any(~np.isfinite(arr)):
        raise ValueError(f"{name} must contain finite values")
    return arr


def _positive(value: np.ndarray | float, name: str) -> np.ndarray:
    arr = _finite(value, name)
    if np.any(arr <= 0.0):
        raise ValueError(f"{name} must contain positive values")
    return arr


def relativistic_gamma(speed_m_s: np.ndarray | float) -> np.ndarray:
    speed = _finite(speed_m_s, "speed_m_s")
    if np.any(np.abs(speed) >= C):
        raise ValueError("require |speed| < c")
    return 1.0 / np.sqrt(1.0 - (speed / C) ** 2)


def relativistic_momentum(mass_kg: float, speed_m_s: np.ndarray | float) -> np.ndarray:
    if mass_kg <= 0.0:
        raise ValueError("mass_kg must be positive")
    speed = _finite(speed_m_s, "speed_m_s")
    return relativistic_gamma(speed) * mass_kg * speed


def kinetic_energy_relativistic_j(mass_kg: float, speed_m_s: np.ndarray | float) -> np.ndarray:
    if mass_kg <= 0.0:
        raise ValueError("mass_kg must be positive")
    return (relativistic_gamma(speed_m_s) - 1.0) * mass_kg * C**2


def momentum_from_kinetic_energy_j(mass_kg: float, kinetic_energy_j: np.ndarray | float) -> np.ndarray:
    """Exact momentum from K using (pc)^2 = K^2 + 2Kmc^2."""
    if mass_kg <= 0.0:
        raise ValueError("mass_kg must be positive")
    energy = _positive(kinetic_energy_j, "kinetic_energy_j")
    return np.sqrt(energy**2 / C**2 + 2.0 * mass_kg * energy)


def de_broglie_wavelength_from_momentum(momentum_kg_m_s: np.ndarray | float) -> np.ndarray:
    momentum = _positive(np.abs(momentum_kg_m_s), "momentum_kg_m_s")
    return H / momentum


def de_broglie_wavelength_from_speed(
    mass_kg: float,
    speed_m_s: np.ndarray | float,
    *,
    relativistic: bool = True,
) -> np.ndarray:
    speed = _positive(np.abs(speed_m_s), "speed_m_s")
    momentum = relativistic_momentum(mass_kg, speed) if relativistic else mass_kg * speed
    return de_broglie_wavelength_from_momentum(momentum)


def de_broglie_wavelength_from_kinetic_energy(
    mass_kg: float,
    kinetic_energy_j: np.ndarray | float,
    *,
    relativistic: bool = True,
) -> np.ndarray:
    energy = _positive(kinetic_energy_j, "kinetic_energy_j")
    momentum = momentum_from_kinetic_energy_j(mass_kg, energy) if relativistic else np.sqrt(2.0 * mass_kg * energy)
    return de_broglie_wavelength_from_momentum(momentum)


def electron_wavelength_from_voltage(voltage_v: np.ndarray | float, *, relativistic: bool = True) -> np.ndarray:
    voltage = _positive(voltage_v, "voltage_v")
    return de_broglie_wavelength_from_kinetic_energy(M_E, E_CHARGE * voltage, relativistic=relativistic)


def phase_velocity_relativistic(speed_m_s: np.ndarray | float) -> np.ndarray:
    speed = _positive(np.abs(speed_m_s), "speed_m_s")
    if np.any(speed >= C):
        raise ValueError("require speed < c")
    return C**2 / speed


def group_velocity_from_momentum(mass_kg: float, momentum_kg_m_s: np.ndarray | float) -> np.ndarray:
    if mass_kg <= 0.0:
        raise ValueError("mass_kg must be positive")
    p = _finite(momentum_kg_m_s, "momentum_kg_m_s")
    total_energy = np.sqrt((p * C) ** 2 + (mass_kg * C**2) ** 2)
    return p * C**2 / total_energy


def fourier_sigma_k(sigma_x_m: np.ndarray | float) -> np.ndarray:
    sigma_x = _positive(sigma_x_m, "sigma_x_m")
    return 1.0 / (2.0 * sigma_x)


def gaussian_packet_width_m(sigma_x0_m: float, time_s: np.ndarray | float, mass_kg: float) -> np.ndarray:
    if sigma_x0_m <= 0.0 or mass_kg <= 0.0:
        raise ValueError("sigma_x0_m and mass_kg must be positive")
    time = _finite(time_s, "time_s")
    tau = 2.0 * mass_kg * sigma_x0_m**2 / HBAR
    return sigma_x0_m * np.sqrt(1.0 + (time / tau) ** 2)


def gaussian_packet_density(
    x_m: np.ndarray,
    time_s: float,
    mass_kg: float,
    sigma_x0_m: float,
    mean_position_m: float = 0.0,
    mean_momentum_kg_m_s: float = 0.0,
) -> np.ndarray:
    x = _finite(x_m, "x_m")
    if x.ndim != 1 or np.any(np.diff(x) <= 0.0):
        raise ValueError("x_m must be a strictly increasing one-dimensional grid")
    sigma = float(gaussian_packet_width_m(sigma_x0_m, time_s, mass_kg))
    center = mean_position_m + mean_momentum_kg_m_s * time_s / mass_kg
    density = np.exp(-0.5 * ((x - center) / sigma) ** 2) / (sqrt(2.0 * pi) * sigma)
    return density / np.trapezoid(density, x)


def bragg_angle_rad(wavelength_m: float, plane_spacing_m: float, order: int = 1) -> float:
    if wavelength_m <= 0.0 or plane_spacing_m <= 0.0 or order < 1:
        raise ValueError("wavelength, spacing, and order must be positive")
    argument = order * wavelength_m / (2.0 * plane_spacing_m)
    if argument > 1.0:
        raise ValueError("no real Bragg angle for the requested order")
    return asin(argument)


def diffraction_ring_radius_m(camera_length_m: float, bragg_angle_rad_value: float) -> float:
    if camera_length_m <= 0.0 or not 0.0 <= bragg_angle_rad_value < pi / 4.0:
        raise ValueError("invalid camera length or Bragg angle")
    return camera_length_m * np.tan(2.0 * bragg_angle_rad_value)


def finite_grating_intensity(phase_half_difference: np.ndarray | float, slit_count: int) -> np.ndarray:
    """Normalized N-source interference factor [sin(Nx)/(N sin x)]^2."""
    if slit_count < 1:
        raise ValueError("slit_count must be positive")
    x = _finite(phase_half_difference, "phase_half_difference")
    denominator = np.sin(x)
    ratio = np.empty_like(x, dtype=float)
    near = np.abs(denominator) < 1e-12
    ratio[near] = 1.0
    ratio[~near] = np.sin(slit_count * x[~near]) / (slit_count * denominator[~near])
    return ratio**2


def double_slit_intensity(
    screen_position_m: np.ndarray,
    wavelength_m: float,
    distance_m: float,
    slit_separation_m: float,
    *,
    visibility: float = 1.0,
    phase_rad: float = 0.0,
    slit_width_m: float | None = None,
) -> np.ndarray:
    x = _finite(screen_position_m, "screen_position_m")
    if x.ndim != 1 or wavelength_m <= 0.0 or distance_m <= 0.0 or slit_separation_m <= 0.0:
        raise ValueError("invalid double-slit geometry")
    if not 0.0 <= visibility <= 1.0:
        raise ValueError("visibility must lie in [0,1]")
    phase = 2.0 * pi * slit_separation_m * x / (wavelength_m * distance_m) + phase_rad
    envelope = np.ones_like(x)
    if slit_width_m is not None:
        if slit_width_m <= 0.0:
            raise ValueError("slit_width_m must be positive")
        beta = pi * slit_width_m * x / (wavelength_m * distance_m)
        envelope = np.sinc(beta / pi) ** 2
    intensity = 0.5 * envelope * (1.0 + visibility * np.cos(phase))
    norm = np.trapezoid(intensity, x)
    if norm <= 0.0:
        raise ValueError("screen grid does not support a positive intensity integral")
    return intensity / norm


def fringe_visibility(maximum: float, minimum: float) -> float:
    if maximum < minimum or minimum < 0.0 or maximum + minimum <= 0.0:
        raise ValueError("require maximum >= minimum >= 0 and nonzero total")
    return (maximum - minimum) / (maximum + minimum)


def marker_overlap_visibility(overlap: complex | float) -> float:
    value = abs(overlap)
    if value > 1.0 + 1e-12:
        raise ValueError("normalized marker-state overlap cannot exceed one")
    return min(1.0, value)


def distinguishability_bound(visibility: np.ndarray | float) -> np.ndarray:
    value = _finite(visibility, "visibility")
    if np.any((value < 0.0) | (value > 1.0)):
        raise ValueError("visibility must lie in [0,1]")
    return np.sqrt(np.maximum(0.0, 1.0 - value**2))


def coherence_length_from_sigma_lambda(wavelength_m: float, sigma_wavelength_m: float) -> float:
    if wavelength_m <= 0.0 or sigma_wavelength_m <= 0.0:
        raise ValueError("wavelength and sigma_wavelength must be positive")
    return wavelength_m**2 / (2.0 * pi * sigma_wavelength_m)


def sample_detection_events(
    grid_m: np.ndarray,
    probability_density: np.ndarray,
    event_count: int,
    *,
    seed: int = 23,
) -> np.ndarray:
    grid = _finite(grid_m, "grid_m")
    density = _finite(probability_density, "probability_density")
    if grid.ndim != 1 or density.shape != grid.shape or np.any(np.diff(grid) <= 0.0):
        raise ValueError("grid and density must be matching one-dimensional arrays")
    if np.any(density < 0.0) or event_count < 1:
        raise ValueError("density must be nonnegative and event_count positive")
    weights = density / density.sum()
    if not np.isfinite(weights).all() or weights.sum() <= 0.0:
        raise ValueError("probability density has zero or invalid weight")
    rng = np.random.default_rng(seed)
    return rng.choice(grid, size=event_count, p=weights)


def rms(values: Iterable[float]) -> float:
    arr = _finite(np.asarray(list(values), dtype=float), "values")
    if arr.size == 0:
        raise ValueError("values must be nonempty")
    return float(np.sqrt(np.mean(arr**2)))
