"""Deterministic symbolic and numerical tools for Chapter 12 classical fields.

The routines are intentionally small and explicit. They support the textbook's
one-dimensional wave, Klein--Gordon, Poisson, gauge, and sine--Gordon examples,
with diagnostics designed for regression tests rather than production-scale PDEs.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
import sympy as sp

Array = np.ndarray


def euler_lagrange_density(
    density: sp.Expr,
    field: sp.Expr,
    coordinates: tuple[sp.Symbol, ...],
) -> sp.Expr:
    """Return the Euler--Lagrange operator for a first-derivative density.

    ``field`` should be a SymPy function evaluated on ``coordinates``. The
    result is dL/dphi - sum_mu d_mu[dL/d(d_mu phi)].
    """
    result = sp.diff(density, field)
    for coordinate in coordinates:
        derivative = sp.diff(field, coordinate)
        result -= sp.diff(sp.diff(density, derivative), coordinate)
    return sp.simplify(result)


def periodic_laplacian(values: Array, spacing: float) -> Array:
    """Second-order periodic finite-difference Laplacian in one dimension."""
    values = np.asarray(values, dtype=float)
    if spacing <= 0:
        raise ValueError("spacing must be positive")
    return (np.roll(values, -1) - 2.0 * values + np.roll(values, 1)) / spacing**2


def dirichlet_laplacian(values: Array, spacing: float) -> Array:
    """Second-order Laplacian with fixed zero endpoint values."""
    values = np.asarray(values, dtype=float)
    result = np.zeros_like(values)
    result[1:-1] = (values[2:] - 2.0 * values[1:-1] + values[:-2]) / spacing**2
    return result


def gradient_periodic(values: Array, spacing: float) -> Array:
    """Centered periodic first derivative."""
    values = np.asarray(values, dtype=float)
    return (np.roll(values, -1) - np.roll(values, 1)) / (2.0 * spacing)


def wave_leapfrog(
    initial_displacement: Array,
    initial_velocity: Array,
    spacing: float,
    step: float,
    steps: int,
    speed: float = 1.0,
    boundary: str = "periodic",
) -> Array:
    """Integrate u_tt = c^2 u_xx with centered time and space differences."""
    if steps < 1:
        raise ValueError("steps must be positive")
    if step <= 0 or speed <= 0:
        raise ValueError("step and speed must be positive")
    u0 = np.asarray(initial_displacement, dtype=float)
    v0 = np.asarray(initial_velocity, dtype=float)
    if u0.shape != v0.shape:
        raise ValueError("initial arrays must have the same shape")
    lap = periodic_laplacian if boundary == "periodic" else dirichlet_laplacian
    history = np.empty((steps + 1, u0.size), dtype=float)
    history[0] = u0
    history[1] = u0 + step * v0 + 0.5 * (speed * step) ** 2 * lap(u0, spacing)
    if boundary == "dirichlet":
        history[1, [0, -1]] = 0.0
    for index in range(1, steps):
        history[index + 1] = (
            2.0 * history[index] - history[index - 1]
            + (speed * step) ** 2 * lap(history[index], spacing)
        )
        if boundary == "dirichlet":
            history[index + 1, [0, -1]] = 0.0
    return history


def wave_energy(history: Array, spacing: float, step: float, speed: float = 1.0) -> Array:
    """Discrete periodic wave energy at interior time levels."""
    history = np.asarray(history, dtype=float)
    velocity = (history[2:] - history[:-2]) / (2.0 * step)
    gradient = np.array([gradient_periodic(state, spacing) for state in history[1:-1]])
    return spacing * np.sum(0.5 * velocity**2 + 0.5 * speed**2 * gradient**2, axis=1)


def klein_gordon_dispersion(wavenumber: Array, speed: float = 1.0, mass_frequency: float = 1.0) -> Array:
    """Dispersion omega(k)=sqrt(c^2 k^2 + Omega^2)."""
    wavenumber = np.asarray(wavenumber, dtype=float)
    return np.sqrt((speed * wavenumber) ** 2 + mass_frequency**2)


def solve_poisson_dirichlet(source: Array, spacing: float) -> Array:
    """Solve -u_xx=f on a uniform interval with u=0 at both endpoints."""
    source = np.asarray(source, dtype=float)
    if source.ndim != 1 or source.size < 3:
        raise ValueError("source must be a one-dimensional array with at least 3 points")
    interior = source.size - 2
    matrix = np.diag(np.full(interior, 2.0))
    matrix += np.diag(np.full(interior - 1, -1.0), 1)
    matrix += np.diag(np.full(interior - 1, -1.0), -1)
    solution = np.zeros_like(source)
    solution[1:-1] = np.linalg.solve(matrix / spacing**2, source[1:-1])
    return solution


def dirichlet_green_matrix(points: Array) -> Array:
    """Green matrix for -d^2/dx^2 on [0,L] with Dirichlet endpoints."""
    points = np.asarray(points, dtype=float)
    length = points[-1] - points[0]
    x = points - points[0]
    left = np.minimum.outer(x, x)
    right = length - np.maximum.outer(x, x)
    return left * right / length


def potentials_to_fields_1d(
    scalar_potential: Array,
    vector_potential: Array,
    spacing: float,
    step: float,
) -> tuple[Array, Array]:
    """Recover E_x and a transverse B_z from Phi(x,t), A_y(x,t).

    Inputs have shape (time, space). E_x=-partial_x Phi and
    B_z=partial_x A_y. The temporal derivative term in E vanishes because the
    chosen vector potential has no x component.
    """
    scalar_potential = np.asarray(scalar_potential, dtype=float)
    vector_potential = np.asarray(vector_potential, dtype=float)
    if scalar_potential.shape != vector_potential.shape:
        raise ValueError("potential arrays must have equal shape")
    electric = -np.array([gradient_periodic(row, spacing) for row in scalar_potential])
    magnetic = np.array([gradient_periodic(row, spacing) for row in vector_potential])
    return electric, magnetic


def gauge_transform_1d(
    scalar_potential: Array,
    vector_potential_x: Array,
    gauge_function: Array,
    spacing: float,
    step: float,
) -> tuple[Array, Array]:
    """Apply Phi' = Phi-d_t chi and A_x'=A_x+d_x chi."""
    phi = np.asarray(scalar_potential, dtype=float)
    ax = np.asarray(vector_potential_x, dtype=float)
    chi = np.asarray(gauge_function, dtype=float)
    if phi.shape != ax.shape or phi.shape != chi.shape:
        raise ValueError("all arrays must have equal shape")
    d_t_chi = np.zeros_like(chi)
    d_t_chi[1:-1] = (chi[2:] - chi[:-2]) / (2.0 * step)
    d_t_chi[0] = (chi[1] - chi[0]) / step
    d_t_chi[-1] = (chi[-1] - chi[-2]) / step
    d_x_chi = np.array([gradient_periodic(row, spacing) for row in chi])
    return phi - d_t_chi, ax + d_x_chi


def electric_field_1d(phi: Array, ax: Array, spacing: float, step: float) -> Array:
    """Compute E_x=-d_x Phi-d_t A_x with periodic x derivative."""
    phi = np.asarray(phi, dtype=float)
    ax = np.asarray(ax, dtype=float)
    d_x_phi = np.array([gradient_periodic(row, spacing) for row in phi])
    d_t_ax = np.zeros_like(ax)
    d_t_ax[1:-1] = (ax[2:] - ax[:-2]) / (2.0 * step)
    d_t_ax[0] = (ax[1] - ax[0]) / step
    d_t_ax[-1] = (ax[-1] - ax[-2]) / step
    return -d_x_phi - d_t_ax


def continuity_residual(density: Array, current: Array, spacing: float, step: float) -> Array:
    """Centered residual partial_t rho + partial_x J."""
    density = np.asarray(density, dtype=float)
    current = np.asarray(current, dtype=float)
    d_t = (density[2:] - density[:-2]) / (2.0 * step)
    d_x = np.array([gradient_periodic(row, spacing) for row in current[1:-1]])
    return d_t + d_x


def sine_gordon_static_kink(x: Array, center: float = 0.0, width: float = 1.0) -> Array:
    """Static 2-pi sine--Gordon kink."""
    x = np.asarray(x, dtype=float)
    return 4.0 * np.arctan(np.exp((x - center) / width))


def sine_gordon_static_residual(field: Array, spacing: float) -> Array:
    """Interior residual phi_xx-sin(phi) for the unit-width static equation."""
    field = np.asarray(field, dtype=float)
    second = (field[2:] - 2.0 * field[1:-1] + field[:-2]) / spacing**2
    return second - np.sin(field[1:-1])


def observed_order(errors: Array, spacings: Array) -> float:
    """Least-squares convergence order from error proportional to h^p."""
    errors = np.asarray(errors, dtype=float)
    spacings = np.asarray(spacings, dtype=float)
    if np.any(errors <= 0) or np.any(spacings <= 0):
        raise ValueError("errors and spacings must be positive")
    return float(np.polyfit(np.log(spacings), np.log(errors), 1)[0])


@dataclass(frozen=True)
class StabilityReport:
    courant_number: float
    stable_by_cfl: bool


def wave_cfl_report(speed: float, step: float, spacing: float) -> StabilityReport:
    """Return the Courant number and the 1D leapfrog stability prediction."""
    courant = speed * step / spacing
    return StabilityReport(courant, courant <= 1.0 + 1.0e-14)
