"""Numerical building blocks for Chapter 9: Newtonian Mechanics.

The functions mirror the notation used in the textbook and are deliberately
small, deterministic, and reusable.  They support force balances, friction
regimes, coupled systems, circular contact forces, drag, rotating coordinates,
and inverse-dynamics reconstruction from sampled trajectories.
"""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class AtwoodState:
    """Acceleration and ideal-rope tension for a two-mass Atwood machine."""

    acceleration: float
    tension: float


@dataclass(frozen=True)
class FrictionState:
    """Friction force and the active contact regime."""

    force: float
    regime: str


def net_acceleration(forces: np.ndarray, mass: float) -> np.ndarray:
    """Return acceleration from a collection of force vectors."""
    if mass <= 0.0:
        raise ValueError("mass must be positive")
    array = np.asarray(forces, dtype=float)
    if array.ndim == 1:
        net_force = array
    elif array.ndim == 2:
        net_force = np.sum(array, axis=0)
    else:
        raise ValueError("forces must be one vector or an array of vectors")
    return net_force / mass


def friction_force(
    drive_force: float,
    normal_force: float,
    mu_static: float,
    mu_kinetic: float,
    velocity: float = 0.0,
    tolerance: float = 1.0e-12,
) -> FrictionState:
    """Return the one-dimensional Coulomb-friction force.

    Static friction cancels the attempted tangential drive while the required
    magnitude does not exceed ``mu_static * normal_force``.  During sliding,
    kinetic friction opposes the velocity; at a numerically zero velocity it
    opposes the attempted drive.
    """
    if normal_force < 0.0:
        raise ValueError("normal_force must be nonnegative")
    if mu_static < 0.0 or mu_kinetic < 0.0:
        raise ValueError("friction coefficients must be nonnegative")
    static_limit = mu_static * normal_force
    if abs(velocity) <= tolerance and abs(drive_force) <= static_limit:
        return FrictionState(-float(drive_force), "static")
    direction_source = velocity if abs(velocity) > tolerance else drive_force
    if abs(direction_source) <= tolerance:
        return FrictionState(0.0, "kinetic")
    return FrictionState(-mu_kinetic * normal_force * float(np.sign(direction_source)), "kinetic")


def atwood_machine(mass1: float, mass2: float, gravity: float = 9.81) -> AtwoodState:
    """Ideal Atwood-machine acceleration and rope tension.

    Positive acceleration means ``mass2`` moves downward while ``mass1`` moves
    upward.
    """
    if mass1 <= 0.0 or mass2 <= 0.0 or gravity <= 0.0:
        raise ValueError("masses and gravity must be positive")
    acceleration = (mass2 - mass1) * gravity / (mass1 + mass2)
    tension = 2.0 * mass1 * mass2 * gravity / (mass1 + mass2)
    return AtwoodState(float(acceleration), float(tension))


def vertical_circle_contact_force(
    mass: float,
    speed: np.ndarray | float,
    radius: float,
    angle_from_top: np.ndarray | float,
    gravity: float = 9.81,
) -> np.ndarray:
    """Inward contact force required on the inside of a vertical circle.

    ``angle_from_top`` is zero at the top and pi at the bottom.  Positive
    output means the track or string must pull inward; negative output signals
    loss of contact for a unilateral normal force.
    """
    if mass <= 0.0 or radius <= 0.0 or gravity <= 0.0:
        raise ValueError("mass, radius, and gravity must be positive")
    v = np.asarray(speed, dtype=float)
    theta = np.asarray(angle_from_top, dtype=float)
    return mass * v**2 / radius - mass * gravity * np.cos(theta)


def linear_drag_velocity(
    time: np.ndarray | float,
    mass: float,
    drag_coefficient: float,
    gravity: float = 9.81,
    initial_velocity: float = 0.0,
) -> np.ndarray:
    """Downward-positive velocity for gravity with linear drag ``-b v``."""
    if mass <= 0.0 or drag_coefficient <= 0.0 or gravity <= 0.0:
        raise ValueError("mass, drag coefficient, and gravity must be positive")
    t = np.asarray(time, dtype=float)
    terminal = mass * gravity / drag_coefficient
    tau = mass / drag_coefficient
    return terminal + (initial_velocity - terminal) * np.exp(-t / tau)


