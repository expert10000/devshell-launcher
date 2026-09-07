"""Numerical building blocks for Chapter 8: Motion.

The functions are deliberately small, deterministic, and expressed in the
same notation used in the text.  They can be imported independently from the
plot-generating companion.
"""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class ConstantAccelerationState:
    """Position, velocity, and acceleration at one time."""

    position: np.ndarray
    velocity: np.ndarray
    acceleration: np.ndarray


def constant_acceleration_state(
    t: np.ndarray | float,
    position0: np.ndarray | float,
    velocity0: np.ndarray | float,
    acceleration: np.ndarray | float,
) -> ConstantAccelerationState:
    """Evaluate r(t), v(t), and a(t) for constant acceleration."""
    t_arr = np.asarray(t, dtype=float)
    r0 = np.asarray(position0, dtype=float)
    v0 = np.asarray(velocity0, dtype=float)
    a = np.asarray(acceleration, dtype=float)
    if r0.ndim == 0:
        position = r0 + v0 * t_arr + 0.5 * a * t_arr**2
        velocity = v0 + a * t_arr
    else:
        tau = np.expand_dims(t_arr, axis=-1)
        position = r0 + v0 * tau + 0.5 * a * tau**2
        velocity = v0 + a * tau
    return ConstantAccelerationState(position, velocity, np.broadcast_to(a, np.shape(velocity)))


def projectile_trajectory(
    t: np.ndarray,
    speed: float,
    angle_deg: float,
    origin: tuple[float, float] = (0.0, 0.0),
    gravity: float = 9.81,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Return x, y, vx, and vy for ideal projectile motion."""
    t = np.asarray(t, dtype=float)
    angle = np.deg2rad(angle_deg)
    vx0 = speed * np.cos(angle)
    vy0 = speed * np.sin(angle)
    x = origin[0] + vx0 * t
    y = origin[1] + vy0 * t - 0.5 * gravity * t**2
    vx = np.full_like(t, vx0)
    vy = vy0 - gravity * t
    return x, y, vx, vy


def polar_state(
    r: np.ndarray,
    theta: np.ndarray,
    r_dot: np.ndarray,
    theta_dot: np.ndarray,
    r_ddot: np.ndarray,
    theta_ddot: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Convert polar position, velocity, and acceleration to Cartesian form."""
    r = np.asarray(r, dtype=float)
    theta = np.asarray(theta, dtype=float)
    r_dot = np.asarray(r_dot, dtype=float)
    theta_dot = np.asarray(theta_dot, dtype=float)
    r_ddot = np.asarray(r_ddot, dtype=float)
    theta_ddot = np.asarray(theta_ddot, dtype=float)

    e_r = np.column_stack((np.cos(theta), np.sin(theta)))
    e_theta = np.column_stack((-np.sin(theta), np.cos(theta)))
    position = r[:, None] * e_r
    velocity = r_dot[:, None] * e_r + (r * theta_dot)[:, None] * e_theta
    acceleration = (
        (r_ddot - r * theta_dot**2)[:, None] * e_r
        + (r * theta_ddot + 2.0 * r_dot * theta_dot)[:, None] * e_theta
    )
    return position, velocity, acceleration


def centered_first_derivative(values: np.ndarray, dt: float) -> np.ndarray:
    """Second-order centered first derivative with one-sided end points."""
    values = np.asarray(values, dtype=float)
    if values.shape[0] < 3:
        raise ValueError("At least three samples are required")
    derivative = np.empty_like(values)
    derivative[1:-1] = (values[2:] - values[:-2]) / (2.0 * dt)
    derivative[0] = (-3.0 * values[0] + 4.0 * values[1] - values[2]) / (2.0 * dt)
    derivative[-1] = (3.0 * values[-1] - 4.0 * values[-2] + values[-3]) / (2.0 * dt)
    return derivative


def centered_second_derivative(values: np.ndarray, dt: float) -> np.ndarray:
    """Second-order centered second derivative with quadratic end formulas."""
    values = np.asarray(values, dtype=float)
    if values.shape[0] < 4:
        raise ValueError("At least four samples are required")
    derivative = np.empty_like(values)
    derivative[1:-1] = (values[2:] - 2.0 * values[1:-1] + values[:-2]) / dt**2
    derivative[0] = (2.0 * values[0] - 5.0 * values[1] + 4.0 * values[2] - values[3]) / dt**2
    derivative[-1] = (2.0 * values[-1] - 5.0 * values[-2] + 4.0 * values[-3] - values[-4]) / dt**2
    return derivative


def fit_constant_acceleration(time: np.ndarray, position: np.ndarray) -> tuple[float, float, float]:
    """Least-squares estimate of x0, v0, and a from sampled positions."""
    time = np.asarray(time, dtype=float)
    position = np.asarray(position, dtype=float)
    if time.ndim != 1 or position.ndim != 1 or time.size != position.size:
        raise ValueError("time and position must be one-dimensional arrays of equal length")
    design = np.column_stack((np.ones_like(time), time, 0.5 * time**2))
    x0, v0, acceleration = np.linalg.lstsq(design, position, rcond=None)[0]
    return float(x0), float(v0), float(acceleration)


def projectile_range(speed: float, angle_rad: np.ndarray, gravity: float = 9.81) -> np.ndarray:
    """Range for level-ground projectile motion."""
    return speed**2 * np.sin(2.0 * np.asarray(angle_rad, dtype=float)) / gravity


def monte_carlo_projectile_range(
    speed_mean: float,
    speed_sigma: float,
    angle_mean_deg: float,
    angle_sigma_deg: float,
    samples: int = 20_000,
    seed: int = 20260729,
    gravity: float = 9.81,
) -> np.ndarray:
    """Draw a deterministic Monte Carlo ensemble of projectile ranges."""
    if samples <= 0:
        raise ValueError("samples must be positive")
    rng = np.random.default_rng(seed)
    speeds = rng.normal(speed_mean, speed_sigma, samples)
    angles = np.deg2rad(rng.normal(angle_mean_deg, angle_sigma_deg, samples))
    return projectile_range(speeds, angles, gravity)


def closest_approach(
    relative_position0: np.ndarray,
    relative_velocity: np.ndarray,
) -> tuple[float, float]:
    """Return time and distance of closest approach for uniform relative motion."""
    r0 = np.asarray(relative_position0, dtype=float)
    velocity = np.asarray(relative_velocity, dtype=float)
    speed_squared = float(velocity @ velocity)
    if speed_squared == 0.0:
        return 0.0, float(np.linalg.norm(r0))
    time = max(0.0, -float(r0 @ velocity) / speed_squared)
    distance = float(np.linalg.norm(r0 + velocity * time))
    return time, distance
