from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from maxwell_induction_companion import (
    C0,
    EPS0,
    MU0,
    charge_relaxation,
    conduction_displacement_ratio,
    diffusion_convergence,
    diffusion_sine_mode,
    identical_coupled_mode_frequencies,
    lc_energy,
    lc_state,
    retardation_parameter,
    rl_current,
    sampled_vacuum_maxwell_residual,
    skin_depth,
)

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "generated/ch16/computational"
OUT.mkdir(parents=True, exist_ok=True)


def save(name: str) -> None:
    plt.tight_layout()
    plt.savefig(OUT / name, bbox_inches="tight")
    plt.close()


# 1. Regime map
eta = np.logspace(-5, 1, 240)
kappa = np.logspace(-5, 5, 240)
E, K = np.meshgrid(eta, kappa)
region = np.where(E >= 0.1, 2, np.where(K >= 1.0, 1, 0))
plt.figure(figsize=(6.4, 4.3))
plt.pcolormesh(eta, kappa, region, shading="auto", alpha=0.55)
plt.xscale("log"); plt.yscale("log")
plt.axvline(0.1, linestyle="--"); plt.axhline(1.0, linestyle="--")
plt.text(2e-4, 2e-3, "EQS"); plt.text(2e-4, 2e2, "MQS"); plt.text(0.35, 2e0, "full Maxwell")
plt.xlabel(r"retardation parameter $\eta=\omega a/c$")
plt.ylabel(r"current ratio $\sigma/(\omega\epsilon)$")
save("regime_map.pdf")

# 2. Current ratio
freq = np.logspace(-1, 10, 400)
for sigma in [1e-10, 1e-6, 1e-2, 1e6]:
    ratio = conduction_displacement_ratio(sigma, 2*np.pi*freq, 4*EPS0)
    plt.loglog(freq, ratio, label=fr"$\sigma={sigma:g}$ S/m")
plt.axhline(1.0, linestyle="--")
plt.xlabel("frequency (Hz)"); plt.ylabel("conduction/displacement current")
plt.legend(fontsize=8)
save("current_ratio.pdf")

# 3. Charge relaxation
x = np.linspace(0.0, 6.0, 300)
for tau in [0.2, 1.0, 3.0]:
    plt.plot(x, np.exp(-x/tau), label=fr"$\tau_e={tau:g}$")
plt.xlabel("time (arbitrary units)"); plt.ylabel(r"$\rho/\rho_0$")
plt.legend()
save("charge_relaxation.pdf")

# 4. Magnetic diffusion modes
space = np.linspace(0.0, 1.0, 300)
for mode in [1, 2, 3]:
    plt.plot(space, diffusion_sine_mode(space, 0.03, 1.0, 1.0, mode=mode), label=f"mode {mode}")
plt.xlabel(r"$x/a$"); plt.ylabel(r"$B/B_0$")
plt.legend()
save("magnetic_diffusion_modes.pdf")

# 5. Skin depth
freq = np.logspace(0, 8, 400)
for sigma in [1e5, 1e6, 5.8e7]:
    plt.loglog(freq, skin_depth(MU0, sigma, 2*np.pi*freq), label=fr"$\sigma={sigma:g}$ S/m")
plt.xlabel("frequency (Hz)"); plt.ylabel("skin depth (m)")
plt.legend(fontsize=8)
save("skin_depth.pdf")

# 6. Transients and energy
t = np.linspace(0.0, 8.0, 500)
current = rl_current(t, 1.0, 1.0, 1.0)
q, i = lc_state(t, 1.0, 1.0, 1.0)
energy_e = 0.5*q*q
energy_m = 0.5*i*i
plt.plot(t, current, label="RL current")
plt.plot(t, energy_e, label="LC electric energy")
plt.plot(t, energy_m, label="LC magnetic energy")
plt.plot(t, lc_energy(q, i, 1.0, 1.0), linestyle="--", label="LC total energy")
plt.xlabel("normalized time"); plt.ylabel("normalized quantity")
plt.legend(fontsize=8)
save("transients_energy.pdf")

# 7. Coupled modes
coupling = np.linspace(0.0, 0.9, 300)
ws, wa = identical_coupled_mode_frequencies(1.0, 1.0, coupling)
plt.plot(coupling, ws, label="symmetric")
plt.plot(coupling, wa, label="antisymmetric")
plt.xlabel("coupling coefficient $k$"); plt.ylabel(r"$\omega/\omega_0$")
plt.legend()
save("coupled_modes.pdf")

# 8. Maxwell residuals
points = np.array([31, 51, 81, 121, 181, 251])
results = [sampled_vacuum_maxwell_residual(int(n)) for n in points]
dx = np.array([r.dx for r in results])
rf = np.array([r.faraday_rms for r in results])
ra = np.array([r.ampere_rms for r in results])
plt.loglog(dx, rf, "o-", label="Faraday residual")
plt.loglog(dx, ra, "s-", label="Ampere-Maxwell residual")
plt.loglog(dx, 0.3*dx**2, linestyle="--", label="second-order guide")
plt.xlabel("grid spacing"); plt.ylabel("normalized RMS residual")
plt.legend(fontsize=8)
save("maxwell_residuals.pdf")

# 9. Diffusion convergence
spacings, errors, slope = diffusion_convergence([31, 41, 61, 81, 121, 161], final_time=0.03)
plt.loglog(spacings, errors, "o-", label=f"measured slope {slope:.2f}")
plt.loglog(spacings, errors[-1]*(spacings/spacings[-1])**2, linestyle="--", label="second-order guide")
plt.xlabel("grid spacing"); plt.ylabel("RMS error")
plt.legend()
save("diffusion_convergence.pdf")

summary = {
    "retardation_example": retardation_parameter(0.2, 2*np.pi*1e4),
    "copper_current_ratio_1MHz": conduction_displacement_ratio(5.8e7, 2*np.pi*1e6, EPS0),
    "copper_skin_depth_10kHz_m": float(skin_depth(MU0, 5.8e7, 2*np.pi*1e4)),
    "diffusion_convergence_slope": slope,
    "maxwell_faraday_residual_finest": float(rf[-1]),
    "maxwell_ampere_residual_finest": float(ra[-1]),
    "generated_figures": 9,
    "regression_tests_required": 14,
}
(OUT / "companion_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
print(json.dumps(summary, indent=2))
