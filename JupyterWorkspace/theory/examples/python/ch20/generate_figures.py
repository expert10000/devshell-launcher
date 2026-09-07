from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from blackbody_companion import (
    C, KB, H, WIEN_B, band_fraction, convolve_gaussian,
    finite_difference_log_slope, fit_graybody_temperature,
    normalized_gaussian_response, planck_frequency, planck_wavelength,
    rayleigh_jeans_frequency, spectral_radiance_wavelength,
    total_exitance, two_color_temperature, wien_frequency,
)

OUT = Path("generated/ch20/computational")
OUT.mkdir(parents=True, exist_ok=True)


def save(name: str) -> None:
    plt.tight_layout()
    plt.savefig(OUT / f"{name}.pdf", bbox_inches="tight")
    plt.close()


# 1: Planck family in wavelength representation
lam = np.geomspace(0.2e-6, 40e-6, 1000)
for t in (300.0, 600.0, 1200.0, 3000.0):
    plt.plot(lam * 1e6, planck_wavelength(lam, t), label=f"{t:g} K")
plt.xscale("log")
plt.yscale("log")
plt.xlabel("wavelength (micrometres)")
plt.ylabel(r"$u_\lambda$ (J m$^{-4}$)")
plt.legend()
save("planck_family_wavelength")

# 2: Universal dimensionless collapse
x = np.geomspace(1e-2, 30.0, 1000)
y = x**3 / np.expm1(x)
plt.plot(x, y)
plt.xscale("log")
plt.xlabel(r"$x=h\nu/(k_{\mathrm{B}}T)$")
plt.ylabel(r"$x^3/(e^x-1)$")
save("dimensionless_collapse")

# 3: Asymptotic comparison
nu = np.geomspace(1e10, 2e15, 1200)
t = 1800.0
plt.plot(nu, planck_frequency(nu, t), label="Planck")
plt.plot(nu, rayleigh_jeans_frequency(nu, t), label="Rayleigh-Jeans")
plt.plot(nu, wien_frequency(nu, t), label="Wien")
plt.xscale("log")
plt.yscale("log")
plt.ylim(1e-22, 2e-13)
plt.xlabel("frequency (Hz)")
plt.ylabel(r"$u_\nu$ (J m$^{-3}$ Hz$^{-1}$)")
plt.legend()
save("asymptotic_comparison")

# 4: Stefan-Boltzmann slope
T = np.geomspace(100.0, 6000.0, 200)
M = np.array([total_exitance(v) for v in T])
plt.plot(T, M)
plt.xscale("log")
plt.yscale("log")
plt.xlabel("temperature (K)")
plt.ylabel(r"exitance (W m$^{-2}$)")
save("stefan_boltzmann_scaling")

# 5: Wien peak scaling
T2 = np.linspace(250.0, 5000.0, 250)
peak = WIEN_B / T2
plt.plot(T2, peak * 1e6)
plt.xlabel("temperature (K)")
plt.ylabel("wavelength-density peak (micrometres)")
save("wien_peak_scaling")

# 6: Fraction in selected bands
T3 = np.linspace(200.0, 1800.0, 140)
f_3_5 = np.array([band_fraction(v, 3e-6, 5e-6, points=1800) for v in T3])
f_8_14 = np.array([band_fraction(v, 8e-6, 14e-6, points=1800) for v in T3])
plt.plot(T3, f_3_5, label="3-5 micrometres")
plt.plot(T3, f_8_14, label="8-14 micrometres")
plt.xlabel("temperature (K)")
plt.ylabel("fraction of total exitance")
plt.legend()
save("band_fractions")

# 7: Instrument broadening
lam_u = np.linspace(1e-6, 15e-6, 3000)
true = spectral_radiance_wavelength(lam_u, 900.0)
blurred = convolve_gaussian(lam_u, true, 1.0e-6)
plt.plot(lam_u * 1e6, true / np.max(true), label="intrinsic")
plt.plot(lam_u * 1e6, blurred / np.max(blurred), label="1 micrometre FWHM")
plt.xlabel("wavelength (micrometres)")
plt.ylabel("normalized radiance")
plt.legend()
save("instrument_broadening")

# 8: Two-color ratio thermometer
T4 = np.linspace(500.0, 5000.0, 400)
lam1, lam2 = 1.2e-6, 1.8e-6
ratios = []
for temp in T4:
    b = spectral_radiance_wavelength(np.array([lam1, lam2]), temp)
    ratios.append(b[0] / b[1])
plt.plot(T4, ratios)
plt.xlabel("temperature (K)")
plt.ylabel(r"$B_{1.2\,\mu m}/B_{1.8\,\mu m}$")
save("two_color_ratio")

# 9: Synthetic fit and residuals
rng = np.random.default_rng(20260803)
lam_f = np.linspace(2e-6, 12e-6, 70)
true_t, eps = 1250.0, 0.68
clean = eps * spectral_radiance_wavelength(lam_f, true_t)
unc = np.maximum(0.02 * clean, np.max(clean) * 2e-4)
measured = clean + rng.normal(0.0, unc)
fit = fit_graybody_temperature(lam_f, measured, unc, np.arange(1100.0, 1401.0, 2.0))
model = fit.scale * spectral_radiance_wavelength(lam_f, fit.temperature)
plt.plot(lam_f * 1e6, measured, marker="o", linestyle="none", label="synthetic data")
plt.plot(lam_f * 1e6, model, label="best graybody fit")
plt.xlabel("wavelength (micrometres)")
plt.ylabel(r"radiance (W m$^{-3}$ sr$^{-1}$)")
plt.legend()
save("graybody_fit")

slope = finite_difference_log_slope(T, M)
b = spectral_radiance_wavelength(np.array([lam1, lam2]), 2200.0)
inferred_two_color = two_color_temperature(lam1, lam2, float(b[0] / b[1]))
diagnostics = {
    "stefan_boltzmann_log_slope_median": float(np.median(slope[3:-3])),
    "wien_constant_m_K": WIEN_B,
    "graybody_true_temperature_K": true_t,
    "graybody_fit_temperature_K": fit.temperature,
    "graybody_fit_scale": fit.scale,
    "graybody_fit_chi_square": fit.chi_square,
    "two_color_round_trip_temperature_K": inferred_two_color,
    "dimensionless_peak_frequency_x": float(x[np.argmax(y)]),
}
(OUT / "diagnostics.json").write_text(json.dumps(diagnostics, indent=2) + "\n")
print(json.dumps(diagnostics, indent=2))
