"""Generate Chapter 24 computational figures and diagnostics."""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from schrodinger_companion import (
    E_CHARGE, HBAR, M_E, barrier_transmission, free_gaussian_wavefunction,
    harmonic_oscillator_energy, infinite_well_energy, infinite_well_state,
    potential_step_coefficients, probability_current, probability_density,
    probability_norm, solve_bound_states, split_step_propagate,
)

OUT = Path("generated/ch24/computational")
OUT.mkdir(parents=True, exist_ok=True)


def save(fig: plt.Figure, name: str) -> None:
    fig.tight_layout()
    fig.savefig(OUT / name, bbox_inches="tight")
    plt.close(fig)


# 1. Exact free Gaussian evolution.
x = np.linspace(-0.7e-6, 1.4e-6, 12000)
sigma0 = 8e-9
p0 = M_E * 1.2e6
fig, ax = plt.subplots(figsize=(7.2, 4.4))
for t in [0.0, 2e-13, 5e-13]:
    psi = free_gaussian_wavefunction(x, t, M_E, sigma0, mean_momentum_kg_m_s=p0)
    rho = probability_density(psi)
    ax.plot(x * 1e6, rho / rho.max(), label=f"t = {t*1e15:.0f} fs")
ax.set_xlabel("Position (micrometres)")
ax.set_ylabel("Density divided by its maximum")
ax.set_title("Exact free-packet translation and spreading")
ax.grid(True, alpha=0.25)
ax.legend()
save(fig, "free_gaussian_evolution.pdf")

# 2. Probability current across a travelling packet.
psi = free_gaussian_wavefunction(x, 2e-13, M_E, sigma0, mean_momentum_kg_m_s=p0)
rho = probability_density(psi)
j = probability_current(psi, x, M_E)
fig, ax = plt.subplots(figsize=(7.2, 4.4))
ax.plot(x * 1e6, rho / rho.max(), label="probability density")
ax.plot(x * 1e6, j / np.max(np.abs(j)), linestyle="--", label="probability current")
ax.set_xlabel("Position (micrometres)")
ax.set_ylabel("Normalized profile")
ax.set_title("Density and current for a travelling Gaussian packet")
ax.grid(True, alpha=0.25)
ax.legend()
save(fig, "packet_density_and_current.pdf")

# 3. Norm conservation under split-step propagation.
x_ss = np.linspace(-2e-7, 2e-7, 4096)
psi_ss = free_gaussian_wavefunction(x_ss, 0.0, M_E, 8e-9, mean_momentum_kg_m_s=M_E * 2e5)
dt = 2e-16
steps = np.arange(0, 501, 25)
norms = []
for n in steps:
    state = split_step_propagate(psi_ss, x_ss, np.zeros_like(x_ss), dt, int(n))
    norms.append(probability_norm(state, x_ss))
fig, ax = plt.subplots(figsize=(7.2, 4.4))
ax.plot(steps * dt * 1e15, np.asarray(norms) - 1.0, marker="o")
ax.set_xlabel("Propagation time (fs)")
ax.set_ylabel("Norm error")
ax.set_title("Unitary norm audit for split-step propagation")
ax.grid(True, alpha=0.25)
save(fig, "split_step_norm_conservation.pdf")

# 4. Infinite-well eigenstates.
width = 1.0e-9
x_well = np.linspace(0.0, width, 2401)
fig, ax = plt.subplots(figsize=(7.2, 4.4))
for n in range(1, 5):
    psi_n = infinite_well_state(n, x_well, width).real
    ax.plot(x_well * 1e9, psi_n * np.sqrt(width) + 2.3 * n, label=f"n = {n}")
ax.set_xlabel("Position (nm)")
ax.set_ylabel("Offset dimensionless wavefunction")
ax.set_title("Infinite-square-well stationary states")
ax.grid(True, alpha=0.25)
ax.legend(ncol=2)
save(fig, "infinite_well_eigenstates.pdf")

# 5. Finite well numerical spectrum.
x_fw = np.linspace(-2.5e-9, 2.5e-9, 701)
well_half = 0.65e-9
barrier = 2.5 * E_CHARGE
v_fw = np.where(np.abs(x_fw) <= well_half, 0.0, barrier)
sol_fw = solve_bound_states(x_fw, v_fw, 5)
fig, ax = plt.subplots(figsize=(7.2, 4.4))
ax.plot(x_fw * 1e9, v_fw / E_CHARGE, linewidth=2.0, label="potential")
for idx, energy in enumerate(sol_fw.energies_j):
    ax.axhline(energy / E_CHARGE, linestyle="--", linewidth=1.0, label=f"E{idx+1} = {energy/E_CHARGE:.3f} eV")
ax.set_xlabel("Position (nm)")
ax.set_ylabel("Energy (eV)")
ax.set_title("Finite-well spectrum from a finite-difference Hamiltonian")
ax.grid(True, alpha=0.25)
ax.legend(fontsize=8, ncol=2)
save(fig, "finite_well_numerical_spectrum.pdf")

