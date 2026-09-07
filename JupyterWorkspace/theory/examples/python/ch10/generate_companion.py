"""Generate Chapter 10 computational-companion figures and diagnostics.

Run from the repository root:
    python3 examples/python/ch10/generate_companion.py
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import sympy as sp

from lagrangian_dynamics import (
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
    rk4_system,
    solve_accelerations,
)


def save_figure(fig: plt.Figure, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(
        path,
        bbox_inches="tight",
        metadata={"Creator": "PR-BOOK Chapter 10 companion", "CreationDate": None, "ModDate": None},
    )
    plt.close(fig)


def symbolic_euler_lagrange() -> dict[str, str]:
    theta, theta_dot, theta_ddot, mass, length, gravity, time = sp.symbols(
        "theta theta_dot theta_ddot m l g t", positive=True
    )
    lagrangian = sp.Rational(1, 2) * mass * length**2 * theta_dot**2 + mass * gravity * length * sp.cos(theta)
    residual = euler_lagrange_residuals(
        lagrangian, (theta,), (theta_dot,), (theta_ddot,), time
    )[0]
    solution = solve_accelerations((residual,), (theta_ddot,))[theta_ddot]
    expected = mass * length**2 * theta_ddot + mass * gravity * length * sp.sin(theta)
    if sp.simplify(residual - expected) != 0:
        raise RuntimeError("symbolic pendulum residual failed its analytic check")
    return {
        "lagrangian": str(lagrangian),
        "residual": str(sp.factor(residual)),
        "acceleration": str(solution),
    }


def pendulum_phase_portrait(output_dir: Path) -> dict[str, float]:
    time = np.linspace(0.0, 20.0, 4001)
    result = rk4_system(pendulum_rhs(1.0), time, np.array([1.2, 0.0]))
    energy = pendulum_energy(result.state, mass=1.0, length=1.0)
    relative_error = np.max(np.abs((energy - energy[0]) / energy[0]))

    fig, axis = plt.subplots(figsize=(6.8, 5.0))
    axis.plot(result.state[:, 0], result.state[:, 1])
    axis.scatter([result.state[0, 0]], [result.state[0, 1]], s=34, label="initial state")
    axis.set_xlabel(r"angle $\theta$")
    axis.set_ylabel(r"angular velocity $\dot\theta$")
    axis.set_title("Nonlinear pendulum phase trajectory")
    axis.grid(True, alpha=0.25)
    axis.legend()
    save_figure(fig, output_dir / "pendulum_phase_portrait.pdf")
    return {"maximum_relative_energy_error": float(relative_error)}


def pendulum_energy_convergence(output_dir: Path) -> dict[str, object]:
    steps = np.array([0.16, 0.08, 0.04, 0.02])
    errors = []
    for step in steps:
        time = np.arange(0.0, 24.0 + 0.5 * step, step)
        result = rk4_system(pendulum_rhs(1.0), time, np.array([1.0, 0.0]))
        energy = pendulum_energy(result.state, mass=1.0, length=1.0)
        errors.append(float(np.max(np.abs((energy - energy[0]) / energy[0]))))
    errors_array = np.array(errors)
    observed_order = float(np.polyfit(np.log(steps), np.log(errors_array), 1)[0])

    fig, axis = plt.subplots(figsize=(6.8, 4.8))
    axis.loglog(steps, errors_array, marker="o", label="maximum energy error")
    reference = errors_array[-1] * (steps / steps[-1]) ** 4
    axis.loglog(steps, reference, linestyle="--", label=r"$\Delta t^4$ reference")
    axis.set_xlabel(r"time step $\Delta t$")
    axis.set_ylabel("maximum relative energy error")
    axis.set_title("Runge--Kutta convergence for the pendulum")
    axis.grid(True, which="both", alpha=0.25)
    axis.legend()
    save_figure(fig, output_dir / "pendulum_energy_convergence.pdf")
    return {
        "steps": [float(value) for value in steps],
        "maximum_relative_errors": errors,
        "observed_order": observed_order,
    }


def constraint_residuals(output_dir: Path) -> dict[str, float]:
    length = 1.0
    theta0 = 1.1
    initial = np.array([length * np.sin(theta0), -length * np.cos(theta0), 0.0, 0.0])
    time = np.linspace(0.0, 40.0, 1001)
    raw = integrate_cartesian_pendulum(time, initial, length, project_each_step=False)
    projected = integrate_cartesian_pendulum(time, initial, length, project_each_step=True)
    raw_position, raw_tangent = circle_constraint_residuals(raw.state, length)
    projected_position, projected_tangent = circle_constraint_residuals(projected.state, length)

    floor = 1.0e-18
    fig, axis = plt.subplots(figsize=(7.0, 4.9))
    axis.semilogy(time, np.maximum(np.abs(raw_position), floor), label="unprojected position residual")
    axis.semilogy(time, np.maximum(np.abs(projected_position), floor), label="projected position residual")
    axis.set_xlabel("time")
    axis.set_ylabel(r"$|r^2-\ell^2|/\ell^2$")
    axis.set_title("Holonomic-constraint residual under numerical integration")
    axis.grid(True, which="both", alpha=0.25)
    axis.legend()
    save_figure(fig, output_dir / "constraint_residuals.pdf")
    return {
        "raw_maximum_position_residual": float(np.max(np.abs(raw_position))),
        "projected_maximum_position_residual": float(np.max(np.abs(projected_position))),
        "raw_maximum_tangency_residual": float(np.max(np.abs(raw_tangent))),
        "projected_maximum_tangency_residual": float(np.max(np.abs(projected_tangent))),
    }


def nonlinear_period_sweep(output_dir: Path) -> dict[str, float]:
    amplitudes = np.linspace(0.02, 2.8, 90)
    small_angle_period = 2.0 * np.pi * np.sqrt(1.0 / 9.81)
    periods = np.array([pendulum_period_quadrature(value, 1.0) for value in amplitudes])
    ratios = periods / small_angle_period

    fig, axis = plt.subplots(figsize=(6.9, 4.8))
    axis.plot(amplitudes, ratios)
    axis.axhline(1.0, linewidth=0.8, linestyle="--", label="small-angle value")
    axis.set_xlabel(r"amplitude $\theta_0$ (rad)")
    axis.set_ylabel(r"$T(\theta_0)/T_0$")
    axis.set_title("Amplitude dependence of the nonlinear pendulum period")
    axis.grid(True, alpha=0.25)
    axis.legend()
    save_figure(fig, output_dir / "nonlinear_pendulum_period.pdf")
    return {
        "small_amplitude_ratio": float(ratios[0]),
        "largest_amplitude": float(amplitudes[-1]),
        "largest_amplitude_ratio": float(ratios[-1]),
    }


def central_effective_potential(output_dir: Path) -> dict[str, object]:
    radius = np.linspace(0.22, 5.5, 600)
    momenta = [0.8, 1.0, 1.2]
    minima = {}
    fig, axis = plt.subplots(figsize=(7.0, 4.9))
    for angular_momentum in momenta:
        potential = kepler_effective_potential(radius, 1.0, angular_momentum, 1.0)
        circular = kepler_circular_radius(1.0, angular_momentum, 1.0)
        minimum = float(kepler_effective_potential(circular, 1.0, angular_momentum, 1.0))
        minima[f"L={angular_momentum:g}"] = {"radius": circular, "energy": minimum}
        axis.plot(radius, potential, label=fr"$L={angular_momentum:g}$")
        axis.scatter([circular], [minimum], s=28)
    axis.axhline(0.0, linewidth=0.8)
    axis.set_xlim(radius[0], radius[-1])
    axis.set_ylim(-1.0, 2.1)
    axis.set_xlabel("radius")
    axis.set_ylabel(r"effective potential $U_{\mathrm{eff}}$")
    axis.set_title("Kepler effective potentials and circular-orbit minima")
    axis.grid(True, alpha=0.25)
    axis.legend()
    save_figure(fig, output_dir / "central_effective_potential.pdf")
    return minima


def normal_modes(output_dir: Path) -> dict[str, object]:
    mass = np.diag([2.0, 1.0])
    stiffness = np.array([[5.0, -2.0], [-2.0, 6.0]])
    frequencies, modes = generalized_normal_modes(mass, stiffness)
    orthogonality_error = float(np.max(np.abs(modes.T @ mass @ modes - np.eye(2))))

    coordinates = np.array([1.0, 2.0])
    fig, axis = plt.subplots(figsize=(6.8, 4.8))
    for mode_index in range(2):
        axis.plot(
            coordinates,
            modes[:, mode_index],
            marker="o",
            label=fr"mode {mode_index + 1}, $\omega={frequencies[mode_index]:.3f}$",
        )
    axis.axhline(0.0, linewidth=0.8)
    axis.set_xticks(coordinates, ["coordinate 1", "coordinate 2"])
    axis.set_ylabel("mass-normalized mode component")
    axis.set_title("Generalized normal modes of a two-coordinate system")
    axis.grid(True, alpha=0.25)
    axis.legend()
    save_figure(fig, output_dir / "generalized_normal_modes.pdf")

    time = np.linspace(0.0, 4.0, 401)
    evolution, _, _ = modal_time_evolution(mass, stiffness, np.array([0.3, -0.2]), np.zeros(2), time)
    residual = mass @ np.gradient(np.gradient(evolution, time, axis=0), time, axis=0).T + stiffness @ evolution.T
    interior_residual = float(np.max(np.abs(residual[:, 3:-3])))
    return {
        "frequencies": [float(value) for value in frequencies],
        "modes": modes.tolist(),
        "mass_orthogonality_error": orthogonality_error,
        "finite_difference_equation_residual": interior_residual,
    }


def electromagnetic_trajectories(output_dir: Path) -> dict[str, float]:
    charge = mass = magnetic_strength = 1.0
    cyclotron_period = 2.0 * np.pi
    time = np.linspace(0.0, 8.0 * cyclotron_period, 8001)
    magnetic = np.array([0.0, 0.0, magnetic_strength])
    initial_position = np.zeros(3)
    initial_velocity = np.array([1.0, 0.0, 0.0])

    pure = integrate_charged_particle(
        time, initial_position, initial_velocity, charge, mass, np.zeros(3), magnetic
    )
    electric = np.array([0.2, 0.0, 0.0])
    crossed = integrate_charged_particle(
        time, initial_position, initial_velocity, charge, mass, electric, magnetic
    )
    speed = np.linalg.norm(pure.state[:, 3:], axis=1)
    speed_error = float(np.max(np.abs(speed - speed[0])))
    drift = (crossed.state[-1, :3] - crossed.state[0, :3]) / (time[-1] - time[0])
    expected_drift = np.cross(electric, magnetic) / np.dot(magnetic, magnetic)

    fig, axis = plt.subplots(figsize=(7.0, 5.1))
    axis.plot(pure.state[:, 0], pure.state[:, 1], label="magnetic field only")
    axis.plot(crossed.state[:, 0], crossed.state[:, 1], label="crossed electric and magnetic fields")
    axis.plot(
        expected_drift[0] * time,
        expected_drift[1] * time,
        linestyle="--",
        label=r"guiding-center $\mathbf{E}\times\mathbf{B}/B^2$ drift",
    )
    axis.set_xlabel("x")
    axis.set_ylabel("y")
    axis.set_aspect("equal", adjustable="box")
    axis.set_title("Charged-particle trajectories from the electromagnetic Lagrangian")
    axis.grid(True, alpha=0.25)
    axis.legend()
    save_figure(fig, output_dir / "electromagnetic_trajectories.pdf")
    return {
        "maximum_speed_error_in_pure_B": speed_error,
        "measured_drift_x": float(drift[0]),
        "measured_drift_y": float(drift[1]),
        "expected_drift_x": float(expected_drift[0]),
        "expected_drift_y": float(expected_drift[1]),
    }


def write_diagnostics(output_dir: Path, summary: dict[str, object]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "companion_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    rows: list[tuple[str, str, str]] = []
    for section, values in summary.items():
        if isinstance(values, dict):
            for metric, value in values.items():
                if isinstance(value, (str, int, float)):
                    rows.append((section, metric, str(value)))
    with (output_dir / "numerical_diagnostics.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["section", "metric", "value"])
        writer.writerows(sorted(rows))


def generate(output_dir: Path) -> dict[str, object]:
    summary: dict[str, object] = {
        "symbolic_euler_lagrange": symbolic_euler_lagrange(),
        "pendulum_phase_portrait": pendulum_phase_portrait(output_dir),
        "pendulum_energy_convergence": pendulum_energy_convergence(output_dir),
        "constraint_residuals": constraint_residuals(output_dir),
        "nonlinear_period_sweep": nonlinear_period_sweep(output_dir),
        "central_effective_potential": central_effective_potential(output_dir),
        "generalized_normal_modes": normal_modes(output_dir),
        "electromagnetic_trajectories": electromagnetic_trajectories(output_dir),
    }
    write_diagnostics(output_dir, summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("generated/ch10/computational"),
        help="directory for deterministic figures and diagnostics",
    )
    arguments = parser.parse_args()
    summary = generate(arguments.output_dir)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
