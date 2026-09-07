"""Numerical companion for Chapter 24: the Schrödinger equation.

The routines use SI units unless stated otherwise. They emphasize normalization,
probability current, one-dimensional stationary states, scattering, tunnelling,
and unitary wave-packet propagation. The module deliberately avoids the general
measurement and observable postulates reserved for Chapter 25.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import factorial, pi, sqrt
from typing import Callable

import numpy as np

H = 6.62607015e-34
HBAR = H / (2.0 * pi)
M_E = 9.1093837139e-31
E_CHARGE = 1.602176634e-19


def _grid(x_m: np.ndarray) -> np.ndarray:
    x = np.asarray(x_m, dtype=float)
    if x.ndim != 1 or x.size < 3 or np.any(~np.isfinite(x)):
        raise ValueError("x_m must be a finite one-dimensional grid")
    dx = np.diff(x)
    if np.any(dx <= 0.0) or not np.allclose(dx, dx[0], rtol=1e-8, atol=0.0):
        raise ValueError("x_m must be strictly increasing and uniformly spaced")
    return x


def probability_norm(psi: np.ndarray, x_m: np.ndarray) -> float:
    x = _grid(x_m)
    state = np.asarray(psi, dtype=complex)
    if state.shape != x.shape or np.any(~np.isfinite(state)):
        raise ValueError("psi must be finite and have the same shape as x_m")
    return float(np.trapezoid(np.abs(state) ** 2, x))


def normalize_wavefunction(psi: np.ndarray, x_m: np.ndarray) -> np.ndarray:
    norm = probability_norm(psi, x_m)
    if norm <= 0.0:
        raise ValueError("wavefunction norm must be positive")
    return np.asarray(psi, dtype=complex) / sqrt(norm)


def probability_density(psi: np.ndarray) -> np.ndarray:
    state = np.asarray(psi, dtype=complex)
    if np.any(~np.isfinite(state)):
        raise ValueError("psi must contain finite values")
    return np.abs(state) ** 2


def probability_current(psi: np.ndarray, x_m: np.ndarray, mass_kg: float) -> np.ndarray:
    if mass_kg <= 0.0:
        raise ValueError("mass_kg must be positive")
    x = _grid(x_m)
    state = np.asarray(psi, dtype=complex)
    if state.shape != x.shape:
        raise ValueError("psi and x_m must have the same shape")
    derivative = np.gradient(state, x, edge_order=2)
    return (HBAR / mass_kg) * np.imag(np.conjugate(state) * derivative)


def infinite_well_energy(level: int, width_m: float, mass_kg: float = M_E) -> float:
    if level < 1 or width_m <= 0.0 or mass_kg <= 0.0:
        raise ValueError("level, width_m, and mass_kg must be positive")
    return level**2 * pi**2 * HBAR**2 / (2.0 * mass_kg * width_m**2)


def infinite_well_state(level: int, x_m: np.ndarray, width_m: float) -> np.ndarray:
    x = _grid(x_m)
    if level < 1 or width_m <= 0.0:
        raise ValueError("level and width_m must be positive")
    psi = np.zeros_like(x, dtype=float)
    inside = (x >= 0.0) & (x <= width_m)
    psi[inside] = sqrt(2.0 / width_m) * np.sin(level * pi * x[inside] / width_m)
    return psi.astype(complex)


def free_gaussian_wavefunction(
    x_m: np.ndarray,
    time_s: float,
    mass_kg: float,
    sigma_x0_m: float,
    mean_position_m: float = 0.0,
    mean_momentum_kg_m_s: float = 0.0,
) -> np.ndarray:
    """Exact normalized free Gaussian with initial rms density width sigma_x0_m."""
    x = _grid(x_m)
    if mass_kg <= 0.0 or sigma_x0_m <= 0.0 or not np.isfinite(time_s):
        raise ValueError("mass, width, and time must be valid")
    tau = 2.0 * mass_kg * sigma_x0_m**2 / HBAR
    q = 1.0 + 1j * time_s / tau
    center = mean_position_m + mean_momentum_kg_m_s * time_s / mass_kg
    amplitude = (2.0 * pi * sigma_x0_m**2) ** (-0.25) / np.sqrt(q)
    envelope = np.exp(-((x - center) ** 2) / (4.0 * sigma_x0_m**2 * q))
    phase = np.exp(1j * mean_momentum_kg_m_s * (x - mean_position_m - mean_momentum_kg_m_s * time_s / (2.0 * mass_kg)) / HBAR)
    return normalize_wavefunction(amplitude * envelope * phase, x)


def potential_step_coefficients(energy_j: float, step_j: float) -> tuple[float, float]:
    if energy_j <= 0.0 or step_j < 0.0:
        raise ValueError("energy must be positive and step nonnegative")
    if energy_j <= step_j:
        return 1.0, 0.0
    k1 = sqrt(energy_j)
    k2 = sqrt(energy_j - step_j)
    reflection = ((k1 - k2) / (k1 + k2)) ** 2
    return reflection, 1.0 - reflection


def barrier_transmission(
    energy_j: np.ndarray | float,
    barrier_j: float,
    width_m: float,
    mass_kg: float = M_E,
) -> np.ndarray:
    energy = np.asarray(energy_j, dtype=float)
    if np.any(~np.isfinite(energy)) or np.any(energy <= 0.0) or barrier_j <= 0.0 or width_m <= 0.0 or mass_kg <= 0.0:
        raise ValueError("energies, barrier, width, and mass must be positive")
    result = np.empty_like(energy)
    below = energy < barrier_j
    above = energy > barrier_j
    equal = ~(below | above)
    if np.any(below):
        e = energy[below]
        kappa = np.sqrt(2.0 * mass_kg * (barrier_j - e)) / HBAR
        result[below] = 1.0 / (1.0 + (barrier_j**2 * np.sinh(kappa * width_m) ** 2) / (4.0 * e * (barrier_j - e)))
    if np.any(above):
        e = energy[above]
        q = np.sqrt(2.0 * mass_kg * (e - barrier_j)) / HBAR
        result[above] = 1.0 / (1.0 + (barrier_j**2 * np.sin(q * width_m) ** 2) / (4.0 * e * (e - barrier_j)))
    if np.any(equal):
        result[equal] = 1.0 / (1.0 + mass_kg * barrier_j * width_m**2 / (2.0 * HBAR**2))
    return np.clip(result, 0.0, 1.0)


def harmonic_oscillator_energy(level: int, angular_frequency_s: float) -> float:
    if level < 0 or angular_frequency_s <= 0.0:
        raise ValueError("level must be nonnegative and frequency positive")
    return HBAR * angular_frequency_s * (level + 0.5)


def harmonic_ground_state(x_m: np.ndarray, mass_kg: float, angular_frequency_s: float) -> np.ndarray:
    x = _grid(x_m)
    if mass_kg <= 0.0 or angular_frequency_s <= 0.0:
        raise ValueError("mass and frequency must be positive")
    alpha = mass_kg * angular_frequency_s / HBAR
    psi = (alpha / pi) ** 0.25 * np.exp(-0.5 * alpha * x**2)
    return normalize_wavefunction(psi, x)


def finite_difference_hamiltonian(
    x_m: np.ndarray,
    potential_j: np.ndarray,
    mass_kg: float = M_E,
) -> np.ndarray:
    x = _grid(x_m)
    potential = np.asarray(potential_j, dtype=float)
    if potential.shape != x.shape or np.any(~np.isfinite(potential)) or mass_kg <= 0.0:
        raise ValueError("potential must match x_m and mass must be positive")
    dx = x[1] - x[0]
    interior_v = potential[1:-1]
    factor = HBAR**2 / (2.0 * mass_kg * dx**2)
    diagonal = 2.0 * factor + interior_v
    off = -factor * np.ones(x.size - 3)
    return np.diag(diagonal) + np.diag(off, 1) + np.diag(off, -1)


@dataclass(frozen=True)
class BoundStateSolution:
    energies_j: np.ndarray
    states: np.ndarray


def solve_bound_states(
    x_m: np.ndarray,
    potential_j: np.ndarray,
    state_count: int,
    mass_kg: float = M_E,
) -> BoundStateSolution:
    x = _grid(x_m)
    if state_count < 1 or state_count > x.size - 2:
        raise ValueError("invalid state_count")
    hamiltonian = finite_difference_hamiltonian(x, potential_j, mass_kg)
    energies, vectors = np.linalg.eigh(hamiltonian)
    states = np.zeros((state_count, x.size), dtype=complex)
    for index in range(state_count):
        states[index, 1:-1] = vectors[:, index]
        states[index] = normalize_wavefunction(states[index], x)
        pivot = int(np.argmax(np.abs(states[index])))
        if states[index, pivot].real < 0.0:
            states[index] *= -1.0
    return BoundStateSolution(energies[:state_count], states)


def split_step_propagate(
    psi0: np.ndarray,
    x_m: np.ndarray,
    potential_j: np.ndarray | Callable[[np.ndarray], np.ndarray],
    time_step_s: float,
    steps: int,
    mass_kg: float = M_E,
) -> np.ndarray:
    """Second-order split-step Fourier propagation on a periodic numerical grid."""
    x = _grid(x_m)
    if time_step_s == 0.0 or steps < 0 or mass_kg <= 0.0:
        raise ValueError("time step must be nonzero, steps nonnegative, mass positive")
    state = normalize_wavefunction(np.asarray(psi0, dtype=complex), x)
    potential = potential_j(x) if callable(potential_j) else np.asarray(potential_j, dtype=float)
    if potential.shape != x.shape or np.any(~np.isfinite(potential)):
        raise ValueError("potential must be finite and match x_m")
    dx = x[1] - x[0]
    k = 2.0 * pi * np.fft.fftfreq(x.size, d=dx)
    half_v = np.exp(-0.5j * potential * time_step_s / HBAR)
    kinetic = np.exp(-1j * HBAR * k**2 * time_step_s / (2.0 * mass_kg))
    for _ in range(steps):
        state *= half_v
        state = np.fft.ifft(kinetic * np.fft.fft(state))
        state *= half_v
    return state


def continuity_residual(
    psi_before: np.ndarray,
    psi_after: np.ndarray,
    x_m: np.ndarray,
    delta_t_s: float,
    mass_kg: float,
) -> np.ndarray:
    if delta_t_s == 0.0:
        raise ValueError("delta_t_s must be nonzero")
    x = _grid(x_m)
    rho_t = (probability_density(psi_after) - probability_density(psi_before)) / delta_t_s
    j_mid = probability_current(0.5 * (np.asarray(psi_before) + np.asarray(psi_after)), x, mass_kg)
    return rho_t + np.gradient(j_mid, x, edge_order=2)
