"""Executable models for Chapter 10: Lagrangian Mechanics.

The module keeps the numerical and symbolic examples deliberately small and
transparent.  It supports symbolic Euler--Lagrange construction, deterministic
Runge--Kutta integration, pendulum diagnostics, holonomic-constraint residuals,
central-force effective potentials, generalized normal modes, and charged
particle trajectories in uniform electromagnetic fields.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, Sequence

import numpy as np
import sympy as sp

Array = np.ndarray
StateRHS = Callable[[float, Array], Array]


@dataclass(frozen=True)
class IntegrationResult:
    """Time grid and state history returned by a deterministic integrator."""

    time: Array
    state: Array


def euler_lagrange_residuals(
    lagrangian: sp.Expr,
    coordinates: Sequence[sp.Symbol],
    velocities: Sequence[sp.Symbol],
    accelerations: Sequence[sp.Symbol],
    time_symbol: sp.Symbol | None = None,
) -> tuple[sp.Expr, ...]:
    """Return ``d/dt(dL/dqdot_i) - dL/dq_i`` for independent symbols.

    The coordinates, velocities, and accelerations are represented by separate
    symbols.  The total derivative is expanded with the chain rule, which makes
    the result suitable for code generation and algebraic solution for the
    accelerations.
    """
    q = tuple(coordinates)
    qdot = tuple(velocities)
    qddot = tuple(accelerations)
    if not q or len(q) != len(qdot) or len(q) != len(qddot):
        raise ValueError("coordinates, velocities, and accelerations must have equal nonzero length")

    residuals: list[sp.Expr] = []
    for coordinate, velocity in zip(q, qdot):
        momentum = sp.diff(lagrangian, velocity)
        total_derivative = sp.Integer(0)
        if time_symbol is not None:
            total_derivative += sp.diff(momentum, time_symbol)
        for qj, vj, aj in zip(q, qdot, qddot):
            total_derivative += sp.diff(momentum, qj) * vj
            total_derivative += sp.diff(momentum, vj) * aj
        residuals.append(sp.simplify(total_derivative - sp.diff(lagrangian, coordinate)))
    return tuple(residuals)


def solve_accelerations(
    residuals: Iterable[sp.Expr], accelerations: Sequence[sp.Symbol]
) -> dict[sp.Symbol, sp.Expr]:
    """Solve Euler--Lagrange residual equations for generalized accelerations."""
    equations = [sp.Eq(sp.simplify(residual), 0) for residual in residuals]
    solutions = sp.solve(equations, tuple(accelerations), dict=True, simplify=True)
    if len(solutions) != 1:
        raise ValueError("Euler--Lagrange system does not have one explicit acceleration solution")
    return {symbol: sp.simplify(solutions[0][symbol]) for symbol in accelerations}


def rk4_system(rhs: StateRHS, time: Array, initial_state: Array) -> IntegrationResult:
    """Integrate a first-order system on a strictly increasing grid with RK4."""
    t = np.asarray(time, dtype=float)
    y0 = np.asarray(initial_state, dtype=float)
    if t.ndim != 1 or t.size < 2 or np.any(np.diff(t) <= 0.0):
        raise ValueError("time must be a strictly increasing one-dimensional grid")
    if y0.ndim != 1:
        raise ValueError("initial_state must be one-dimensional")

    history = np.empty((t.size, y0.size), dtype=float)
    history[0] = y0
    for index, step in enumerate(np.diff(t)):
        ti = float(t[index])
        yi = history[index]
        k1 = np.asarray(rhs(ti, yi), dtype=float)
        k2 = np.asarray(rhs(ti + 0.5 * step, yi + 0.5 * step * k1), dtype=float)
        k3 = np.asarray(rhs(ti + 0.5 * step, yi + 0.5 * step * k2), dtype=float)
        k4 = np.asarray(rhs(ti + step, yi + step * k3), dtype=float)
        if any(k.shape != y0.shape for k in (k1, k2, k3, k4)):
            raise ValueError("rhs returned a state derivative with the wrong shape")
        history[index + 1] = yi + step * (k1 + 2.0 * k2 + 2.0 * k3 + k4) / 6.0
    return IntegrationResult(t, history)


def pendulum_rhs(length: float, gravity: float = 9.81) -> StateRHS:
    """Return the nonlinear simple-pendulum state equation for ``(theta, omega)``."""
    if length <= 0.0 or gravity <= 0.0:
        raise ValueError("length and gravity must be positive")

    def rhs(_time: float, state: Array) -> Array:
        theta, omega = state
        return np.array([omega, -(gravity / length) * np.sin(theta)], dtype=float)

    return rhs


def pendulum_energy(
    state: Array, mass: float, length: float, gravity: float = 9.81
) -> Array:
    """Return pendulum energy with zero potential at the lowest point."""
    if mass <= 0.0 or length <= 0.0 or gravity <= 0.0:
        raise ValueError("mass, length, and gravity must be positive")
    values = np.asarray(state, dtype=float)
    if values.shape[-1] != 2:
        raise ValueError("state must end with (theta, omega)")
    theta = values[..., 0]
    omega = values[..., 1]
    return 0.5 * mass * length**2 * omega**2 + mass * gravity * length * (1.0 - np.cos(theta))


def pendulum_period_quadrature(
    amplitude: float, length: float, gravity: float = 9.81, nodes: int = 96
) -> float:
    """Return the exact nonlinear pendulum period by Gauss--Legendre quadrature."""
    if not 0.0 <= amplitude < np.pi:
        raise ValueError("amplitude must satisfy 0 <= amplitude < pi")
    if length <= 0.0 or gravity <= 0.0 or nodes < 8:
        raise ValueError("length, gravity, and nodes must be valid positive values")
    abscissa, weight = np.polynomial.legendre.leggauss(nodes)
    phi = 0.25 * np.pi * (abscissa + 1.0)
    modulus = np.sin(0.5 * amplitude)
    integrand = 1.0 / np.sqrt(1.0 - modulus**2 * np.sin(phi) ** 2)
    elliptic_k = 0.25 * np.pi * np.sum(weight * integrand)
    return float(4.0 * np.sqrt(length / gravity) * elliptic_k)


def cartesian_pendulum_rhs(length: float, gravity: float = 9.81) -> StateRHS:
    """Return Cartesian pendulum dynamics for state ``(x, y, vx, vy)``.

    The multiplier acceleration is reconstructed from the differentiated
    holonomic constraint ``x^2 + y^2 = length^2``.
    """
    if length <= 0.0 or gravity <= 0.0:
        raise ValueError("length and gravity must be positive")

    def rhs(_time: float, state: Array) -> Array:
        x, y, vx, vy = state
        speed_squared = vx * vx + vy * vy
        multiplier_per_mass = (gravity * y - speed_squared) / length**2
        ax = multiplier_per_mass * x
        ay = -gravity + multiplier_per_mass * y
        return np.array([vx, vy, ax, ay], dtype=float)

    return rhs


def project_circle_state(state: Array, radius: float) -> Array:
    """Project position to a circle and velocity to its tangent space."""
    if radius <= 0.0:
        raise ValueError("radius must be positive")
    values = np.asarray(state, dtype=float)
    if values.shape != (4,):
        raise ValueError("state must have four components")
    position = values[:2]
    velocity = values[2:]
    norm = float(np.linalg.norm(position))
    if norm == 0.0:
        raise ValueError("cannot project the origin onto a circle")
    projected_position = radius * position / norm
    projected_velocity = velocity - projected_position * (
        np.dot(projected_position, velocity) / radius**2
    )
    return np.concatenate((projected_position, projected_velocity))


def integrate_cartesian_pendulum(
    time: Array,
    initial_state: Array,
    length: float,
    gravity: float = 9.81,
    project_each_step: bool = False,
) -> IntegrationResult:
    """Integrate Cartesian pendulum equations, optionally projecting each step."""
    t = np.asarray(time, dtype=float)
    rhs = cartesian_pendulum_rhs(length, gravity)
    if not project_each_step:
        return rk4_system(rhs, t, np.asarray(initial_state, dtype=float))

    state = project_circle_state(np.asarray(initial_state, dtype=float), length)
    history = np.empty((t.size, 4), dtype=float)
    history[0] = state
    for index, step in enumerate(np.diff(t)):
        ti = float(t[index])
        k1 = rhs(ti, state)
        k2 = rhs(ti + 0.5 * step, state + 0.5 * step * k1)
        k3 = rhs(ti + 0.5 * step, state + 0.5 * step * k2)
        k4 = rhs(ti + step, state + step * k3)
        state = state + step * (k1 + 2.0 * k2 + 2.0 * k3 + k4) / 6.0
        state = project_circle_state(state, length)
        history[index + 1] = state
    return IntegrationResult(t, history)


def circle_constraint_residuals(state: Array, radius: float) -> tuple[Array, Array]:
    """Return normalized position and tangency residuals for a circular constraint."""
    values = np.asarray(state, dtype=float)
    if values.shape[-1] != 4 or radius <= 0.0:
        raise ValueError("state must end with four components and radius must be positive")
    position = values[..., :2]
    velocity = values[..., 2:]
    position_residual = (np.sum(position**2, axis=-1) - radius**2) / radius**2
    tangency_residual = np.sum(position * velocity, axis=-1) / radius**2
    return position_residual, tangency_residual


def kepler_effective_potential(
    radius: Array | float,
    mass: float,
    angular_momentum: float,
    coupling: float,
) -> Array:
    """Return ``L^2/(2 m r^2) - coupling/r`` for an attractive inverse-square force."""
    r = np.asarray(radius, dtype=float)
    if mass <= 0.0 or coupling <= 0.0 or np.any(r <= 0.0):
        raise ValueError("mass, coupling, and radii must be positive")
    return angular_momentum**2 / (2.0 * mass * r**2) - coupling / r


def kepler_circular_radius(mass: float, angular_momentum: float, coupling: float) -> float:
    """Return the positive circular-orbit radius of the Kepler effective potential."""
    if mass <= 0.0 or coupling <= 0.0 or angular_momentum == 0.0:
        raise ValueError("mass and coupling must be positive and angular momentum nonzero")
    return float(angular_momentum**2 / (mass * coupling))


def generalized_normal_modes(mass_matrix: Array, stiffness_matrix: Array) -> tuple[Array, Array]:
    """Solve ``K phi = omega^2 M phi`` with mass-orthonormal eigenvectors."""
    mass = np.asarray(mass_matrix, dtype=float)
    stiffness = np.asarray(stiffness_matrix, dtype=float)
    if mass.ndim != 2 or mass.shape[0] != mass.shape[1] or stiffness.shape != mass.shape:
        raise ValueError("mass and stiffness matrices must be square and have the same shape")
    if not np.allclose(mass, mass.T) or not np.allclose(stiffness, stiffness.T):
        raise ValueError("mass and stiffness matrices must be symmetric")
    cholesky = np.linalg.cholesky(mass)
    inverse_cholesky = np.linalg.inv(cholesky)
    reduced = inverse_cholesky @ stiffness @ inverse_cholesky.T
    eigenvalues, reduced_modes = np.linalg.eigh(reduced)
    if np.any(eigenvalues <= 0.0):
        raise ValueError("the generalized eigenvalues must be positive")
    modes = np.linalg.solve(cholesky.T, reduced_modes)
    for column in range(modes.shape[1]):
        norm = np.sqrt(modes[:, column].T @ mass @ modes[:, column])
        modes[:, column] /= norm
        pivot = int(np.argmax(np.abs(modes[:, column])))
        if modes[pivot, column] < 0.0:
            modes[:, column] *= -1.0
    return np.sqrt(eigenvalues), modes


def modal_time_evolution(
    mass_matrix: Array,
    stiffness_matrix: Array,
    initial_displacement: Array,
    initial_velocity: Array,
    time: Array,
) -> tuple[Array, Array, Array]:
    """Return physical coordinates reconstructed from generalized normal modes."""
    frequencies, modes = generalized_normal_modes(mass_matrix, stiffness_matrix)
    mass = np.asarray(mass_matrix, dtype=float)
    q0 = np.asarray(initial_displacement, dtype=float)
    v0 = np.asarray(initial_velocity, dtype=float)
    t = np.asarray(time, dtype=float)
    if q0.shape != (modes.shape[0],) or v0.shape != q0.shape or t.ndim != 1:
        raise ValueError("initial data and time grid have incompatible shapes")
    cosine_coefficients = modes.T @ mass @ q0
    sine_coefficients = (modes.T @ mass @ v0) / frequencies
    modal_coordinates = (
        cosine_coefficients[:, None] * np.cos(frequencies[:, None] * t[None, :])
        + sine_coefficients[:, None] * np.sin(frequencies[:, None] * t[None, :])
    )
    physical_coordinates = (modes @ modal_coordinates).T
    return physical_coordinates, frequencies, modes


def charged_particle_rhs(
    charge: float,
    mass: float,
    electric_field: Array,
    magnetic_field: Array,
) -> StateRHS:
    """Return the six-dimensional Lorentz-force state equation ``(r, v)``."""
    if mass <= 0.0:
        raise ValueError("mass must be positive")
    electric = np.asarray(electric_field, dtype=float)
    magnetic = np.asarray(magnetic_field, dtype=float)
    if electric.shape != (3,) or magnetic.shape != (3,):
        raise ValueError("electric and magnetic fields must have three components")

    def rhs(_time: float, state: Array) -> Array:
        velocity = state[3:]
        acceleration = (charge / mass) * (electric + np.cross(velocity, magnetic))
        return np.concatenate((velocity, acceleration))

    return rhs


def integrate_charged_particle(
    time: Array,
    initial_position: Array,
    initial_velocity: Array,
    charge: float,
    mass: float,
    electric_field: Array,
    magnetic_field: Array,
) -> IntegrationResult:
    """Integrate a charged-particle trajectory in uniform fields."""
    position = np.asarray(initial_position, dtype=float)
    velocity = np.asarray(initial_velocity, dtype=float)
    if position.shape != (3,) or velocity.shape != (3,):
        raise ValueError("initial position and velocity must have three components")
    state = np.concatenate((position, velocity))
    return rk4_system(
        charged_particle_rhs(charge, mass, electric_field, magnetic_field),
        np.asarray(time, dtype=float),
        state,
    )


def symmetric_gauge_vector_potential(position: Array, magnetic_field: Array) -> Array:
    """Return the symmetric-gauge potential ``A = (1/2) B x r``."""
    r = np.asarray(position, dtype=float)
    magnetic = np.asarray(magnetic_field, dtype=float)
    if r.shape[-1] != 3 or magnetic.shape != (3,):
        raise ValueError("position and magnetic field must have three components")
    return 0.5 * np.cross(magnetic, r)


def canonical_momentum(
    position: Array,
    velocity: Array,
    charge: float,
    mass: float,
    magnetic_field: Array,
) -> Array:
    """Return ``p = m v + q A`` in the symmetric gauge."""
    if mass <= 0.0:
        raise ValueError("mass must be positive")
    v = np.asarray(velocity, dtype=float)
    return mass * v + charge * symmetric_gauge_vector_potential(position, magnetic_field)
