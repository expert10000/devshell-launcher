"""Regression tests for the Chapter 11 computational companion."""
from __future__ import annotations

import unittest

import numpy as np
import sympy as sp

from hamiltonian_dynamics import (
    canonical_map_defect,
    canonical_symplectic_matrix,
    explicit_euler_step,
    finite_difference_jacobian,
    integrate_fixed_step,
    kepler_field,
    kepler_invariants,
    legendre_transform_1d,
    oscillator_energy,
    oscillator_exact_matrix,
    oscillator_field,
    oscillator_from_action_angle,
    oscillator_to_action_angle,
    pendulum_energy,
    pendulum_field,
    poisson_bracket,
    polygon_area,
    rk4_step,
    standard_map,
    symplectic_defect,
    symplectic_euler_step,
    velocity_verlet_step,
)


class HamiltonianCompanionTests(unittest.TestCase):
    def test_poisson_canonical_pair(self):
        q, p = sp.symbols("q p")
        self.assertEqual(poisson_bracket(q, p, [q], [p]), 1)

    def test_poisson_antisymmetry(self):
        q, p = sp.symbols("q p")
        f = q**2 * p
        g = sp.sin(q) + p**2
        self.assertEqual(sp.simplify(poisson_bracket(f, g, [q], [p]) + poisson_bracket(g, f, [q], [p])), 0)

    def test_legendre_transform_oscillator(self):
        q, v, p, m, w = sp.symbols("q v p m w", nonzero=True)
        lagrangian = m * v**2 / 2 - m * w**2 * q**2 / 2
        hamiltonian, velocity = legendre_transform_1d(lagrangian, q, v, p)
        self.assertEqual(sp.simplify(velocity - p / m), 0)
        self.assertEqual(sp.simplify(hamiltonian - (p**2 / (2 * m) + m * w**2 * q**2 / 2)), 0)

    def test_canonical_matrix_is_symplectic(self):
        j = canonical_symplectic_matrix(2)
        self.assertLess(symplectic_defect(j), 1.0e-14)

    def test_noncanonical_scaling_detected(self):
        matrix = np.diag([2.0, 2.0])
        self.assertGreater(symplectic_defect(matrix), 1.0)

    def test_finite_difference_canonical_map(self):
        mapping = lambda z: np.array([1.7 * z[0], z[1] / 1.7])
        self.assertLess(canonical_map_defect(mapping, np.array([0.2, -0.8])), 1.0e-8)

    def test_rk4_oscillator_accuracy(self):
        step = 0.01
        times = np.arange(0.0, 2.0 + step / 2.0, step)
        field = lambda time, state: oscillator_field(time, state)
        states = integrate_fixed_step(lambda t, y, h: rk4_step(field, t, y, h), np.array([1.0, 0.0]), times)
        exact = oscillator_exact_matrix(times[-1]) @ np.array([1.0, 0.0])
        self.assertLess(np.linalg.norm(states[-1] - exact), 1.0e-8)

    def test_symplectic_euler_energy_is_bounded(self):
        step = 0.08
        times = np.arange(0.0, 200.0 + step / 2.0, step)
        states = integrate_fixed_step(
            lambda t, y, h: symplectic_euler_step(lambda p: p, lambda q: q, y, h),
            np.array([1.0, 0.0]),
            times,
        )
        error = np.max(np.abs(oscillator_energy(states) - 0.5))
        self.assertLess(error, 0.03)

    def test_explicit_euler_energy_grows(self):
        step = 0.08
        times = np.arange(0.0, 40.0 + step / 2.0, step)
        field = lambda time, state: oscillator_field(time, state)
        states = integrate_fixed_step(lambda t, y, h: explicit_euler_step(field, t, y, h), np.array([1.0, 0.0]), times)
        self.assertGreater(oscillator_energy(states[-1]), 2.0)

    def test_velocity_verlet_time_reversal(self):
        state = np.array([0.8, -0.3])
        forward = velocity_verlet_step(lambda q: -q, state, 0.04)
        reversed_state = forward.copy()
        reversed_state[1] *= -1.0
        backward_motion = velocity_verlet_step(lambda q: -q, reversed_state, 0.04)
        backward_motion[1] *= -1.0
        self.assertLess(np.linalg.norm(backward_motion - state), 1.0e-12)

    def test_phase_space_area_preserved(self):
        angle = np.linspace(0.0, 2.0 * np.pi, 300, endpoint=False)
        polygon = np.column_stack((1.2 * np.cos(angle), 0.7 * np.sin(angle)))
        mapped = polygon @ oscillator_exact_matrix(1.3).T
        self.assertAlmostEqual(abs(polygon_area(polygon)), abs(polygon_area(mapped)), places=11)

    def test_action_angle_roundtrip(self):
        state = np.array([0.72, -0.41])
        action, theta = oscillator_to_action_angle(state)
        reconstructed = oscillator_from_action_angle(action, theta)
        self.assertLess(np.linalg.norm(reconstructed - state), 1.0e-12)

    def test_pendulum_rk4_energy(self):
        step = 0.005
        times = np.arange(0.0, 10.0 + step / 2.0, step)
        field = lambda time, state: pendulum_field(time, state)
        states = integrate_fixed_step(lambda t, y, h: rk4_step(field, t, y, h), np.array([0.9, 0.0]), times)
        energy = pendulum_energy(states)
        self.assertLess(np.max(np.abs(energy - energy[0])), 1.0e-10)

    def test_kepler_invariants(self):
        step = 0.002
        times = np.arange(0.0, 8.0 + step / 2.0, step)
        field = lambda time, state: kepler_field(time, state)
        states = integrate_fixed_step(lambda t, y, h: rk4_step(field, t, y, h), np.array([1.0, 0.0, 0.0, 0.82]), times)
        energy, angular, runge_lenz = kepler_invariants(states)
        self.assertLess(np.max(np.abs(energy - energy[0])), 2.0e-10)
        self.assertLess(np.max(np.abs(angular - angular[0])), 2.0e-10)
        self.assertLess(np.max(np.linalg.norm(runge_lenz - runge_lenz[0], axis=1)), 5.0e-10)

    def test_standard_map_local_jacobian(self):
        mapping = lambda z: np.asarray(standard_map(z[0], z[1], 0.7))
        jacobian = finite_difference_jacobian(mapping, np.array([0.4, -0.2]))
        self.assertAlmostEqual(np.linalg.det(jacobian), 1.0, places=7)


if __name__ == "__main__":
    unittest.main()