def rk4_scalar(
    rhs,
    time: np.ndarray,
    initial_value: float,
) -> np.ndarray:
    """Integrate a scalar first-order ODE on an increasing time grid."""
    t = np.asarray(time, dtype=float)
    if t.ndim != 1 or t.size < 2 or np.any(np.diff(t) <= 0.0):
        raise ValueError("time must be a strictly increasing one-dimensional grid")
    values = np.empty_like(t)
    values[0] = initial_value
    for index, step in enumerate(np.diff(t)):
        ti = t[index]
        yi = values[index]
        k1 = rhs(ti, yi)
        k2 = rhs(ti + 0.5 * step, yi + 0.5 * step * k1)
        k3 = rhs(ti + 0.5 * step, yi + 0.5 * step * k2)
        k4 = rhs(ti + step, yi + step * k3)
        values[index + 1] = yi + step * (k1 + 2.0 * k2 + 2.0 * k3 + k4) / 6.0
    return values


def quadratic_drag_velocity(
    time: np.ndarray,
    mass: float,
    drag_coefficient: float,
    gravity: float = 9.81,
    initial_velocity: float = 0.0,
) -> np.ndarray:
    """Numerically integrate downward motion with drag ``-c v |v|``."""
    if mass <= 0.0 or drag_coefficient <= 0.0 or gravity <= 0.0:
        raise ValueError("mass, drag coefficient, and gravity must be positive")

    def rhs(_time: float, velocity: float) -> float:
        return gravity - (drag_coefficient / mass) * velocity * abs(velocity)

    return rk4_scalar(rhs, np.asarray(time, dtype=float), initial_velocity)


def rotating_coordinates(
    inertial_position: np.ndarray,
    time: np.ndarray,
    angular_speed: float,
) -> np.ndarray:
    """Express planar inertial positions in axes rotating counterclockwise."""
    position = np.asarray(inertial_position, dtype=float)
    t = np.asarray(time, dtype=float)
    if position.shape != (t.size, 2):
        raise ValueError("inertial_position must have shape (len(time), 2)")
    angle = angular_speed * t
    cosine = np.cos(angle)
    sine = np.sin(angle)
    x = cosine * position[:, 0] + sine * position[:, 1]
    y = -sine * position[:, 0] + cosine * position[:, 1]
    return np.column_stack((x, y))


def rotating_frame_inertial_acceleration(
    position: np.ndarray,
    relative_velocity: np.ndarray,
    angular_velocity: np.ndarray,
    angular_acceleration: np.ndarray | None = None,
    origin_acceleration: np.ndarray | None = None,
) -> dict[str, np.ndarray]:
    """Return translational, Coriolis, Euler, and centrifugal accelerations."""
    r = np.asarray(position, dtype=float)
    v = np.asarray(relative_velocity, dtype=float)
    omega = np.asarray(angular_velocity, dtype=float)
    alpha = np.zeros(3) if angular_acceleration is None else np.asarray(angular_acceleration, dtype=float)
    origin = np.zeros(3) if origin_acceleration is None else np.asarray(origin_acceleration, dtype=float)
    for vector in (r, v, omega, alpha, origin):
        if vector.shape != (3,):
            raise ValueError("all rotating-frame vectors must have three components")
    return {
        "translational": -origin,
        "coriolis": -2.0 * np.cross(omega, v),
        "euler": -np.cross(alpha, r),
        "centrifugal": -np.cross(omega, np.cross(omega, r)),
    }


def reconstruct_force_polynomial(
    time: np.ndarray,
    position: np.ndarray,
    mass: float,
    degree: int = 4,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Fit a polynomial trajectory and reconstruct acceleration and force."""
    if mass <= 0.0:
        raise ValueError("mass must be positive")
    t = np.asarray(time, dtype=float)
    x = np.asarray(position, dtype=float)
    if t.ndim != 1 or x.ndim != 1 or t.size != x.size:
        raise ValueError("time and position must be equal-length one-dimensional arrays")
    if degree < 2 or degree >= t.size:
        raise ValueError("degree must be at least 2 and smaller than the sample count")
    coefficients = np.polyfit(t, x, degree)
    fitted_position = np.polyval(coefficients, t)
    acceleration = np.polyval(np.polyder(coefficients, 2), t)
    force = mass * acceleration
    return fitted_position, acceleration, force
