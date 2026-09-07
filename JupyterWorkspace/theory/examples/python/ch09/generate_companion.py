"""Generate Chapter 9 computational-companion figures and diagnostics.

Run from the repository root:
    python3 examples/python/ch09/generate_companion.py
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

from newtonian_dynamics import (
    atwood_machine,
    friction_force,
    linear_drag_velocity,
    net_acceleration,
    quadratic_drag_velocity,
    reconstruct_force_polynomial,
    rotating_coordinates,
    vertical_circle_contact_force,
)


def save_figure(fig: plt.Figure, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(
        path,
        bbox_inches="tight",
        metadata={"Creator": "PR-BOOK Chapter 9 companion", "CreationDate": None, "ModDate": None},
    )
    plt.close(fig)


def force_acceleration_map(output_dir: Path) -> dict[str, float]:
    forces = np.linspace(-20.0, 20.0, 241)
    masses = [1.0, 2.0, 5.0]
    fig, axis = plt.subplots(figsize=(6.8, 4.8))
    for mass in masses:
        accelerations = np.array([net_acceleration(np.array([force]), mass)[0] for force in forces])
        axis.plot(forces, accelerations, label=fr"$m={mass:g}$")
    axis.axhline(0.0, linewidth=0.8)
    axis.axvline(0.0, linewidth=0.8)
    axis.set_xlabel("net force")
    axis.set_ylabel("acceleration")
    axis.set_title("Newton's second law as a family of response lines")
    axis.grid(True, alpha=0.25)
    axis.legend()
    save_figure(fig, output_dir / "force_acceleration_map.pdf")
    return {"slope_mass_1": 1.0, "slope_mass_2": 0.5, "slope_mass_5": 0.2}


def friction_regimes(output_dir: Path) -> dict[str, float]:
    normal = 10.0
    mu_static = 0.60
    mu_kinetic = 0.40
    drive = np.linspace(-12.0, 12.0, 481)
    friction = np.array([
        friction_force(value, normal, mu_static, mu_kinetic).force for value in drive
    ])
    net = drive + friction
    fig, axes = plt.subplots(2, 1, figsize=(7.0, 6.4), sharex=True)
    axes[0].plot(drive, friction)
    axes[0].axvline(mu_static * normal, linestyle="--")
    axes[0].axvline(-mu_static * normal, linestyle="--")
    axes[0].set_ylabel("friction force")
    axes[0].set_title("Static friction adjusts; kinetic friction saturates")
    axes[1].plot(drive, net)
    axes[1].axhline(0.0, linewidth=0.8)
    axes[1].set_xlabel("attempted tangential drive")
    axes[1].set_ylabel("net tangential force")
    for axis in axes:
        axis.grid(True, alpha=0.25)
    save_figure(fig, output_dir / "friction_regimes.pdf")
    return {
        "static_limit": mu_static * normal,
        "kinetic_magnitude": mu_kinetic * normal,
        "net_force_at_drive_10": 10.0 - mu_kinetic * normal,
    }


def atwood_sweep(output_dir: Path) -> dict[str, float]:
    mass1 = 2.0
    mass2 = np.linspace(0.4, 7.0, 300)
    acceleration = np.empty_like(mass2)
    tension = np.empty_like(mass2)
    for index, value in enumerate(mass2):
        state = atwood_machine(mass1, float(value))
        acceleration[index] = state.acceleration
        tension[index] = state.tension
    fig, axes = plt.subplots(2, 1, figsize=(7.0, 6.4), sharex=True)
    axes[0].plot(mass2 / mass1, acceleration)
    axes[0].axhline(0.0, linewidth=0.8)
    axes[0].set_ylabel("acceleration")
    axes[0].set_title("Atwood machine as a parameter study")
    axes[1].plot(mass2 / mass1, tension)
    axes[1].set_xlabel(r"mass ratio $m_2/m_1$")
    axes[1].set_ylabel("rope tension")
    for axis in axes:
        axis.grid(True, alpha=0.25)
    save_figure(fig, output_dir / "atwood_parameter_sweep.pdf")
    reference = atwood_machine(mass1, 5.0)
    return {"reference_acceleration": reference.acceleration, "reference_tension": reference.tension}


def vertical_circle_contact(output_dir: Path) -> dict[str, float]:
    mass = 1.0
    radius = 2.0
    angle = np.linspace(0.0, 2.0 * np.pi, 500)
    speeds = [3.5, 4.5, 5.5]
    fig, axis = plt.subplots(figsize=(7.0, 4.8))
    minima: dict[str, float] = {}
    for speed in speeds:
        contact = vertical_circle_contact_force(mass, speed, radius, angle)
        axis.plot(np.rad2deg(angle), contact, label=fr"$v={speed:g}$")
        minima[f"minimum_contact_speed_{speed:g}"] = float(contact.min())
    axis.axhline(0.0, linewidth=0.9, linestyle="--")
    axis.set_xlabel("angle from the top (degrees)")
    axis.set_ylabel("inward contact force")
    axis.set_title("Vertical-circle contact condition")
    axis.grid(True, alpha=0.25)
    axis.legend()
    save_figure(fig, output_dir / "vertical_circle_contact.pdf")
    minima["minimum_top_speed"] = float(np.sqrt(9.81 * radius))
    return minima


def drag_approach_terminal(output_dir: Path) -> dict[str, float]:
    mass = 80.0
    gravity = 9.81
    linear_coefficient = 16.0
    quadratic_coefficient = 0.30
    time = np.linspace(0.0, 25.0, 1001)
    linear_velocity = linear_drag_velocity(time, mass, linear_coefficient, gravity)
    quadratic_velocity = quadratic_drag_velocity(time, mass, quadratic_coefficient, gravity)
    linear_terminal = mass * gravity / linear_coefficient
    quadratic_terminal = np.sqrt(mass * gravity / quadratic_coefficient)
    fig, axis = plt.subplots(figsize=(7.0, 4.8))
    axis.plot(time, linear_velocity, label="linear drag")
    axis.plot(time, quadratic_velocity, label="quadratic drag")
    axis.axhline(linear_terminal, linestyle="--", label="linear terminal speed")
    axis.axhline(quadratic_terminal, linestyle=":", label="quadratic terminal speed")
    axis.set_xlabel("time")
    axis.set_ylabel("downward speed")
    axis.set_title("Different drag laws approach different terminal speeds")
    axis.grid(True, alpha=0.25)
    axis.legend(ncol=2)
    save_figure(fig, output_dir / "drag_terminal_approach.pdf")
    return {
        "linear_terminal_speed": float(linear_terminal),
        "quadratic_terminal_speed": float(quadratic_terminal),
        "quadratic_final_speed": float(quadratic_velocity[-1]),
    }


def rotating_frame_path(output_dir: Path) -> dict[str, float]:
    time = np.linspace(0.0, 18.0, 700)
    initial = np.array([1.5, -1.0])
    velocity = np.array([1.2, 0.35])
    inertial = initial[None, :] + time[:, None] * velocity[None, :]
    angular_speed = 0.32
    rotating = rotating_coordinates(inertial, time, angular_speed)
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 4.5))
    axes[0].plot(inertial[:, 0], inertial[:, 1])
    axes[0].set_title("Inertial coordinates")
    axes[1].plot(rotating[:, 0], rotating[:, 1])
    axes[1].set_title("Rotating coordinates")
    for axis in axes:
        axis.set_aspect("equal", adjustable="box")
        axis.set_xlabel("x")
        axis.set_ylabel("y")
        axis.grid(True, alpha=0.25)
    fig.suptitle("One force-free trajectory, two coordinate descriptions")
    save_figure(fig, output_dir / "rotating_frame_path.pdf")
    norm_error = np.max(np.abs(np.linalg.norm(inertial, axis=1) - np.linalg.norm(rotating, axis=1)))
    return {"angular_speed": angular_speed, "maximum_norm_error": float(norm_error)}


def force_reconstruction(output_dir: Path) -> dict[str, float]:
    rng = np.random.default_rng(90)
    time = np.linspace(0.0, 8.0, 161)
    mass = 3.0
    exact_position = 0.4 + 1.2 * time + 0.30 * time**2 - 0.012 * time**4
    exact_acceleration = 0.60 - 0.144 * time**2
    exact_force = mass * exact_acceleration
    sampled_position = exact_position + rng.normal(0.0, 0.035, time.size)
    fitted_position, fitted_acceleration, fitted_force = reconstruct_force_polynomial(
        time, sampled_position, mass, degree=4
    )
    fig, axes = plt.subplots(2, 1, figsize=(7.2, 6.6), sharex=True)
    axes[0].plot(time, exact_position, label="exact trajectory")
    axes[0].scatter(time[::4], sampled_position[::4], s=10, label="noisy samples")
    axes[0].plot(time, fitted_position, linestyle="--", label="polynomial fit")
    axes[0].set_ylabel("position")
    axes[0].legend(ncol=3)
    axes[1].plot(time, exact_force, label="exact force")
    axes[1].plot(time, fitted_force, linestyle="--", label="reconstructed force")
    axes[1].set_xlabel("time")
    axes[1].set_ylabel("force")
    axes[1].legend()
    for axis in axes:
        axis.grid(True, alpha=0.25)
    fig.suptitle("Inverse dynamics from noisy trajectory data")
    save_figure(fig, output_dir / "force_reconstruction.pdf")
    rmse = float(np.sqrt(np.mean((fitted_force - exact_force) ** 2)))
    position_rmse = float(np.sqrt(np.mean((fitted_position - exact_position) ** 2)))
    return {"force_rmse": rmse, "position_fit_rmse": position_rmse,
            "maximum_acceleration": float(np.max(np.abs(fitted_acceleration)))}


def write_diagnostics(output_dir: Path, sections: dict[str, dict[str, float]]) -> None:
    (output_dir / "companion_summary.json").write_text(
        json.dumps(sections, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    with (output_dir / "numerical_diagnostics.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["section", "quantity", "value"])
        for section, values in sections.items():
            for quantity, value in values.items():
                writer.writerow([section, quantity, f"{value:.12g}"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("generated/ch09/computational"),
        help="directory for deterministic PDF figures and diagnostics",
    )
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    sections = {
        "force_acceleration_map": force_acceleration_map(args.output_dir),
        "friction_regimes": friction_regimes(args.output_dir),
        "atwood_parameter_sweep": atwood_sweep(args.output_dir),
        "vertical_circle_contact": vertical_circle_contact(args.output_dir),
        "drag_terminal_approach": drag_approach_terminal(args.output_dir),
        "rotating_frame_path": rotating_frame_path(args.output_dir),
        "force_reconstruction": force_reconstruction(args.output_dir),
    }
    write_diagnostics(args.output_dir, sections)


if __name__ == "__main__":
    main()
