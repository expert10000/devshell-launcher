"""Generate Chapter 23 computational figures and diagnostics."""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from wave_particle_companion import (
    C, E_CHARGE, HBAR, M_C60, M_E, M_N,
    bragg_angle_rad, de_broglie_wavelength_from_speed,
    distinguishability_bound, double_slit_intensity,
    electron_wavelength_from_voltage, fourier_sigma_k,
    gaussian_packet_density, gaussian_packet_width_m,
    marker_overlap_visibility, phase_velocity_relativistic,
    relativistic_momentum, sample_detection_events,
)

OUT = Path("generated/ch23/computational")
OUT.mkdir(parents=True, exist_ok=True)


def save(fig: plt.Figure, name: str) -> None:
    fig.tight_layout()
    fig.savefig(OUT / name, bbox_inches="tight")
    plt.close(fig)


# 1. Electron wavelength versus accelerating voltage.
voltage = np.geomspace(1.0, 2.0e5, 500)
fig, ax = plt.subplots(figsize=(7.2, 4.4))
ax.loglog(voltage, electron_wavelength_from_voltage(voltage, relativistic=False) * 1e12, label="nonrelativistic")
ax.loglog(voltage, electron_wavelength_from_voltage(voltage, relativistic=True) * 1e12, linestyle="--", label="relativistic")
ax.set_xlabel("Accelerating voltage (V)")
ax.set_ylabel("Electron wavelength (pm)")
ax.set_title("Electron de Broglie wavelength")
ax.grid(True, alpha=0.25)
ax.legend()
save(fig, "electron_wavelength_voltage.pdf")

# 2. Relativistic correction.
correction = electron_wavelength_from_voltage(voltage, relativistic=True) / electron_wavelength_from_voltage(voltage, relativistic=False)
fig, ax = plt.subplots(figsize=(7.2, 4.4))
ax.semilogx(voltage, 100.0 * (1.0 - correction))
ax.set_xlabel("Accelerating voltage (V)")
ax.set_ylabel("Wavelength reduction (%)")
ax.set_title("Relativistic correction to electron wavelength")
ax.grid(True, alpha=0.25)
save(fig, "relativistic_wavelength_correction.pdf")

# 3. Phase and group velocity.
beta = np.linspace(0.05, 0.95, 500)
fig, ax = plt.subplots(figsize=(7.2, 4.4))
ax.plot(beta, beta, label=r"group velocity $v_g/c$")
ax.plot(beta, phase_velocity_relativistic(beta * C) / C, label=r"phase velocity $v_p/c$")
ax.axhline(1.0, linestyle=":", linewidth=1.0)
ax.set_ylim(0.0, 6.0)
ax.set_xlabel(r"Particle speed $v/c$")
ax.set_ylabel("Velocity in units of c")
ax.set_title("Relativistic matter-wave phase and group velocities")
ax.grid(True, alpha=0.25)
ax.legend()
save(fig, "phase_group_velocity_relativistic.pdf")

# 4. Gaussian packet spreading.
sigma0 = 2.0e-9
p0 = M_E * 1.5e6
time_values = [0.0, 2.0e-13, 5.0e-13]
x = np.linspace(-0.5e-6, 1.3e-6, 12000)
fig, ax = plt.subplots(figsize=(7.2, 4.4))
for t in time_values:
    rho = gaussian_packet_density(x, t, M_E, sigma0, mean_momentum_kg_m_s=p0)
    ax.plot(x * 1e6, rho / rho.max(), label=f"t = {t*1e15:.0f} fs")
ax.set_xlabel("Position (micrometres)")
ax.set_ylabel("Normalized probability density")
ax.set_title("Translation and spreading of a Gaussian packet")
ax.grid(True, alpha=0.25)
ax.legend()
save(fig, "gaussian_packet_spreading.pdf")

# 5. Fourier width tradeoff.
sigma_x = np.geomspace(1e-12, 1e-6, 500)
sigma_p = HBAR * fourier_sigma_k(sigma_x)
fig, ax = plt.subplots(figsize=(7.2, 4.4))
ax.loglog(sigma_x, sigma_p)
ax.set_xlabel(r"Position width $\sigma_x$ (m)")
ax.set_ylabel(r"Momentum width $\sigma_p$ (kg m s$^{-1}$)")
ax.set_title(r"Minimum Gaussian Fourier tradeoff: $\sigma_x\sigma_p=\hbar/2$")
ax.grid(True, alpha=0.25)
save(fig, "fourier_width_product.pdf")

