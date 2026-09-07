"""Generate deterministic Chapter 12 computational figures and diagnostics."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from classical_fields import (
    dirichlet_green_matrix,
    electric_field_1d,
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


def save_figure(path: Path) -> None:
    plt.tight_layout()
    plt.savefig(path, metadata={"CreationDate": None, "ModDate": None})
    plt.close()


def make_outputs(output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)

    # Periodic wave packet.
    points = 401
    length = 20.0
    x = np.linspace(-length / 2.0, length / 2.0, points, endpoint=False)
    dx = length / points
    speed = 1.0
    dt = 0.45 * dx / speed
    initial = np.exp(-((x + 3.0) / 1.1) ** 2) * np.cos(3.0 * (x + 3.0))
    velocity = -speed * np.gradient(initial, dx, edge_order=2)
    history = wave_leapfrog(initial, velocity, dx, dt, 700, speed=speed)
    snapshot_indices = [0, 180, 360, 540]
    plt.figure(figsize=(7.0, 4.6))
    for index in snapshot_indices:
        plt.plot(x, history[index], label=f"t={index * dt:.2f}")
    plt.xlabel("x")
    plt.ylabel("field amplitude")
    plt.legend()
    save_figure(output_dir / "wave_packet_snapshots.pdf")

    energies = wave_energy(history, dx, dt, speed=speed)
    relative_energy = (energies - energies[0]) / energies[0]
    plt.figure(figsize=(6.8, 4.2))
    plt.plot(dt * np.arange(1, history.shape[0] - 1), relative_energy)
    plt.xlabel("time")
    plt.ylabel("relative discrete energy change")
    save_figure(output_dir / "wave_energy_diagnostic.pdf")

    # CFL comparison.
    stable_dt = 0.9 * dx / speed
    unstable_dt = 1.08 * dx / speed
    stable = wave_leapfrog(initial, np.zeros_like(initial), dx, stable_dt, 260, speed=speed)
    unstable = wave_leapfrog(initial, np.zeros_like(initial), dx, unstable_dt, 260, speed=speed)
    plt.figure(figsize=(6.8, 4.3))
    plt.semilogy(np.max(np.abs(stable), axis=1), label="Courant 0.90")
    plt.semilogy(np.max(np.abs(unstable), axis=1), label="Courant 1.08")
    plt.xlabel("time step")
    plt.ylabel("maximum absolute field")
    plt.legend()
    save_figure(output_dir / "cfl_stability_comparison.pdf")

    # Laplacian convergence.
    grid_sizes = np.array([40, 80, 160, 320, 640])
    spacings = 2.0 * np.pi / grid_sizes
    errors = []
    for count, spacing in zip(grid_sizes, spacings):
        grid = np.arange(count) * spacing
        numerical = periodic_laplacian(np.sin(3.0 * grid), spacing)
        exact = -9.0 * np.sin(3.0 * grid)
        errors.append(np.sqrt(np.mean((numerical - exact) ** 2)))
    errors = np.asarray(errors)
    order = observed_order(errors, spacings)
    plt.figure(figsize=(6.2, 4.4))
    plt.loglog(spacings, errors, "o-", label=f"observed order {order:.3f}")
    plt.loglog(spacings, errors[-1] * (spacings / spacings[-1]) ** 2, "--", label="second-order guide")
    plt.xlabel("grid spacing")
    plt.ylabel("RMS Laplacian error")
    plt.legend()
    save_figure(output_dir / "finite_difference_convergence.pdf")

    # Klein--Gordon phase and group velocities.
    k = np.linspace(0.05, 6.0, 500)
    omega = klein_gordon_dispersion(k, speed=1.0, mass_frequency=1.4)
    phase_velocity = omega / k
    group_velocity = k / omega
    plt.figure(figsize=(6.6, 4.4))
    plt.plot(k, omega, label=r"$\omega(k)$")
    plt.plot(k, phase_velocity, label="phase velocity")
    plt.plot(k, group_velocity, label="group velocity")
    plt.xlabel("wavenumber k")
    plt.ylabel("dimensionless value")
    plt.legend()
    save_figure(output_dir / "klein_gordon_dispersion.pdf")

    # Poisson response by matrix and Green kernel.
    x_p = np.linspace(0.0, 1.0, 241)
    dx_p = x_p[1] - x_p[0]
    source = np.exp(-((x_p - 0.38) / 0.07) ** 2) - 0.55 * np.exp(-((x_p - 0.72) / 0.10) ** 2)
    solution = solve_poisson_dirichlet(source, dx_p)
    green = dirichlet_green_matrix(x_p)
    green_solution = green @ source * dx_p
    plt.figure(figsize=(6.8, 4.6))
    plt.plot(x_p, source / np.max(np.abs(source)), label="normalized source")
    plt.plot(x_p, solution / np.max(np.abs(solution)), label="finite-difference response")
    plt.plot(x_p, green_solution / np.max(np.abs(green_solution)), "--", label="Green-kernel response")
    plt.xlabel("x")
    plt.ylabel("normalized amplitude")
    plt.legend()
    save_figure(output_dir / "poisson_green_response.pdf")

    # Gauge-invariance test in 1+1 dimensions.
    nt = 121
    nx = 241
    times = np.linspace(0.0, 2.0, nt)
    x_g = np.linspace(0.0, 2.0 * np.pi, nx, endpoint=False)
    dt_g = times[1] - times[0]
    dx_g = x_g[1] - x_g[0]
    tt, xx = np.meshgrid(times, x_g, indexing="ij")
    phi = 0.35 * np.cos(xx - 0.8 * tt)
    ax = 0.22 * np.sin(2.0 * xx + 0.4 * tt)
    chi = 0.18 * np.sin(xx) * np.cos(0.7 * tt)
    electric_before = electric_field_1d(phi, ax, dx_g, dt_g)
    transformed_phi, transformed_ax = gauge_transform_1d(phi, ax, chi, dx_g, dt_g)
    electric_after = electric_field_1d(transformed_phi, transformed_ax, dx_g, dt_g)
    gauge_error = np.max(np.abs(electric_before[2:-2] - electric_after[2:-2]))
    middle = nt // 2
    plt.figure(figsize=(6.8, 4.3))
    plt.plot(x_g, electric_before[middle], label="before gauge transformation")
    plt.plot(x_g, electric_after[middle], "--", label="after gauge transformation")
    plt.xlabel("x")
    plt.ylabel(r"$E_x$")
    plt.legend()
    save_figure(output_dir / "gauge_invariance_diagnostic.pdf")

    # Static sine--Gordon kink and field energy density.
    x_s = np.linspace(-9.0, 9.0, 1201)
    dx_s = x_s[1] - x_s[0]
    kink = sine_gordon_static_kink(x_s)
    gradient = np.gradient(kink, dx_s, edge_order=2)
    density = 0.5 * gradient**2 + 1.0 - np.cos(kink)
    residual = sine_gordon_static_residual(kink, dx_s)
    plt.figure(figsize=(6.8, 4.4))
    plt.plot(x_s, kink, label="kink field")
    plt.plot(x_s, density, label="energy density")
    plt.xlabel("x")
    plt.ylabel("field / density")
    plt.legend()
    save_figure(output_dir / "sine_gordon_kink.pdf")

    diagnostics = [
        {"quantity": "wave_max_relative_energy_change", "value": float(np.max(np.abs(relative_energy)))},
        {"quantity": "laplacian_observed_order", "value": float(order)},
        {"quantity": "poisson_green_max_difference", "value": float(np.max(np.abs(solution - green_solution)))},
        {"quantity": "gauge_electric_max_difference", "value": float(gauge_error)},
        {"quantity": "sine_gordon_max_static_residual", "value": float(np.max(np.abs(residual[20:-20])))},
    ]
    summary = {
        "wave": {
            "courant": wave_cfl_report(speed, dt, dx).courant_number,
            "maximum_relative_energy_change": diagnostics[0]["value"],
        },
        "cfl": {
            "stable_case": wave_cfl_report(speed, stable_dt, dx).__dict__,
            "unstable_case": wave_cfl_report(speed, unstable_dt, dx).__dict__,
            "unstable_amplification": float(np.max(np.abs(unstable[-1])) / np.max(np.abs(unstable[0]))),
        },
        "convergence": {"observed_order": float(order)},
        "poisson": {"maximum_green_difference": diagnostics[2]["value"]},
        "gauge": {"maximum_electric_field_difference": diagnostics[3]["value"]},
        "sine_gordon": {"maximum_static_residual": diagnostics[4]["value"]},
    }
    (output_dir / "companion_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    with (output_dir / "numerical_diagnostics.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["quantity", "value"])
        writer.writeheader()
        writer.writerows(diagnostics)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("generated/ch12/computational"))
    arguments = parser.parse_args()
    print(json.dumps(make_outputs(arguments.output_dir), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
