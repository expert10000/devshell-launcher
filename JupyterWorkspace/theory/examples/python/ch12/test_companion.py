"""Regression tests for the Chapter 12 computational companion."""
from __future__ import annotations

import unittest

import numpy as np
import sympy as sp

from classical_fields import (
    continuity_residual,
    dirichlet_green_matrix,
    electric_field_1d,
    euler_lagrange_density,
    gauge_transform_1d,
    klein_gordon_dispersion,
    observed_order,
    periodic_laplacian,
    sine_gordon_static_kink,
    sine_gordon_static_residual,
    solve_poisson_dirichlet,
    wave_cfl_report,
    wave_energy,
    wave_leapfrog,
)


class ClassicalFieldCompanionTests(unittest.TestCase):
    def test_symbolic_wave_euler_lagrange(self):
        t, x, c = sp.symbols("t x c", positive=True)
        phi = sp.Function("phi")(t, x)
        density = sp.diff(phi, t) ** 2 / 2 - c**2 * sp.diff(phi, x) ** 2 / 2
        result = euler_lagrange_density(density, phi, (t, x))
        self.assertEqual(sp.simplify(result + sp.diff(phi, t, 2) - c**2 * sp.diff(phi, x, 2)), 0)

    def test_periodic_laplacian_constant(self):
        self.assertLess(np.max(np.abs(periodic_laplacian(np.ones(64), 0.1))), 1.0e-14)

    def test_periodic_laplacian_second_order(self):
        errors = []
        spacings = []
        for count in (64, 128, 256, 512):
            h = 2.0 * np.pi / count
            x = np.arange(count) * h
            errors.append(np.sqrt(np.mean((periodic_laplacian(np.sin(2*x), h) + 4*np.sin(2*x)) ** 2)))
            spacings.append(h)
        self.assertGreater(observed_order(np.array(errors), np.array(spacings)), 1.95)

    def test_wave_zero_solution(self):
        zero = np.zeros(80)
        history = wave_leapfrog(zero, zero, 0.1, 0.05, 20)
        self.assertEqual(float(np.max(np.abs(history))), 0.0)

    def test_wave_translation_accuracy(self):
        count = 400
        length = 20.0
        x = np.linspace(-10.0, 10.0, count, endpoint=False)
        h = length / count
        dt = 0.4 * h
        initial = np.exp(-((x + 2.0) / 1.3) ** 2)
        velocity = -np.gradient(initial, h, edge_order=2)
        steps = 100
        history = wave_leapfrog(initial, velocity, h, dt, steps)
        exact = np.exp(-((x - steps * dt + 2.0) / 1.3) ** 2)
        self.assertLess(np.sqrt(np.mean((history[-1] - exact) ** 2)), 3.0e-3)

    def test_wave_energy_bounded(self):
        count = 300
        x = np.linspace(0.0, 2*np.pi, count, endpoint=False)
        h = 2*np.pi/count
        dt = 0.5*h
        history = wave_leapfrog(np.sin(3*x), np.zeros_like(x), h, dt, 500)
        energy = wave_energy(history, h, dt)
        self.assertLess(np.max(np.abs((energy-energy[0])/energy[0])), 4.0e-3)

    def test_cfl_report(self):
        self.assertTrue(wave_cfl_report(2.0, 0.04, 0.1).stable_by_cfl)
        self.assertFalse(wave_cfl_report(2.0, 0.06, 0.1).stable_by_cfl)

    def test_klein_gordon_massless_limit(self):
        k = np.array([0.2, 1.1, 3.4])
        self.assertLess(np.max(np.abs(klein_gordon_dispersion(k, speed=2.0, mass_frequency=0.0)-2*k)), 1e-14)

    def test_poisson_sine_solution(self):
        x = np.linspace(0.0, 1.0, 401)
        h = x[1]-x[0]
        source = np.pi**2*np.sin(np.pi*x)
        solution = solve_poisson_dirichlet(source, h)
        self.assertLess(np.max(np.abs(solution-np.sin(np.pi*x))), 6.0e-6)

    def test_green_matrix_symmetry(self):
        x = np.linspace(0.0, 1.0, 21)
        green = dirichlet_green_matrix(x)
        self.assertLess(np.max(np.abs(green-green.T)), 1e-15)

    def test_green_matrix_boundary(self):
        x = np.linspace(0.0, 1.0, 21)
        green = dirichlet_green_matrix(x)
        self.assertEqual(float(np.max(np.abs(green[[0,-1],:]))), 0.0)

    def test_gauge_invariant_electric_field(self):
        nt, nx = 101, 240
        t = np.linspace(0.0, 1.0, nt)
        x = np.linspace(0.0, 2*np.pi, nx, endpoint=False)
        dt, dx = t[1]-t[0], x[1]-x[0]
        tt, xx = np.meshgrid(t, x, indexing="ij")
        phi = np.cos(xx-tt)
        ax = 0.3*np.sin(2*xx+0.2*tt)
        chi = 0.2*np.sin(xx)*np.cos(0.4*tt)
        before = electric_field_1d(phi, ax, dx, dt)
        p2, a2 = gauge_transform_1d(phi, ax, chi, dx, dt)
        after = electric_field_1d(p2, a2, dx, dt)
        self.assertLess(np.max(np.abs(before[2:-2]-after[2:-2])), 2.0e-12)

    def test_continuity_traveling_density(self):
        nt, nx = 101, 256
        t = np.linspace(0.0, 1.0, nt)
        x = np.linspace(0.0, 2*np.pi, nx, endpoint=False)
        dt, dx = t[1]-t[0], x[1]-x[0]
        tt, xx = np.meshgrid(t, x, indexing="ij")
        rho = 1.0 + 0.2*np.sin(xx-0.6*tt)
        current = 0.6*rho
        residual = continuity_residual(rho, current, dx, dt)
        self.assertLess(np.max(np.abs(residual)), 3.0e-5)

    def test_sine_gordon_kink_endpoints(self):
        x = np.array([-20.0, 20.0])
        kink = sine_gordon_static_kink(x)
        self.assertLess(kink[0], 1e-7)
        self.assertLess(abs(kink[1]-2*np.pi), 1e-7)

    def test_sine_gordon_static_residual(self):
        x = np.linspace(-8.0, 8.0, 4001)
        h = x[1]-x[0]
        residual = sine_gordon_static_residual(sine_gordon_static_kink(x), h)
        self.assertLess(np.max(np.abs(residual[20:-20])), 5.0e-6)

    def test_observed_order_exact_data(self):
        h = np.array([0.2, 0.1, 0.05, 0.025])
        self.assertAlmostEqual(observed_order(3.0*h**2, h), 2.0, places=12)


if __name__ == "__main__":
    unittest.main()
