from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from photon_evidence_companion import (
    E_CHARGE, H, LAMBDA_C, M_E, chi_square, common_mode_covariance,
    compton_recoil_energy_ev, compton_scattered_energy_ev, compton_shift,
    generalized_linear_fit, infer_scatterer_mass, photoelectric_stopping_potential,
    retarding_current, synthetic_compton_spectrum,
)

OUT = Path("generated/ch21/computational")
OUT.mkdir(parents=True, exist_ok=True)


def save(name: str) -> None:
    plt.tight_layout()
    plt.savefig(OUT / name)
    plt.close()


# 1: photoelectric I-V family
v = np.linspace(-2.5, 1.0, 600)
for vs in (0.8, 1.2, 1.6):
    plt.plot(v, retarding_current(v, vs, 1.0, 0.06), label=fr"$V_s={vs:.1f}$ V")
plt.xlabel("applied voltage (V)"); plt.ylabel("normalized photocurrent"); plt.legend()
save("photoelectric_iv_family.pdf")

# 2: stopping-potential fit with common-mode covariance
nu = np.linspace(5.5e14, 9.5e14, 9)
true_v = photoelectric_stopping_potential(nu, 2.25, 0.08)
noise = np.array([.010, -.006, .004, .012, -.009, .006, -.003, .008, -.005])
y = true_v + noise
cov = common_mode_covariance(np.full(nu.size, 0.015), 0.025)
fit = generalized_linear_fit(nu / 1e14, y, cov)
plt.errorbar(nu / 1e14, y, yerr=np.sqrt(np.diag(cov)), fmt="o", label="synthetic data")
xx = np.linspace(5.3, 9.7, 200)
plt.plot(xx, fit.slope * xx + fit.intercept, label="GLS fit")
plt.xlabel(r"frequency ($10^{14}$ Hz)"); plt.ylabel("stopping potential (V)"); plt.legend()
save("stopping_potential_fit.pdf")

# 3: work-function intercepts
materials = ["Cs-like", "Na-like", "Zn-like"]
phi = np.array([2.1, 2.7, 4.3])
intercepts = -phi + 0.1
plt.bar(materials, intercepts)
plt.ylabel("stopping-line intercept (V)")
save("work_function_intercepts.pdf")

# 4: Compton shift curve
angles = np.linspace(0.0, np.pi, 300)
plt.plot(np.rad2deg(angles), compton_shift(angles) * 1e12)
plt.xlabel("scattering angle (deg)"); plt.ylabel("wavelength shift (pm)")
save("compton_shift_curve.pdf")

# 5: energy partition
angles = np.linspace(0.0, np.pi, 300)
incident = 300e3
scattered = compton_scattered_energy_ev(incident, angles)
recoil = compton_recoil_energy_ev(incident, angles)
plt.plot(np.rad2deg(angles), scattered / incident, label="scattered photon")
plt.plot(np.rad2deg(angles), recoil / incident, label="recoil electron")
plt.xlabel("scattering angle (deg)"); plt.ylabel("fraction of incident energy"); plt.legend()
save("compton_energy_partition_companion.pdf")

# 6: detector broadening
energy = np.linspace(100.0, 700.0, 5000)
for sigma in (4.0, 10.0, 22.0):
    spec = synthetic_compton_spectrum(energy, 420.0, 662.0, sigma, background_level=0.0005)
    plt.plot(energy, spec / np.max(spec), label=fr"$\sigma={sigma:.0f}$ keV")
plt.xlabel("detected energy (keV)"); plt.ylabel("normalized counts"); plt.legend()
save("detector_broadening.pdf")

# 7: Compton mass fit
angle_data = np.deg2rad(np.array([25, 45, 70, 90, 120, 150], dtype=float))
shift_data = compton_shift(angle_data) + np.array([.004, -.003, .002, .001, -.004, .003]) * 1e-12
shift_cov = np.eye(angle_data.size) * (0.008e-12) ** 2
mass, mass_sigma = infer_scatterer_mass(angle_data, shift_data, shift_cov)
x = 1.0 - np.cos(angle_data)
plt.errorbar(x, shift_data * 1e12, yerr=np.sqrt(np.diag(shift_cov)) * 1e12, fmt="o")
xx = np.linspace(0.0, 2.0, 200)
plt.plot(xx, (H / (mass * 299792458.0)) * xx * 1e12)
plt.xlabel(r"$1-\cos\theta$"); plt.ylabel("wavelength shift (pm)")
save("compton_mass_fit.pdf")

# 8: model residual comparison
rng = np.random.default_rng(2026)
angles_deg = np.linspace(15, 165, 12)
truth = compton_shift(np.deg2rad(angles_deg)) * 1e12
observed = truth + rng.normal(0.0, 0.025, truth.size)
sigma = np.full(truth.size, 0.025)
plt.axhline(0.0, linewidth=0.8)
plt.plot(angles_deg, (observed - truth) / sigma, "o-", label="Compton model")
plt.plot(angles_deg, observed / sigma, "s--", label="null-shift model")
plt.xlabel("scattering angle (deg)"); plt.ylabel("normalized residual"); plt.legend()
save("residual_model_comparison.pdf")

# 9: Monte Carlo uncertainty correlation
rng = np.random.default_rng(721)
mean = np.array([H / E_CHARGE, -2.3])
parameter_cov = np.array([[0.04e-30, -0.7e-16], [-0.7e-16, 0.04]])
samples = rng.multivariate_normal(mean, parameter_cov, 4000)
plt.scatter(samples[:, 0] * 1e15, samples[:, 1], s=4, alpha=0.25)
plt.xlabel(r"slope ($10^{-15}$ V s)"); plt.ylabel("intercept (V)")
save("uncertainty_monte_carlo.pdf")

null = np.zeros_like(observed)
ind_cov = np.diag(sigma**2)
diagnostics = {
    "chapter": 21,
    "commit": 215,
    "photoelectric_fit_slope_V_s": fit.slope / 1e14,
    "photoelectric_fit_h_J_s": fit.slope / 1e14 * E_CHARGE,
    "photoelectric_fit_chi_square": fit.chi_square,
    "compton_wavelength_m": LAMBDA_C,
    "inferred_electron_mass_kg": mass,
    "inferred_electron_mass_sigma_kg": mass_sigma,
    "compton_model_chi_square": chi_square(observed, truth, ind_cov),
    "null_shift_chi_square": chi_square(observed, null, ind_cov),
    "generated_figures": 9,
}
(OUT / "diagnostics.json").write_text(json.dumps(diagnostics, indent=2) + "\n")