# 6. Potential-step reflection and transmission.
ratio = np.linspace(1.001, 8.0, 1000)
r_values = []
t_values = []
for value in ratio:
    r, t = potential_step_coefficients(value, 1.0)
    r_values.append(r)
    t_values.append(t)
fig, ax = plt.subplots(figsize=(7.2, 4.4))
ax.plot(ratio, r_values, label="reflection R")
ax.plot(ratio, t_values, linestyle="--", label="transmission T")
ax.set_xlabel("Energy ratio E/V0")
ax.set_ylabel("Flux coefficient")
ax.set_title("Flux-conserving potential-step coefficients")
ax.grid(True, alpha=0.25)
ax.legend()
save(fig, "potential_step_flux_coefficients.pdf")

# 7. Barrier transmission and resonances.
energy = np.linspace(0.03, 4.0, 3000) * E_CHARGE
fig, ax = plt.subplots(figsize=(7.2, 4.4))
for width_nm in [0.35, 0.70, 1.05]:
    ax.semilogy(energy / E_CHARGE, barrier_transmission(energy, E_CHARGE, width_nm * 1e-9), label=f"a = {width_nm:.2f} nm")
ax.axvline(1.0, linestyle=":", linewidth=1.0)
ax.set_ylim(1e-8, 1.1)
ax.set_xlabel("Energy (eV)")
ax.set_ylabel("Transmission probability")
ax.set_title("Rectangular-barrier tunnelling and above-barrier resonances")
ax.grid(True, alpha=0.25)
ax.legend()
save(fig, "barrier_transmission_resonances.pdf")

# 8. Exponential thickness sensitivity below the barrier.
widths = np.linspace(0.1e-9, 1.5e-9, 500)
fig, ax = plt.subplots(figsize=(7.2, 4.4))
for e_ev in [0.15, 0.30, 0.60]:
    ax.semilogy(widths * 1e9, [float(barrier_transmission(e_ev * E_CHARGE, E_CHARGE, w)) for w in widths], label=f"E = {e_ev:.2f} eV")
ax.set_xlabel("Barrier width (nm)")
ax.set_ylabel("Transmission probability")
ax.set_title("Exponential tunnelling sensitivity to barrier width")
ax.grid(True, alpha=0.25)
ax.legend()
save(fig, "tunnelling_thickness_sensitivity.pdf")

# 9. Harmonic oscillator numerical versus exact spectrum.
omega = 2.0e15
x_ho = np.linspace(-1.4e-9, 1.4e-9, 701)
v_ho = 0.5 * M_E * omega**2 * x_ho**2
sol_ho = solve_bound_states(x_ho, v_ho, 8)
levels = np.arange(8)
exact_ho = np.array([harmonic_oscillator_energy(int(n), omega) for n in levels])
fig, ax = plt.subplots(figsize=(7.2, 4.4))
ax.plot(levels, exact_ho / E_CHARGE, marker="o", label="exact")
ax.plot(levels, sol_ho.energies_j / E_CHARGE, marker="x", linestyle="none", label="finite difference")
ax.set_xlabel("Level n")
ax.set_ylabel("Energy (eV)")
ax.set_title("Harmonic-oscillator spectrum: exact and numerical")
ax.grid(True, alpha=0.25)
ax.legend()
save(fig, "harmonic_oscillator_spectrum_audit.pdf")

# Machine-readable diagnostics.
step_r, step_t = potential_step_coefficients(2.0, 1.0)
diagnostics = {
    "generated_figure_count": 9,
    "chapter24_regression_test_count": 26,
    "free_packet_norm_500fs": probability_norm(free_gaussian_wavefunction(x, 5e-13, M_E, sigma0, mean_momentum_kg_m_s=p0), x),
    "split_step_max_abs_norm_error": float(np.max(np.abs(np.asarray(norms) - 1.0))),
    "infinite_well_ground_energy_eV_1nm": infinite_well_energy(1, width) / E_CHARGE,
    "finite_well_lowest_energy_eV": float(sol_fw.energies_j[0] / E_CHARGE),
    "step_reflection_E_over_V0_2": step_r,
    "step_transmission_E_over_V0_2": step_t,
    "barrier_transmission_E0p3eV_V1eV_a0p7nm": float(barrier_transmission(0.3 * E_CHARGE, E_CHARGE, 0.7e-9)),
    "oscillator_ground_energy_eV": harmonic_oscillator_energy(0, omega) / E_CHARGE,
    "oscillator_fd_relative_error_n0": float(abs(sol_ho.energies_j[0] - exact_ho[0]) / exact_ho[0]),
}
(OUT / "diagnostics.json").write_text(json.dumps(diagnostics, indent=2) + "\n", encoding="utf-8")
print(json.dumps(diagnostics, indent=2))
