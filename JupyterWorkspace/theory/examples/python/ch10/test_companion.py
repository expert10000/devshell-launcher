"""Regression tests for the Chapter 10 Python computational companion."""
from __future__ import annotations

import unittest

import numpy as np
import sympy as sp

from lagrangian_dynamics import (
    canonical_momentum,
    circle_constraint_residuals,
    euler_lagrange_residuals,
    generalized_normal_modes,
    integrate_cartesian_pendulum,
    integrate_charged_particle,
    kepler_circular_radius,
    kepler_effective_potential,
    modal_time_evolution,
    pendulum_energy,
    pendulum_period_quadrature,
    pendulum_rhs,
    project_circle_state,
    rk4_system,
    solve_accelerations,
)


class Chapter10CompanionTests(unittest.TestCase):
    def test_symbolic_pendulum_euler_lagrange_equation(self) -> None:
        q, qd, qdd, m, length, gravity, time = sp.symbols("q qd qdd m l g t")
        lagrangian = sp.Rational(1, 2) * m * length**2 * qd**2 + m * gravity * length * sp.cos(q)
        residual = euler_lagrange_residuals(lagrangian, (q,), (qd,), (qdd,), time)[0]
        expected = m * length**2 * qdd + m * gravity * length * sp.sin(q)
        self.assertEqual(sp.simplify(residual - expected), 0)
        solution = solve_accelerations((residual,), (qdd,))
        self.assertEqual(sp.simplify(solution[qdd] + gravity * sp.sin(q) / length), 0)

    def test_explicit_time_total_derivative(self) -> None:
        q, qd, qdd, m, time = sp.symbols("q qd qdd m t")
        lagrangian = sp.Rational(1, 2) * m * sp.exp(time) * qd**2
        residual = euler_lagrange_residuals(lagrangian, (q,), (qd,), (qdd,), time)[0]
        self.assertEqual(sp.simplify(residual - m * sp.exp(time) * (qdd + qd)), 0)

    def test_rk4_harmonic_oscillator_accuracy(self) -> None:
        time = np.linspace(0.0, 2.0 * np.pi, 1001)
        result = rk4_system(
            lambda _t, state: np.array([state[1], -state[0]]),
            time,
            np.array([1.0, 0.0]),
        )
        np.testing.assert_allclose(result.state[-1], [1.0, 0.0], atol=2.0e-9)

    def test_pendulum_energy_is_nearly_conserved(self) -> None:
        time = np.linspace(0.0, 20.0, 4001)
        result = rk4_system(pendulum_rhs(1.0), time, np.array([1.0, 0.0]))
        energy = pendulum_energy(result.state, 1.0, 1.0)
        relative = np.max(np.abs((energy - energy[0]) / energy[0]))
        self.assertLess(float(relative), 2.0e-8)

    def test_pendulum_period_small_amplitude_limit(self) -> None:
        period = pendulum_period_quadrature(1.0e-4, 2.0, gravity=9.81)
        expected = 2.0 * np.pi * np.sqrt(2.0 / 9.81)
        self.assertAlmostEqual(period, expected, places=7)

    def test_circle_projection_enforces_position_and_tangency(self) -> None:
        projected = project_circle_state(np.array([0.8, -0.3, 1.2, 0.7]), 1.0)
        position_residual, tangency_residual = circle_constraint_residuals(projected, 1.0)
        self.assertLess(abs(float(position_residual)), 2.0e-15)
        self.assertLess(abs(float(tangency_residual)), 2.0e-15)

    def test_projected_cartesian_pendulum_controls_constraint_drift(self) -> None:
        theta0 = 1.0
        initial = np.array([np.sin(theta0), -np.cos(theta0), 0.0, 0.0])
        time = np.linspace(0.0, 20.0, 501)
        result = integrate_cartesian_pendulum(time, initial, 1.0, project_each_step=True)
        position_residual, tangency_residual = circle_constraint_residuals(result.state, 1.0)
        self.assertLess(float(np.max(np.abs(position_residual))), 2.0e-14)
        self.assertLess(float(np.max(np.abs(tangency_residual))), 2.0e-14)

    def test_kepler_effective_potential_has_expected_minimum(self) -> None:
        radius = kepler_circular_radius(2.0, 3.0, 4.0)
        self.assertAlmostEqual(radius, 9.0 / 8.0)
        epsilon = 1.0e-5
        left = kepler_effective_potential(radius - epsilon, 2.0, 3.0, 4.0)
        center = kepler_effective_potential(radius, 2.0, 3.0, 4.0)
        right = kepler_effective_potential(radius + epsilon, 2.0, 3.0, 4.0)
        self.assertLess(float(center), float(left))
        self.assertLess(float(center), float(right))

    def test_generalized_modes_are_mass_orthonormal(self) -> None:
        mass = np.diag([2.0, 1.0])
        stiffness = np.array([[5.0, -2.0], [-2.0, 6.0]])
        frequencies, modes = generalized_normal_modes(mass, stiffness)
        np.testing.assert_allclose(modes.T @ mass @ modes, np.eye(2), atol=1.0e-12)
        np.testing.assert_allclose(
            stiffness @ modes,
            mass @ modes @ np.diag(frequencies**2),
            atol=1.0e-12,
        )

    def test_modal_reconstruction_matches_initial_data(self) -> None:
        mass = np.diag([2.0, 1.0])
        stiffness = np.array([[5.0, -2.0], [-2.0, 6.0]])
        q0 = np.array([0.3, -0.2])
        v0 = np.array([0.1, 0.05])
        time = np.array([0.0, 1.0e-6])
        coordinates, _, _ = modal_time_evolution(mass, stiffness, q0, v0, time)
        np.testing.assert_allclose(coordinates[0], q0, atol=1.0e-12)
        np.testing.assert_allclose((coordinates[1] - coordinates[0]) / 1.0e-6, v0, atol=2.0e-6)

    def test_uniform_magnetic_field_preserves_speed(self) -> None:
        time = np.linspace(0.0, 4.0 * np.pi, 4001)
        result = integrate_charged_particle(
            time,
            np.zeros(3),
            np.array([1.0, 0.0, 0.0]),
            charge=1.0,
            mass=1.0,
            electric_field=np.zeros(3),
            magnetic_field=np.array([0.0, 0.0, 1.0]),
        )
        speed = np.linalg.norm(result.state[:, 3:], axis=1)
        self.assertLess(float(np.max(np.abs(speed - 1.0))), 2.0e-11)
        np.testing.assert_allclose(result.state[-1, :2], [0.0, 0.0], atol=2.0e-10)

    def test_crossed_field_drift_matches_e_cross_b(self) -> None:
        time = np.linspace(0.0, 16.0 * np.pi, 8001)
        electric = np.array([0.2, 0.0, 0.0])
        magnetic = np.array([0.0, 0.0, 1.0])
        result = integrate_charged_particle(
            time,
            np.zeros(3),
            np.array([1.0, 0.0, 0.0]),
            charge=1.0,
            mass=1.0,
            electric_field=electric,
            magnetic_field=magnetic,
        )
        drift = result.state[-1, :3] / time[-1]
        expected = np.cross(electric, magnetic) / np.dot(magnetic, magnetic)
        np.testing.assert_allclose(drift, expected, atol=2.0e-10)

    def test_canonical_momentum_includes_vector_potential(self) -> None:
        momentum = canonical_momentum(
            position=np.array([2.0, 0.0, 0.0]),
            velocity=np.array([1.0, 0.0, 0.0]),
            charge=3.0,
            mass=2.0,
            magnetic_field=np.array([0.0, 0.0, 4.0]),
        )
        np.testing.assert_allclose(momentum, [2.0, 12.0, 0.0])


if __name__ == "__main__":
    unittest.main()
