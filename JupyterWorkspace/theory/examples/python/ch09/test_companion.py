"""Regression tests for the Chapter 9 computational companion."""
from __future__ import annotations

import unittest
import numpy as np

from newtonian_dynamics import (
    atwood_machine,
    friction_force,
    linear_drag_velocity,
    net_acceleration,
    quadratic_drag_velocity,
    reconstruct_force_polynomial,
    rotating_coordinates,
    rotating_frame_inertial_acceleration,
    vertical_circle_contact_force,
)


class NewtonianCompanionTests(unittest.TestCase):
    def test_net_acceleration_superposition(self) -> None:
        forces = np.array([[3.0, 4.0], [-1.0, 2.0]])
        np.testing.assert_allclose(net_acceleration(forces, 2.0), [1.0, 3.0])

    def test_static_and_kinetic_friction(self) -> None:
        static = friction_force(4.0, 10.0, 0.6, 0.4)
        kinetic = friction_force(8.0, 10.0, 0.6, 0.4)
        self.assertEqual(static.regime, "static")
        self.assertAlmostEqual(static.force, -4.0)
        self.assertEqual(kinetic.regime, "kinetic")
        self.assertAlmostEqual(kinetic.force, -4.0)

    def test_atwood_machine_equations(self) -> None:
        state = atwood_machine(2.0, 5.0)
        self.assertAlmostEqual(state.acceleration, 3.0 * 9.81 / 7.0)
        self.assertAlmostEqual(state.tension, 20.0 * 9.81 / 7.0)

    def test_vertical_circle_contact_threshold(self) -> None:
        radius = 2.0
        speed = np.sqrt(9.81 * radius)
        top_contact = vertical_circle_contact_force(1.0, speed, radius, 0.0)
        self.assertAlmostEqual(float(top_contact), 0.0, places=11)

    def test_linear_drag_terminal_limit(self) -> None:
        velocity = linear_drag_velocity(np.array([0.0, 100.0]), 10.0, 2.0)
        self.assertAlmostEqual(float(velocity[0]), 0.0)
        self.assertAlmostEqual(float(velocity[-1]), 49.05, places=6)

    def test_quadratic_drag_approaches_terminal_speed(self) -> None:
        time = np.linspace(0.0, 60.0, 6001)
        velocity = quadratic_drag_velocity(time, 10.0, 0.5)
        terminal = np.sqrt(10.0 * 9.81 / 0.5)
        self.assertAlmostEqual(float(velocity[-1]), float(terminal), places=5)

    def test_rotating_coordinate_norm_is_preserved(self) -> None:
        time = np.linspace(0.0, 4.0, 21)
        inertial = np.column_stack((1.0 + time, 2.0 - 0.3 * time))
        rotating = rotating_coordinates(inertial, time, 0.7)
        np.testing.assert_allclose(
            np.linalg.norm(inertial, axis=1), np.linalg.norm(rotating, axis=1), atol=1.0e-12
        )

    def test_rotating_frame_terms(self) -> None:
        terms = rotating_frame_inertial_acceleration(
            position=np.array([2.0, 0.0, 0.0]),
            relative_velocity=np.array([0.0, 3.0, 0.0]),
            angular_velocity=np.array([0.0, 0.0, 0.5]),
        )
        np.testing.assert_allclose(terms["coriolis"], [3.0, 0.0, 0.0])
        np.testing.assert_allclose(terms["centrifugal"], [0.5, 0.0, 0.0])

    def test_polynomial_force_reconstruction(self) -> None:
        time = np.linspace(0.0, 5.0, 41)
        position = 2.0 + 1.5 * time - 0.4 * time**2 + 0.02 * time**4
        _, acceleration, force = reconstruct_force_polynomial(time, position, mass=3.0, degree=4)
        exact_acceleration = -0.8 + 0.24 * time**2
        np.testing.assert_allclose(acceleration, exact_acceleration, atol=1.0e-10)
        np.testing.assert_allclose(force, 3.0 * exact_acceleration, atol=3.0e-10)


if __name__ == "__main__":
    unittest.main()
