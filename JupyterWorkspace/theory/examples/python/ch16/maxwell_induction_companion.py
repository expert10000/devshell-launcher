"""Numerical companion for Chapter 16: induction and Maxwell diagnostics.

All routines use SI units.  The module deliberately favors small, auditable
functions over opaque simulation frameworks.  It supports the figures and
regression tests shipped with Commit 168.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Tuple

import numpy as np

MU0 = 4.0e-7 * np.pi
EPS0 = 8.8541878128e-12
C0 = 1.0 / np.sqrt(MU0 * EPS0)


def retardation_parameter(length: float, omega: float, wave_speed: float = C0) -> float:
    """Return eta = omega * length / wave_speed."""
    if length < 0 or omega < 0 or wave_speed <= 0:
        raise ValueError("length and omega must be nonnegative; wave_speed positive")
    return omega * length / wave_speed


def conduction_displacement_ratio(sigma: float, omega: np.ndarray | float, epsilon: float) -> np.ndarray:
    """Return |J_conduction| / |J_displacement| = sigma/(omega epsilon)."""
    omega_array = np.asarray(omega, dtype=float)
    if sigma < 0 or np.any(omega_array <= 0) or epsilon <= 0:
        raise ValueError("sigma must be nonnegative; omega and epsilon positive")
    return sigma / (omega_array * epsilon)


def charge_relaxation_time(epsilon: float, sigma: float) -> float:
    if epsilon <= 0 or sigma <= 0:
        raise ValueError("epsilon and sigma must be positive")
    return epsilon / sigma


def charge_relaxation(t: np.ndarray | float, rho0: float, epsilon: float, sigma: float) -> np.ndarray:
    tau = charge_relaxation_time(epsilon, sigma)
    return rho0 * np.exp(-np.asarray(t, dtype=float) / tau)


def magnetic_diffusivity(mu: float, sigma: float) -> float:
    if mu <= 0 or sigma <= 0:
        raise ValueError("mu and sigma must be positive")
    return 1.0 / (mu * sigma)


def magnetic_diffusion_time(mu: float, sigma: float, length: float) -> float:
    if length <= 0:
        raise ValueError("length must be positive")
    return mu * sigma * length**2


def skin_depth(mu: float, sigma: float, omega: np.ndarray | float) -> np.ndarray:
    omega_array = np.asarray(omega, dtype=float)
    if mu <= 0 or sigma <= 0 or np.any(omega_array <= 0):
        raise ValueError("mu, sigma, and omega must be positive")
    return np.sqrt(2.0 / (mu * sigma * omega_array))


def effective_complex_permittivity(epsilon: float, sigma: float, omega: np.ndarray | float) -> np.ndarray:
    """Effective permittivity for the exp(-i omega t) convention."""
    omega_array = np.asarray(omega, dtype=float)
    if epsilon <= 0 or sigma < 0 or np.any(omega_array <= 0):
        raise ValueError("epsilon and omega must be positive; sigma nonnegative")
    return epsilon + 1j * sigma / omega_array


def rl_current(t: np.ndarray | float, voltage: float, resistance: float, inductance: float, i0: float = 0.0) -> np.ndarray:
    if resistance <= 0 or inductance <= 0:
        raise ValueError("resistance and inductance must be positive")
    t_array = np.asarray(t, dtype=float)
    i_inf = voltage / resistance
    return i_inf + (i0 - i_inf) * np.exp(-resistance * t_array / inductance)


def lc_state(t: np.ndarray | float, capacitance: float, inductance: float, q0: float, i0: float = 0.0) -> Tuple[np.ndarray, np.ndarray]:
    if capacitance <= 0 or inductance <= 0:
        raise ValueError("capacitance and inductance must be positive")
    t_array = np.asarray(t, dtype=float)
    omega0 = 1.0 / np.sqrt(inductance * capacitance)
    q = q0 * np.cos(omega0 * t_array) + (i0 / omega0) * np.sin(omega0 * t_array)
    i = -q0 * omega0 * np.sin(omega0 * t_array) + i0 * np.cos(omega0 * t_array)
    return q, i


def lc_energy(q: np.ndarray, i: np.ndarray, capacitance: float, inductance: float) -> np.ndarray:
    return 0.5 * q**2 / capacitance + 0.5 * inductance * i**2


def coupled_inductance_eigenvalues(l1: float, l2: float, mutual: float) -> np.ndarray:
    matrix = np.array([[l1, mutual], [mutual, l2]], dtype=float)
    return np.linalg.eigvalsh(matrix)


def identical_coupled_mode_frequencies(inductance: float, capacitance: float, coupling: np.ndarray | float) -> Tuple[np.ndarray, np.ndarray]:
    coupling_array = np.asarray(coupling, dtype=float)
    if inductance <= 0 or capacitance <= 0 or np.any(np.abs(coupling_array) >= 1):
        raise ValueError("L and C positive; |coupling| < 1")
    omega_symmetric = 1.0 / np.sqrt(capacitance * inductance * (1.0 + coupling_array))
    omega_antisymmetric = 1.0 / np.sqrt(capacitance * inductance * (1.0 - coupling_array))
    return omega_symmetric, omega_antisymmetric


def capacitor_currents(area: float, spacing: float, epsilon: float, sigma: float, voltage: np.ndarray | float, dvoltage_dt: np.ndarray | float) -> Tuple[np.ndarray, np.ndarray]:
    if area <= 0 or spacing <= 0 or epsilon <= 0 or sigma < 0:
        raise ValueError("invalid capacitor parameters")
    factor = area / spacing
    return sigma * factor * np.asarray(voltage, dtype=float), epsilon * factor * np.asarray(dvoltage_dt, dtype=float)


def faraday_emf(time: np.ndarray, flux: np.ndarray) -> np.ndarray:
    time = np.asarray(time, dtype=float)
    flux = np.asarray(flux, dtype=float)
    if time.ndim != 1 or flux.shape != time.shape or time.size < 3:
        raise ValueError("time and flux must be equal one-dimensional arrays")
    return -np.gradient(flux, time, edge_order=2)


def continuity_residual(drho_dt: np.ndarray | float, div_current: np.ndarray | float) -> np.ndarray:
    return np.asarray(drho_dt, dtype=float) + np.asarray(div_current, dtype=float)


def diffusion_sine_mode(x: np.ndarray, t: float, diffusivity: float, length: float, amplitude: float = 1.0, mode: int = 1) -> np.ndarray:
    if diffusivity <= 0 or length <= 0 or mode < 1:
        raise ValueError("invalid diffusion parameters")
    x = np.asarray(x, dtype=float)
    k = mode * np.pi / length
    return amplitude * np.sin(k * x) * np.exp(-diffusivity * k**2 * t)


def explicit_diffusion_sine(nx: int, final_time: float, diffusivity: float = 1.0, length: float = 1.0, courant: float = 0.4) -> Tuple[np.ndarray, np.ndarray, float]:
    """Evolve a sine mode with stable FTCS and return x, field, actual time."""
    if nx < 11 or final_time <= 0 or not (0 < courant <= 0.5):
        raise ValueError("nx >= 11, final_time > 0, and 0 < courant <= 0.5 required")
    x = np.linspace(0.0, length, nx)
    dx = x[1] - x[0]
    dt_limit = courant * dx**2 / diffusivity
    steps = int(np.ceil(final_time / dt_limit))
    dt = final_time / steps
    r = diffusivity * dt / dx**2
    field = np.sin(np.pi * x / length)
    for _ in range(steps):
        updated = field.copy()
        updated[1:-1] = field[1:-1] + r * (field[2:] - 2.0 * field[1:-1] + field[:-2])
        updated[0] = 0.0
        updated[-1] = 0.0
        field = updated
    return x, field, steps * dt


def diffusion_convergence(n_values: Iterable[int], final_time: float = 0.05) -> Tuple[np.ndarray, np.ndarray, float]:
    ns = np.asarray(list(n_values), dtype=int)
    errors = []
    spacings = []
    for nx in ns:
        x, numeric, actual_time = explicit_diffusion_sine(int(nx), final_time)
        exact = diffusion_sine_mode(x, actual_time, 1.0, 1.0)
        errors.append(np.sqrt(np.mean((numeric - exact) ** 2)))
        spacings.append(x[1] - x[0])
    slope = np.polyfit(np.log(spacings), np.log(errors), 1)[0]
    return np.asarray(spacings), np.asarray(errors), float(slope)


@dataclass(frozen=True)
class MaxwellResidualResult:
    faraday_rms: float
    ampere_rms: float
    dx: float


def sampled_vacuum_maxwell_residual(points: int, time: float = 0.19, wavelength: float = 1.0) -> MaxwellResidualResult:
    """Finite-difference residuals for an exact 1D vacuum field pair."""
    if points < 21:
        raise ValueError("points must be at least 21")
    x = np.linspace(0.0, wavelength, points)
    dx = x[1] - x[0]
    k = 2.0 * np.pi / wavelength
    omega = C0 * k
    e = np.sin(k * x) * np.cos(omega * time)
    b = -(1.0 / C0) * np.cos(k * x) * np.sin(omega * time)
    de_dx = np.gradient(e, dx, edge_order=2)
    db_dx = np.gradient(b, dx, edge_order=2)
    db_dt = -(omega / C0) * np.cos(k * x) * np.cos(omega * time)
    de_dt = -omega * np.sin(k * x) * np.sin(omega * time)
    faraday = de_dx + db_dt
    ampere = -db_dx - MU0 * EPS0 * de_dt
    interior = slice(2, -2)
    faraday_scale = max(np.sqrt(np.mean(de_dx[interior] ** 2)), 1e-30)
    ampere_scale = max(np.sqrt(np.mean(db_dx[interior] ** 2)), 1e-30)
    return MaxwellResidualResult(
        faraday_rms=float(np.sqrt(np.mean(faraday[interior] ** 2)) / faraday_scale),
        ampere_rms=float(np.sqrt(np.mean(ampere[interior] ** 2)) / ampere_scale),
        dx=float(dx),
    )
