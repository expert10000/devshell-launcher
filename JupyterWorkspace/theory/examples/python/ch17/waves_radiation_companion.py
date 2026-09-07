"""Auditable calculations for Chapter 17 waves and radiation.

The functions are intentionally small and side-effect free so that every plot
can be checked against analytic limits and regression tests.
"""
from __future__ import annotations
import math
from typing import Iterable
import numpy as np

C0 = 299_792_458.0
EPS0 = 8.854_187_8128e-12
MU0 = 1.256_637_06212e-6
Z0 = math.sqrt(MU0 / EPS0)


def _positive(name: str, value: float) -> float:
    value = float(value)
    if not math.isfinite(value) or value <= 0.0:
        raise ValueError(f"{name} must be finite and positive")
    return value


def retarded_time(observation_time: float, distance: float, speed: float = C0) -> float:
    """Return t_r=t-R/v for a causal outgoing signal."""
    distance = float(distance)
    if distance < 0.0 or not math.isfinite(distance):
        raise ValueError("distance must be finite and nonnegative")
    speed = _positive("speed", speed)
    return float(observation_time) - distance / speed


def zone_terms(k: float, r: float) -> tuple[float, float, float]:
    """Dimensionless relative magnitudes of r^-3, k r^-2, and k^2 r^-1 terms.

    The common dimensional prefactor is omitted.  Ratios are exact: induction /
    near = kr and radiation / induction = kr.
    """
    k = _positive("k", k); r = _positive("r", r)
    return (1.0 / r**3, k / r**2, k**2 / r)


def radiation_zone_parameter(k: float, r: float) -> float:
    return _positive("k", k) * _positive("r", r)


def dipole_power_pattern(theta: np.ndarray | float) -> np.ndarray:
    """Normalized electric-dipole power pattern sin^2(theta)."""
    th = np.asarray(theta, dtype=float)
    return np.sin(th) ** 2


def half_wave_power_pattern(theta: np.ndarray | float) -> np.ndarray:
    """Normalized thin half-wave dipole power pattern.

    The limiting value on the dipole axis is zero and the broadside value is 1.
    """
    th = np.asarray(theta, dtype=float)
    s = np.sin(th)
    numerator = np.cos(0.5 * np.pi * np.cos(th))
    field = np.divide(numerator, s, out=np.zeros_like(th), where=np.abs(s) > 1e-12)
    return field**2


def dipole_solid_angle_integral(points: int = 2001) -> float:
    """Numerically integrate sin^2(theta) over solid angle."""
    if int(points) < 5:
        raise ValueError("points must be at least 5")
    theta = np.linspace(0.0, np.pi, int(points))
    integrand = np.sin(theta) ** 3
    return float(2.0 * np.pi * np.trapezoid(integrand, theta))


def harmonic_dipole_power(p0: float, omega: float) -> float:
    """Cycle-averaged power of p(t)=p0 cos(omega t)."""
    omega = _positive("omega", omega)
    p0 = float(p0)
    if not math.isfinite(p0):
        raise ValueError("p0 must be finite")
    return p0**2 * omega**4 / (12.0 * np.pi * EPS0 * C0**3)


def hertzian_radiation_resistance(length: float, wavelength: float) -> float:
    """Radiation resistance of an ideal uniform-current element."""
    length = _positive("length", length); wavelength = _positive("wavelength", wavelength)
    return 80.0 * np.pi**2 * (length / wavelength) ** 2


def array_factor(theta: np.ndarray | float, elements: int, spacing: float,
                 wavelength: float, progressive_phase: float = 0.0) -> np.ndarray:
    """Normalized magnitude-squared factor for a uniform linear z-directed array.

    theta is measured from the array axis, so the phase increment is k d cos(theta).
    """
    if int(elements) < 1:
        raise ValueError("elements must be positive")
    spacing = _positive("spacing", spacing); wavelength = _positive("wavelength", wavelength)
    th = np.asarray(theta, dtype=float)
    psi = 2.0 * np.pi * spacing / wavelength * np.cos(th) + float(progressive_phase)
    n = np.arange(int(elements), dtype=float)
    af = np.sum(np.exp(1j * np.multiply.outer(psi, n)), axis=-1)
    return np.abs(af / int(elements)) ** 2


def effective_aperture(gain: float, wavelength: float) -> float:
    gain = _positive("gain", gain); wavelength = _positive("wavelength", wavelength)
    return gain * wavelength**2 / (4.0 * np.pi)


def friis_received_power(transmitted_power: float, gain_tx: float, gain_rx: float,
                         wavelength: float, distance: float) -> float:
    pt = _positive("transmitted_power", transmitted_power)
    gt = _positive("gain_tx", gain_tx); gr = _positive("gain_rx", gain_rx)
    wavelength = _positive("wavelength", wavelength); distance = _positive("distance", distance)
    return pt * gt * gr * (wavelength / (4.0 * np.pi * distance)) ** 2


def gaussian_pulse(time: np.ndarray | float, center: float, width: float,
                   carrier_frequency: float) -> np.ndarray:
    width = _positive("width", width); carrier_frequency = _positive("carrier_frequency", carrier_frequency)
    t = np.asarray(time, dtype=float)
    tau = t - float(center)
    return np.exp(-0.5 * (tau / width) ** 2) * np.cos(2.0 * np.pi * carrier_frequency * tau)


def directivity_from_axisymmetric_pattern(theta: Iterable[float], pattern: Iterable[float]) -> float:
    th = np.asarray(list(theta), dtype=float); p = np.asarray(list(pattern), dtype=float)
    if th.ndim != 1 or p.shape != th.shape or th.size < 5:
        raise ValueError("theta and pattern must be matching one-dimensional arrays")
    if np.any(p < 0.0):
        raise ValueError("power pattern must be nonnegative")
    total = 2.0 * np.pi * np.trapezoid(p * np.sin(th), th)
    if total <= 0.0:
        raise ValueError("pattern must have positive integral")
    return float(4.0 * np.pi * np.max(p) / total)
