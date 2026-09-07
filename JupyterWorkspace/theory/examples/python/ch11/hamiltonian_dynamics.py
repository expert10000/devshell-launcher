"""Reusable symbolic and numerical tools for Chapter 11 Hamiltonian mechanics.

The module intentionally keeps the algorithms explicit.  It is designed for
small deterministic examples, regression tests, and figure generation rather
than as a replacement for a production scientific-computing library.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

import numpy as np
import sympy as sp

Array = np.ndarray
VectorField = Callable[[float, Array], Array]


def poisson_bracket(
    f: sp.Expr,
    g: sp.Expr,
    coordinates: Iterable[sp.Symbol],
    momenta: Iterable[sp.Symbol],
) -> sp.Expr:
    """Return the canonical Poisson bracket {f,g}."""
    qs = tuple(coordinates)
    ps = tuple(momenta)
    if len(qs) != len(ps):
        raise ValueError("coordinates and momenta must have equal length")
    return sp.simplify(
        sum(sp.diff(f, q) * sp.diff(g, p) - sp.diff(f, p) * sp.diff(g, q)
            for q, p in zip(qs, ps))
    )


def legendre_transform_1d(
    lagrangian: sp.Expr,
    coordinate: sp.Symbol,
    velocity: sp.Symbol,
    momentum: sp.Symbol,
) -> tuple[sp.Expr, sp.Expr]:
    """Perform a regular one-dimensional Legendre transform.

    Returns ``(hamiltonian, velocity_as_function_of_q_p)``.  A ValueError is
    raised when SymPy cannot isolate a unique velocity branch.
    """
    equation = sp.Eq(sp.diff(lagrangian, velocity), momentum)
    branches = sp.solve(equation, velocity, dict=False)
    if len(branches) != 1:
        raise ValueError("Legendre map is not uniquely invertible")
    velocity_solution = sp.simplify(branches[0])
    hamiltonian = sp.simplify(
        momentum * velocity_solution
        - lagrangian.subs(velocity, velocity_solution)
    )
    return hamiltonian, velocity_solution


def canonical_symplectic_matrix(degrees_of_freedom: int) -> Array:
    """Return J = [[0,I],[-I,0]] for canonical ordering (q,p)."""
    if degrees_of_freedom < 1:
        raise ValueError("degrees_of_freedom must be positive")
    identity = np.eye(degrees_of_freedom)
    zero = np.zeros_like(identity)
    return np.block([[zero, identity], [-identity, zero]])


def symplectic_defect(matrix: Array) -> float:
    """Frobenius norm of M.T J M - J."""
    matrix = np.asarray(matrix, dtype=float)
    if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1]:
        raise ValueError("matrix must be square")
    if matrix.shape[0] % 2:
        raise ValueError("phase-space dimension must be even")
    j_matrix = canonical_symplectic_matrix(matrix.shape[0] // 2)
    return float(np.linalg.norm(matrix.T @ j_matrix @ matrix - j_matrix))


def finite_difference_jacobian(
    mapping: Callable[[Array], Array],
    point: Array,
    epsilon: float = 1.0e-7,
) -> Array:
    """Centered finite-difference Jacobian of a vector mapping."""
    point = np.asarray(point, dtype=float)
    base = np.asarray(mapping(point), dtype=float)
    jacobian = np.empty((base.size, point.size), dtype=float)
    for column in range(point.size):
        step = np.zeros_like(point)
        step[column] = epsilon
        jacobian[:, column] = (
            np.asarray(mapping(point + step))
            - np.asarray(mapping(point - step))
        ) / (2.0 * epsilon)
    return jacobian


def canonical_map_defect(
    mapping: Callable[[Array], Array],
    point: Array,
    epsilon: float = 1.0e-7,
) -> float:
    """Numerically test whether a differentiable map is symplectic at a point."""
    return symplectic_defect(finite_difference_jacobian(mapping, point, epsilon))


def rk4_step(field: VectorField, time: float, state: Array, step: float) -> Array:
    """One classical fourth-order Runge--Kutta step."""
    y = np.asarray(state, dtype=float)
    k1 = np.asarray(field(time, y))
    k2 = np.asarray(field(time + step / 2.0, y + step * k1 / 2.0))
    k3 = np.asarray(field(time + step / 2.0, y + step * k2 / 2.0))
    k4 = np.asarray(field(time + step, y + step * k3))
    return y + step * (k1 + 2.0 * k2 + 2.0 * k3 + k4) / 6.0


def explicit_euler_step(field: VectorField, time: float, state: Array, step: float) -> Array:
    """One explicit Euler step, included as a non-symplectic reference."""
    return np.asarray(state, dtype=float) + step * np.asarray(field(time, state))


def symplectic_euler_step(
    d_t_dp: Callable[[Array], Array],
    d_v_dq: Callable[[Array], Array],
    state: Array,
    step: float,
) -> Array:
    """Momentum-first symplectic Euler for H(q,p)=T(p)+V(q)."""
    state = np.asarray(state, dtype=float)
    half = state.size // 2
    q = state[:half].copy()
    p = state[half:].copy()
    p_new = p - step * np.asarray(d_v_dq(q), dtype=float)
    q_new = q + step * np.asarray(d_t_dp(p_new), dtype=float)
    return np.concatenate((q_new, p_new))


def velocity_verlet_step(
    acceleration: Callable[[Array], Array],
    state: Array,
    step: float,
) -> Array:
    """Velocity-Verlet step for unit canonical mass scaling."""
    state = np.asarray(state, dtype=float)
    half = state.size // 2
    q = state[:half].copy()
    v = state[half:].copy()
    a0 = np.asarray(acceleration(q), dtype=float)
    q_new = q + step * v + 0.5 * step * step * a0
    a1 = np.asarray(acceleration(q_new), dtype=float)
    v_new = v + 0.5 * step * (a0 + a1)
    return np.concatenate((q_new, v_new))


def integrate_fixed_step(
    stepper: Callable[[float, Array, float], Array],
    initial_state: Array,
    time_grid: Array,
) -> Array:
    """Integrate a fixed-step map over a uniform time grid."""
    times = np.asarray(time_grid, dtype=float)
    if times.ndim != 1 or times.size < 2:
        raise ValueError("time_grid must be a one-dimensional array")
    steps = np.diff(times)
    if not np.allclose(steps, steps[0]):
        raise ValueError("time_grid must be uniform")
    states = np.empty((times.size, np.asarray(initial_state).size), dtype=float)
    states[0] = initial_state
    for index, time in enumerate(times[:-1]):
        states[index + 1] = stepper(time, states[index], steps[0])
    return states


def oscillator_field(time: float, state: Array, *, mass: float = 1.0, omega: float = 1.0) -> Array:
    del time
    q, p = np.asarray(state, dtype=float)
    return np.array([p / mass, -mass * omega * omega * q])


def oscillator_energy(states: Array, *, mass: float = 1.0, omega: float = 1.0) -> Array:
    states = np.asarray(states, dtype=float)
    q = states[..., 0]
    p = states[..., 1]
    return p * p / (2.0 * mass) + 0.5 * mass * omega * omega * q * q


def oscillator_exact_matrix(time: float, *, mass: float = 1.0, omega: float = 1.0) -> Array:
    c = np.cos(omega * time)
    s = np.sin(omega * time)
    return np.array([[c, s / (mass * omega)], [-mass * omega * s, c]])


def oscillator_to_action_angle(state: Array, *, mass: float = 1.0, omega: float = 1.0) -> tuple[float, float]:
    q, p = np.asarray(state, dtype=float)
    energy = float(oscillator_energy(np.array([q, p]), mass=mass, omega=omega))
    action = energy / omega
    theta = float(np.arctan2(np.sqrt(mass * omega) * q, p / np.sqrt(mass * omega)))
    return action, theta


def oscillator_from_action_angle(action: float, theta: float, *, mass: float = 1.0, omega: float = 1.0) -> Array:
    if action < 0:
        raise ValueError("action must be nonnegative")
    q = np.sqrt(2.0 * action / (mass * omega)) * np.sin(theta)
    p = np.sqrt(2.0 * mass * omega * action) * np.cos(theta)
    return np.array([q, p])


def pendulum_field(time: float, state: Array, *, gravity: float = 1.0, length: float = 1.0, mass: float = 1.0) -> Array:
    del time
    theta, momentum = np.asarray(state, dtype=float)
    return np.array([
        momentum / (mass * length * length),
        -mass * gravity * length * np.sin(theta),
    ])


def pendulum_energy(states: Array, *, gravity: float = 1.0, length: float = 1.0, mass: float = 1.0) -> Array:
    states = np.asarray(states, dtype=float)
    theta = states[..., 0]
    momentum = states[..., 1]
    return momentum * momentum / (2.0 * mass * length * length) + mass * gravity * length * (1.0 - np.cos(theta))


def kepler_field(time: float, state: Array, *, mass: float = 1.0, strength: float = 1.0) -> Array:
    del time
    x, y, px, py = np.asarray(state, dtype=float)
    radius = np.hypot(x, y)
    if radius == 0.0:
        raise ValueError("Kepler field is singular at the origin")
    factor = -strength / radius**3
    return np.array([px / mass, py / mass, factor * x, factor * y])


def kepler_invariants(states: Array, *, mass: float = 1.0, strength: float = 1.0) -> tuple[Array, Array, Array]:
    states = np.asarray(states, dtype=float)
    x, y, px, py = np.moveaxis(states, -1, 0)
    radius = np.hypot(x, y)
    energy = (px * px + py * py) / (2.0 * mass) - strength / radius
    angular_momentum = x * py - y * px
    # Planar Runge--Lenz vector A = p x L - m k r_hat.
    ax = py * angular_momentum - mass * strength * x / radius
    ay = -px * angular_momentum - mass * strength * y / radius
    return energy, angular_momentum, np.stack((ax, ay), axis=-1)


def standard_map(theta: Array, momentum: Array, kick: float) -> tuple[Array, Array]:
    """One symplectic kicked-rotor map, with angles wrapped to [-pi,pi)."""
    p_new = np.asarray(momentum) + kick * np.sin(theta)
    theta_new = np.asarray(theta) + p_new
    theta_new = (theta_new + np.pi) % (2.0 * np.pi) - np.pi
    p_new = (p_new + np.pi) % (2.0 * np.pi) - np.pi
    return theta_new, p_new


def polygon_area(points: Array) -> float:
    """Signed area of an ordered planar polygon."""
    points = np.asarray(points, dtype=float)
    x = points[:, 0]
    y = points[:, 1]
    return 0.5 * float(np.sum(x * np.roll(y, -1) - y * np.roll(x, -1)))


@dataclass(frozen=True)
class IntegratorDiagnostic:
    method: str
    step: float
    maximum_relative_energy_error: float
    final_state_error: float
