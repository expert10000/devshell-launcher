"""Generate the Chapter 8 computational-companion figures and diagnostics.

Run from the repository root:
    python3 examples/python/ch08/generate_companion.py
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt
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


def save_figure(fig: plt.Figure, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(
        path,
        bbox_inches="tight",
        metadata={"Creator": "PR-BOOK Chapter 8 companion", "CreationDate": None, "ModDate": None},
    )
    plt.close(fig)


def state_graphs(output_dir: Path) -> dict[str, float]:
    time = np.linspace(0.0, 8.0, 401)
    state = constant_acceleration_state(time, position0=1.5, velocity0=5.0, acceleration=-1.2)
    fig, axes = plt.subplots(3, 1, figsize=(7.2, 7.2), sharex=True)
    axes[0].plot(time, state.position)
    axes[0].set_ylabel(r"$x(t)$")
    axes[1].plot(time, state.velocity)
    axes[1].axhline(0.0, linewidth=0.8)
    axes[1].set_ylabel(r"$v(t)$")
    axes[2].plot(time, state.acceleration)
    axes[2].set_ylabel(r"$a(t)$")
    axes[2].set_xlabel(r"time $t$")
    for axis in axes:
        axis.grid(True, alpha=0.25)
    fig.suptitle("One trajectory, three derivative levels")
    save_figure(fig, output_dir / "state_graphs.pdf")
    turning_time = 5.0 / 1.2
    return {"turning_time": turning_time, "turning_position": 1.5 + 5.0 * turning_time - 0.6 * turning_time**2}


def projectile_family(output_dir: Path) -> dict[str, float]:
    speed = 28.0
    angles = [20.0, 35.0, 45.0, 55.0, 70.0]
    fig, axis = plt.subplots(figsize=(7.2, 4.8))
    ranges: dict[str, float] = {}
    for angle in angles:
        flight_time = 2.0 * speed * np.sin(np.deg2rad(angle)) / 9.81
        time = np.linspace(0.0, flight_time, 240)
        x, y, _, _ = projectile_trajectory(time, speed, angle)
        axis.plot(x, y, label=fr"${angle:.0f}^\circ$")
        ranges[f"range_{int(angle)}deg"] = float(x[-1])
    axis.set_xlabel("horizontal position")
    axis.set_ylabel("vertical position")
    axis.set_title("Projectile family at fixed launch speed")
    axis.grid(True, alpha=0.25)
    axis.legend(ncol=3)
    save_figure(fig, output_dir / "projectile_family.pdf")
    return ranges


def polar_kinematics(output_dir: Path) -> dict[str, float]:
    time = np.linspace(0.0, 7.0, 350)
    r = 1.0 + 0.22 * time
    theta = 0.7 * time + 0.03 * time**2
    r_dot = np.full_like(time, 0.22)
    theta_dot = 0.7 + 0.06 * time
    r_ddot = np.zeros_like(time)
    theta_ddot = np.full_like(time, 0.06)
    position, velocity, acceleration = polar_state(r, theta, r_dot, theta_dot, r_ddot, theta_ddot)

    fig, axis = plt.subplots(figsize=(6.4, 6.0))
    axis.plot(position[:, 0], position[:, 1])
    indices = np.linspace(40, time.size - 35, 5, dtype=int)
    scale_v = 0.22
    scale_a = 0.08
    for index in indices:
        x, y = position[index]
        axis.arrow(x, y, scale_v * velocity[index, 0], scale_v * velocity[index, 1],
                   width=0.012, length_includes_head=True)
        axis.arrow(x, y, scale_a * acceleration[index, 0], scale_a * acceleration[index, 1],
                   width=0.010, length_includes_head=True, linestyle="--")
    axis.set_aspect("equal", adjustable="box")
    axis.set_xlabel("$x$")
    axis.set_ylabel("$y$")
    axis.set_title("Polar motion with velocity and acceleration vectors")
    axis.grid(True, alpha=0.25)
    save_figure(fig, output_dir / "polar_kinematics.pdf")
    speed = np.linalg.norm(velocity, axis=1)
    return {"maximum_speed": float(speed.max()), "final_radius": float(r[-1])}


def relative_motion(output_dir: Path) -> dict[str, float]:
    r0 = np.array([12.0, 5.0])
    velocity = np.array([-2.2, -0.35])
    closest_time, closest_distance = closest_approach(r0, velocity)
    time = np.linspace(0.0, max(7.0, 1.35 * closest_time), 220)
    relative = r0[None, :] + time[:, None] * velocity[None, :]

    fig, axis = plt.subplots(figsize=(6.8, 5.2))
    axis.plot(relative[:, 0], relative[:, 1])
    axis.scatter([r0[0]], [r0[1]], label="initial relative position")
    closest = r0 + velocity * closest_time
    axis.scatter([closest[0]], [closest[1]], label="closest approach")
    axis.plot([0.0, closest[0]], [0.0, closest[1]], linestyle="--")
    axis.scatter([0.0], [0.0], marker="x", label="observer")
    axis.set_aspect("equal", adjustable="box")
    axis.set_xlabel("relative $x$")
    axis.set_ylabel("relative $y$")
    axis.set_title("Uniform relative motion and closest approach")
    axis.grid(True, alpha=0.25)
    axis.legend()
    save_figure(fig, output_dir / "relative_motion.pdf")
    return {"closest_time": closest_time, "closest_distance": closest_distance}


def finite_difference_accuracy(output_dir: Path) -> dict[str, float]:
    steps = 2.0 ** (-np.arange(3, 12, dtype=float))
    first_errors = []
    second_errors = []
    for dt in steps:
        time = np.arange(0.0, 2.0 * np.pi + 0.5 * dt, dt)
        values = np.sin(time)
        first = centered_first_derivative(values, dt)
        second = centered_second_derivative(values, dt)
        interior = slice(2, -2)
        first_errors.append(np.max(np.abs(first[interior] - np.cos(time[interior]))))
        second_errors.append(np.max(np.abs(second[interior] + np.sin(time[interior]))))

    fig, axis = plt.subplots(figsize=(6.8, 4.8))
    axis.loglog(steps, first_errors, marker="o", label="first derivative")
    axis.loglog(steps, second_errors, marker="s", label="second derivative")
    axis.loglog(steps, 0.25 * steps**2, linestyle="--", label=r"reference $O(\Delta t^2)$")
    axis.set_xlabel(r"sample spacing $\Delta t$")
    axis.set_ylabel("maximum interior error")
    axis.set_title("Centered differences converge quadratically")
    axis.grid(True, which="both", alpha=0.25)
    axis.legend()
    save_figure(fig, output_dir / "finite_difference_accuracy.pdf")
    return {"smallest_first_error": float(first_errors[-1]), "smallest_second_error": float(second_errors[-1])}


def noise_amplification(output_dir: Path) -> dict[str, float]:
    rng = np.random.default_rng(80)
    time = np.linspace(0.0, 8.0, 321)
    dt = float(time[1] - time[0])
    exact = 0.7 + 2.2 * time - 0.35 * time**2 + 0.035 * time**3
    noisy = exact + rng.normal(0.0, 0.025, time.size)
    velocity = centered_first_derivative(noisy, dt)
    acceleration = centered_second_derivative(noisy, dt)

    fig, axes = plt.subplots(3, 1, figsize=(7.2, 7.2), sharex=True)
    axes[0].plot(time, exact, label="exact")
    axes[0].scatter(time[::5], noisy[::5], s=8, label="sampled")
    axes[0].set_ylabel("position")
    axes[0].legend()
    axes[1].plot(time, velocity)
    axes[1].set_ylabel("estimated velocity")
    axes[2].plot(time, acceleration)
    axes[2].set_ylabel("estimated acceleration")
    axes[2].set_xlabel("time")
    for axis in axes:
        axis.grid(True, alpha=0.25)
    fig.suptitle("Differentiation amplifies measurement noise")
    save_figure(fig, output_dir / "noise_amplification.pdf")

    x0, v0, acceleration_fit = fit_constant_acceleration(time, noisy)
    return {"fit_x0": x0, "fit_v0": v0, "fit_acceleration": acceleration_fit,
            "acceleration_sample_std": float(np.std(acceleration[2:-2]))}


def uncertainty_envelope(output_dir: Path) -> dict[str, float]:
    ranges = monte_carlo_projectile_range(
        speed_mean=30.0,
        speed_sigma=0.7,
        angle_mean_deg=42.0,
        angle_sigma_deg=1.5,
        samples=30_000,
        seed=80,
    )
    q05, median, q95 = np.quantile(ranges, [0.05, 0.5, 0.95])
    fig, axis = plt.subplots(figsize=(6.8, 4.6))
    axis.hist(ranges, bins=70, density=True, alpha=0.75)
    axis.axvline(q05, linestyle="--", label="5th percentile")
    axis.axvline(median, label="median")
    axis.axvline(q95, linestyle="--", label="95th percentile")
    axis.set_xlabel("range")
    axis.set_ylabel("probability density")
    axis.set_title("Monte Carlo propagation of launch uncertainty")
    axis.legend()
    axis.grid(True, alpha=0.2)
    save_figure(fig, output_dir / "uncertainty_envelope.pdf")
    return {"range_q05": float(q05), "range_median": float(median), "range_q95": float(q95)}


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
        default=Path("generated/ch08/computational"),
        help="directory for deterministic PDF figures and diagnostics",
    )
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    sections = {
        "state_graphs": state_graphs(args.output_dir),
        "projectile_family": projectile_family(args.output_dir),
        "polar_kinematics": polar_kinematics(args.output_dir),
        "relative_motion": relative_motion(args.output_dir),
        "finite_difference_accuracy": finite_difference_accuracy(args.output_dir),
        "noise_amplification": noise_amplification(args.output_dir),
        "uncertainty_envelope": uncertainty_envelope(args.output_dir),
    }
    write_diagnostics(args.output_dir, sections)
    print(json.dumps(sections, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
