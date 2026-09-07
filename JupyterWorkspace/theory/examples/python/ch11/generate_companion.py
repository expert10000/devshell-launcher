"""Generate deterministic Chapter 11 computational figures and diagnostics."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from hamiltonian_dynamics import (
    canonical_map_defect,
    explicit_euler_step,
    integrate_fixed_step,
    kepler_field,
    kepler_invariants,
    oscillator_energy,
    oscillator_exact_matrix,
    oscillator_field,
    oscillator_from_action_angle,
    oscillator_to_action_angle,
    polygon_area,
    rk4_step,
    standard_map,
    symplectic_defect,
    symplectic_euler_step,
    velocity_verlet_step,
)


def save_figure(path: Path) -> None:
    plt.tight_layout()
    plt.savefig(path, metadata={"CreationDate": None, "ModDate": None})
    plt.close()


def oscillator_integrations(step: float = 0.08, final_time: float = 160.0):
    times = np.arange(0.0, final_time + step / 2.0, step)
    initial = np.array([1.0, 0.0])
    field = lambda t, y: oscillator_field(t, y)
    rk4 = integrate_fixed_step(lambda t, y, h: rk4_step(field, t, y, h), initial, times)
    euler = integrate_fixed_step(lambda t, y, h: explicit_euler_step(field, t, y, h), initial, times)
    symp = integrate_fixed_step(
        lambda t, y, h: symplectic_euler_step(lambda p: p, lambda q: q, y, h),
        initial,
        times,
    )
    verlet = integrate_fixed_step(
        lambda t, y, h: velocity_verlet_step(lambda q: -q, y, h),
        initial,
        times,
    )
    return times, initial, {"RK4": rk4, "Explicit Euler": euler, "Symplectic Euler": symp, "Velocity Verlet": verlet}


def make_outputs(output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    times, initial, trajectories = oscillator_integrations()
    initial_energy = float(oscillator_energy(initial))

    plt.figure(figsize=(7.0, 4.5))
    for name, states in trajectories.items():
        relative = (oscillator_energy(states) - initial_energy) / initial_energy
        plt.plot(times, relative, label=name)
    plt.xlabel("time")
    plt.ylabel("relative energy error")
    plt.legend()
    save_figure(output_dir / "oscillator_integrator_energy.pdf")

    plt.figure(figsize=(5.6, 5.0))
    for name in ("RK4", "Symplectic Euler", "Velocity Verlet"):
        states = trajectories[name]
        plt.plot(states[:, 0], states[:, 1], label=name)
    plt.xlabel("q")
    plt.ylabel("p")
    plt.axis("equal")
    plt.legend()
    save_figure(output_dir / "oscillator_phase_portrait.pdf")

    # Area preservation under exact Hamiltonian flow versus a contracting map.
    t = np.linspace(0.0, 2.0 * np.pi, 240, endpoint=False)
    boundary = np.column_stack((1.1 * np.cos(t), 0.7 * np.sin(t)))
    exact = boundary @ oscillator_exact_matrix(1.7).T
    contracting_matrix = 0.82 * oscillator_exact_matrix(1.7)
    contracting = boundary @ contracting_matrix.T
    areas = {
        "initial": abs(polygon_area(boundary)),
        "hamiltonian": abs(polygon_area(exact)),
        "contracting": abs(polygon_area(contracting)),
    }
    plt.figure(figsize=(6.0, 4.8))
    plt.plot(boundary[:, 0], boundary[:, 1], label="initial cell")
    plt.plot(exact[:, 0], exact[:, 1], label="Hamiltonian image")
    plt.plot(contracting[:, 0], contracting[:, 1], label="contracting image")
    plt.xlabel("q")
    plt.ylabel("p")
    plt.axis("equal")
    plt.legend()
    save_figure(output_dir / "symplectic_area_diagnostic.pdf")

    # Kicked-rotor Poincare map.
    plt.figure(figsize=(6.2, 5.2))
    for theta0, p0 in [(-2.4, 0.0), (-1.2, 0.2), (0.2, 0.0), (1.4, -0.3), (2.5, 0.1)]:
        theta, momentum = theta0, p0
        points = []
        for iteration in range(1800):
            theta, momentum = standard_map(theta, momentum, 0.92)
            if iteration >= 200:
                points.append((theta, momentum))
        points = np.asarray(points)
        plt.plot(points[:, 0], points[:, 1], ".", markersize=0.7)
    plt.xlabel(r"$\theta$ mod $2\pi$")
    plt.ylabel(r"$p$ mod $2\pi$")
    save_figure(output_dir / "kicked_rotor_poincare.pdf")

    # Kepler orbit and invariant drift.
    step = 0.002
    kepler_times = np.arange(0.0, 20.0 + step / 2.0, step)
    initial_kepler = np.array([1.0, 0.0, 0.0, 0.82])
    field_kepler = lambda time, state: kepler_field(time, state)
    kepler_states = integrate_fixed_step(
        lambda time, state, h: rk4_step(field_kepler, time, state, h),
        initial_kepler,
        kepler_times,
    )
    energy, angular, runge_lenz = kepler_invariants(kepler_states)
    plt.figure(figsize=(5.8, 5.2))
    plt.plot(kepler_states[:, 0], kepler_states[:, 1])
    plt.plot([0.0], [0.0], "o")
    plt.xlabel("x")
    plt.ylabel("y")
    plt.axis("equal")
    save_figure(output_dir / "kepler_orbit_invariants.pdf")

    # Canonical versus noncanonical scaling defect.
    scales = np.linspace(0.45, 2.2, 100)
    canonical_defects = []
    noncanonical_defects = []
    point = np.array([0.7, -0.4])
    for scale in scales:
        canonical_defects.append(canonical_map_defect(lambda z, a=scale: np.array([a * z[0], z[1] / a]), point))
        noncanonical_defects.append(canonical_map_defect(lambda z, a=scale: np.array([a * z[0], a * z[1]]), point))
    plt.figure(figsize=(6.3, 4.5))
    plt.semilogy(scales, np.maximum(canonical_defects, 1.0e-16), label="canonical scaling")
    plt.semilogy(scales, np.maximum(noncanonical_defects, 1.0e-16), label="same scaling of q and p")
    plt.xlabel("scale factor")
    plt.ylabel(r"$\|M^TJM-J\|_F$")
    plt.legend()
    save_figure(output_dir / "canonical_map_defect.pdf")

    # Action-angle reconstruction family.
    angles = np.linspace(0.0, 2.0 * np.pi, 500)
    plt.figure(figsize=(5.8, 5.0))
    for action in (0.25, 0.6, 1.0):
        states = np.array([oscillator_from_action_angle(action, angle) for angle in angles])
        plt.plot(states[:, 0], states[:, 1], label=f"I={action:g}")
    plt.xlabel("q")
    plt.ylabel("p")
    plt.axis("equal")
    plt.legend()
    save_figure(output_dir / "action_angle_reconstruction.pdf")

    diagnostics = []
    exact_final = oscillator_exact_matrix(times[-1]) @ initial
    for name, states in trajectories.items():
        relative = np.abs((oscillator_energy(states) - initial_energy) / initial_energy)
        diagnostics.append({
            "method": name,
            "step": float(times[1] - times[0]),
            "maximum_relative_energy_error": float(np.max(relative)),
            "final_state_error": float(np.linalg.norm(states[-1] - exact_final)),
        })

    summary = {
        "oscillator": {
            "initial_energy": initial_energy,
            "diagnostics": diagnostics,
        },
        "phase_space_area": areas,
        "kepler": {
            "maximum_relative_energy_drift": float(np.max(np.abs((energy - energy[0]) / energy[0]))),
            "maximum_relative_angular_momentum_drift": float(np.max(np.abs((angular - angular[0]) / angular[0]))),
            "maximum_runge_lenz_vector_drift": float(np.max(np.linalg.norm(runge_lenz - runge_lenz[0], axis=1))),
        },
        "symplectic": {
            "exact_oscillator_matrix_defect": symplectic_defect(oscillator_exact_matrix(1.7)),
            "contracting_matrix_defect": symplectic_defect(contracting_matrix),
        },
    }
    (output_dir / "companion_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with (output_dir / "numerical_diagnostics.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(diagnostics[0]))
        writer.writeheader()
        writer.writerows(diagnostics)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("generated/ch11/computational"),
    )
    arguments = parser.parse_args()
    summary = make_outputs(arguments.output_dir)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