# 6. Bragg-angle map for accelerated electrons.
voltages = np.geomspace(20.0, 5.0e4, 350)
spacings = [0.091e-9, 0.123e-9, 0.203e-9]
fig, ax = plt.subplots(figsize=(7.2, 4.4))
for spacing in spacings:
    angles = []
    valid_v = []
    for v in voltages:
        wavelength = float(electron_wavelength_from_voltage(v))
        if wavelength <= 2.0 * spacing:
            valid_v.append(v)
            angles.append(np.degrees(bragg_angle_rad(wavelength, spacing)))
    ax.semilogx(valid_v, angles, label=f"d = {spacing*1e12:.0f} pm")
ax.set_xlabel("Accelerating voltage (V)")
ax.set_ylabel("First-order Bragg angle (degrees)")
ax.set_title("Electron diffraction angle map")
ax.grid(True, alpha=0.25)
ax.legend()
save(fig, "bragg_angle_voltage_map.pdf")

# 7. Localized-event buildup.
screen = np.linspace(-4e-3, 4e-3, 3001)
prob = double_slit_intensity(screen, 100e-12, 1.0, 2.0e-6, visibility=0.92, slit_width_m=0.7e-6)
events = sample_detection_events(screen, prob, 12000, seed=237)
fig, ax = plt.subplots(figsize=(7.2, 4.4))
ax.hist(events * 1e3, bins=120, density=True, alpha=0.65, label="localized detections")
ax.plot(screen * 1e3, prob * 1e-3, linewidth=1.5, label="predicted density")
ax.set_xlabel("Screen coordinate (mm)")
ax.set_ylabel("Normalized count density")
ax.set_title("Single-event accumulation into an interference pattern")
ax.grid(True, alpha=0.25)
ax.legend()
save(fig, "single_event_buildup_computational.pdf")

# 8. Visibility-distinguishability boundary.
visibility = np.linspace(0.0, 1.0, 500)
fig, ax = plt.subplots(figsize=(5.6, 5.0))
ax.plot(visibility, distinguishability_bound(visibility), label=r"$D=\sqrt{1-V^2}$")
ax.fill_between(visibility, 0.0, distinguishability_bound(visibility), alpha=0.2, label=r"allowed $V^2+D^2\leq1$")
ax.set_aspect("equal", adjustable="box")
ax.set_xlim(0.0, 1.03)
ax.set_ylim(0.0, 1.03)
ax.set_xlabel("Visibility V")
ax.set_ylabel("Distinguishability D")
ax.set_title("Quantitative complementarity")
ax.grid(True, alpha=0.25)
ax.legend()
save(fig, "visibility_distinguishability_bound.pdf")

# 9. Marker overlap and fringe washout.
fig, ax = plt.subplots(figsize=(7.2, 4.4))
for overlap in [1.0, 0.65, 0.25, 0.0]:
    vis = marker_overlap_visibility(overlap)
    intensity = double_slit_intensity(screen, 100e-12, 1.0, 2.0e-6, visibility=vis)
    ax.plot(screen * 1e3, intensity / intensity.max(), label=f"|overlap| = {overlap:.2f}")
ax.set_xlabel("Screen coordinate (mm)")
ax.set_ylabel("Normalized intensity")
ax.set_title("Which-way marker overlap controls fringe visibility")
ax.grid(True, alpha=0.25)
ax.legend()
save(fig, "marker_overlap_fringe_washout.pdf")

# Machine-readable release diagnostics.
v150 = float(electron_wavelength_from_voltage(150.0))
v100k_rel = float(electron_wavelength_from_voltage(100_000.0, relativistic=True))
v100k_nr = float(electron_wavelength_from_voltage(100_000.0, relativistic=False))
packet_ratio = float(gaussian_packet_width_m(sigma0, 5e-13, M_E) / sigma0)
diagnostics = {
    "generated_figure_count": 9,
    "chapter23_regression_test_count": 23,
    "electron_wavelength_150V_pm": v150 * 1e12,
    "electron_wavelength_100kV_pm": v100k_rel * 1e12,
    "relativistic_to_nonrelativistic_wavelength_100kV": v100k_rel / v100k_nr,
    "gaussian_packet_width_ratio_500fs": packet_ratio,
    "minimum_uncertainty_product_over_hbar": 0.5,
    "first_order_bragg_angle_deg_150V_d203pm": float(np.degrees(bragg_angle_rad(v150, 0.203e-9))),
    "single_event_sample_count": int(events.size),
    "visibility_for_marker_overlap_0_65": marker_overlap_visibility(0.65),
    "neutron_wavelength_at_1000m_s_pm": float(de_broglie_wavelength_from_speed(M_N, 1000.0, relativistic=False) * 1e12),
    "c60_wavelength_at_100m_s_pm": float(de_broglie_wavelength_from_speed(M_C60, 100.0, relativistic=False) * 1e12),
}
(OUT / "diagnostics.json").write_text(json.dumps(diagnostics, indent=2) + "\n", encoding="utf-8")
print(json.dumps(diagnostics, indent=2))
