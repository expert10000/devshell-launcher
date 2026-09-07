"""Regression tests for the Chapter 8 computational companion."""
from __future__ import annotations

import unittest
import numpy as np

from kinematics import (
    centered_first_derivative,
    centered_second_derivative,
    closest_approach,
    constant_acceleration_state,
    fit_constant_acceleration,
    monte_carlo_projectile_range,
    polar_state,
    projectile_trajectory,
)


class MotionCompanionTests(unittest.TestCase):
    def test_constant_acceleration(self) -> None:
        state = constant_acceleration_state(np.array([0.0, 2.0]), 1.0, 3.0, -0.5)
        np.testing.assert_allclose(state.position, [1.0, 6.0])
        np.testing.assert_allclose(state.velocity, [3.0, 2.0])

    def test_projectile_lands_on_level_ground(self) -> None:
        speed = 20.0
        angle = 35.0
        flight_time = 2.0 * speed * np.sin(np.deg2rad(angle)) / 9.81
        _, y, _, _ = projectile_trajectory(np.array([0.0, flight_time]), speed, angle)
        self.assertAlmostEqual(float(y[-1]), 0.0, places=11)

    def test_uniform_circular_motion_in_polar_form(self) -> None:
        theta = np.linspace(0.0, 1.0, 7)
        ones = np.ones_like(theta)
        zeros = np.zeros_like(theta)
        _, velocity, acceleration = polar_state(2.0 * ones, theta, zeros, 3.0 * ones, zeros, zeros)
        np.testing.assert_allclose(np.linalg.norm(velocity, axis=1), 6.0)
        np.testing.assert_allclose(np.linalg.norm(acceleration, axis=1), 18.0)

    def test_centered_differences(self) -> None:
        time = np.linspace(0.0, 2.0 * np.pi, 1001)
        dt = float(time[1] - time[0])
        values = np.sin(time)
        first = centered_first_derivative(values, dt)
        second = centered_second_derivative(values, dt)
        np.testing.assert_allclose(first[2:-2], np.cos(time[2:-2]), atol=2e-5)
        np.testing.assert_allclose(second[2:-2], -np.sin(time[2:-2]), atol=4e-5)

    def test_fit_constant_acceleration(self) -> None:
        time = np.linspace(0.0, 5.0, 30)
        position = 2.0 - 1.5 * time + 0.5 * 0.8 * time**2
        x0, v0, acceleration = fit_constant_acceleration(time, position)
        self.assertAlmostEqual(x0, 2.0, places=11)
        self.assertAlmostEqual(v0, -1.5, places=11)
        self.assertAlmostEqual(acceleration, 0.8, places=11)

    def test_closest_approach(self) -> None:
        time, distance = closest_approach(np.array([10.0, 3.0]), np.array([-2.0, 0.0]))
        self.assertAlmostEqual(time, 5.0)
        self.assertAlmostEqual(distance, 3.0)

    def test_monte_carlo_is_deterministic(self) -> None:
        first = monte_carlo_projectile_range(30.0, 0.5, 40.0, 1.0, samples=100, seed=17)
        second = monte_carlo_projectile_range(30.0, 0.5, 40.0, 1.0, samples=100, seed=17)
        np.testing.assert_array_equal(first, second)


if __name__ == "__main__":
    unittest.main()
