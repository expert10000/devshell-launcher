"""Generate Chapter 22 computational figures and diagnostics."""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from atomic_spectra_companion import (
    C, E_CHARGE, H, M_D, M_P, R_INF,
    adjacent_transition_frequency_hz, bohr_energy_ev, classical_orbital_frequency_hz,
    finite_mass_rydberg, gaussian_profile, isotope_shift_wavelength_m,
    reconstruct_ritz_terms, rydberg_wavenumber, series_limit_wavelength_m,
    series_wavelength_m, synthetic_line_spectrum, zeeman_frequency_shift_hz,
)

OUT = Path("generated/ch22/computational")
OUT.mkdir(parents=True, exist_ok=True)


def save(fig: plt.Figure, name: str) -> None:
    fig.tight_layout()
    fig.savefig(OUT / name, bbox_inches="tight")
    plt.close(fig)


# 1. Hydrogen-series map
fig, ax = plt.subplots(figsize=(7.2, 4.4))
series = [(1, "Lyman"), (2, "Balmer"), (3, "Paschen"), (4, "Brackett")]
for lower, label in series:
    upper = np.arange(lower + 1, lower + 8)
    wavelength_nm = np.array([series_wavelength_m(lower, int(n), finite_mass_rydberg(M_P)) for n in upper]) * 1e9
    ax.scatter(wavelength_nm, np.full_like(wavelength_nm, lower), label=label)
ax.set_xscale("log")
ax.set_yticks([1, 2, 3, 4], [x[1] for x in series])
ax.set_xlabel("Wavelength (nm, logarithmic scale)")
ax.set_ylabel("Hydrogen series")
ax.set_title("Hydrogen spectral-series map")
ax.grid(True, alpha=0.25)
save(fig, "hydrogen_series_map.pdf")

# 2. Rydberg linear fit
n_upper = np.arange(3, 13)
x = 1.0 / n_upper**2
true_y = np.array([rydberg_wavenumber(2, int(n), finite_mass_rydberg(M_P)) for n in n_upper])
rng = np.random.default_rng(220)
sigma = 12.0
measured = true_y + rng.normal(0.0, sigma, size=true_y.size)
coeff = np.polyfit(x, measured, 1)
fit = np.polyval(coeff, x)
fig, ax = plt.subplots(figsize=(7.2, 4.4))
ax.errorbar(x, measured, yerr=sigma, fmt="o", label="synthetic measurements")
order = np.argsort(x)
ax.plot(x[order], fit[order], label="linear fit")
ax.set_xlabel(r"$1/n_u^2$")
ax.set_ylabel(r"Wavenumber (m$^{-1}$)")
ax.set_title("Balmer-series Rydberg fit")
ax.grid(True, alpha=0.25)
ax.legend()
save(fig, "rydberg_linear_fit.pdf")

# 3. Series-limit convergence
fig, ax = plt.subplots(figsize=(7.2, 4.4))
for lower, label in [(1, "Lyman"), (2, "Balmer"), (3, "Paschen")]:
    upper = np.arange(lower + 1, 31)
    wavelengths = np.array([series_wavelength_m(lower, int(n), R_INF) for n in upper]) * 1e9
    limit = series_limit_wavelength_m(lower, R_INF) * 1e9
    ax.plot(upper, wavelengths - limit, marker="o", ms=2.5, label=label)
ax.set_yscale("log")
ax.set_xlabel(r"Upper principal index $n_u$")
ax.set_ylabel(r"$\lambda_{n_u}-\lambda_{limit}$ (nm)")
ax.set_title("Convergence toward hydrogen series limits")
ax.grid(True, alpha=0.25)
ax.legend()
save(fig, "series_limit_convergence.pdf")

# 4. Isotope shift comparison
transitions = [(2, 3), (2, 4), (2, 5), (1, 2), (3, 4)]
labels = [f"{u}->{l}" for l, u in transitions]
shifts_pm = np.array([isotope_shift_wavelength_m(l, u) for l, u in transitions]) * 1e12
fig, ax = plt.subplots(figsize=(7.2, 4.4))
ax.bar(labels, shifts_pm)
ax.axhline(0.0, linewidth=0.8)
ax.set_ylabel("Deuterium minus hydrogen wavelength (pm)")
ax.set_xlabel("Transition")
ax.set_title("Reduced-mass isotope shifts")
ax.grid(True, axis="y", alpha=0.25)
save(fig, "isotope_shift_comparison.pdf")

# 5. Bohr energy ladder
n = np.arange(1, 9)
energies = np.array([bohr_energy_ev(int(i)) for i in n])
fig, ax = plt.subplots(figsize=(6.4, 5.0))
for ni, energy in zip(n, energies, strict=True):
    ax.hlines(energy, 0.15, 0.85)
    ax.text(0.89, energy, f"n={ni}", va="center", fontsize=8)
ax.set_xlim(0.0, 1.2)
ax.set_xticks([])
ax.set_ylabel("Energy (eV)")
ax.set_title("Hydrogen Bohr energy ladder")
ax.grid(True, axis="y", alpha=0.25)
save(fig, "bohr_energy_ladder_companion.pdf")

# 6. Correspondence ratio
n = np.arange(3, 101)
ratio = np.array([adjacent_transition_frequency_hz(int(i)) / classical_orbital_frequency_hz(int(i)) for i in n])
fig, ax = plt.subplots(figsize=(7.2, 4.4))
ax.plot(n, ratio)
ax.axhline(1.0, linestyle="--", linewidth=1.0)
ax.set_xlabel("Principal index n")
ax.set_ylabel("Adjacent transition / orbital frequency")
ax.set_title("Correspondence limit")
ax.grid(True, alpha=0.25)
save(fig, "correspondence_frequency_ratio.pdf")

# 7. Zeeman triplet resolution
center_nm = 500.0
wavelength = center_nm * 1e-9
field = 1.0
frequency_shift = zeeman_frequency_shift_hz(1, field)
wavelength_shift = wavelength**2 * frequency_shift / C
x_nm = np.linspace(center_nm - 0.08, center_nm + 0.08, 4000)
for resolution_pm, linestyle in [(6.0, "-"), (20.0, "--")]:
    sigma = resolution_pm * 1e-3 / 2.355
    centers = [center_nm - wavelength_shift * 1e9, center_nm, center_nm + wavelength_shift * 1e9]
    profile = synthetic_line_spectrum(x_nm * 1e-9, np.array(centers) * 1e-9, sigma * 1e-9, [1.0, 1.0, 1.0])
    profile /= profile.max()
    plt.plot(x_nm, profile, linestyle=linestyle, label=f"FWHM {resolution_pm:g} pm")
plt.xlabel("Wavelength (nm)")
plt.ylabel("Normalized intensity")
plt.title("Instrument resolution of a Zeeman triplet")
plt.grid(True, alpha=0.25)
plt.legend()
fig = plt.gcf()
save(fig, "zeeman_triplet_resolution.pdf")

# 8. Instrument broadening
x = np.linspace(655.5, 657.2, 4000)
centers = np.array([656.10, 656.28, 656.46])
fig, ax = plt.subplots(figsize=(7.2, 4.4))
for fwhm_nm in [0.03, 0.10, 0.30]:
    sigma_nm = fwhm_nm / 2.355
    spectrum = synthetic_line_spectrum(x * 1e-9, centers * 1e-9, sigma_nm * 1e-9, [0.7, 1.0, 0.5])
    spectrum /= spectrum.max()
    ax.plot(x, spectrum, label=f"FWHM {fwhm_nm:.2f} nm")
ax.set_xlabel("Wavelength (nm)")
ax.set_ylabel("Normalized intensity")
ax.set_title("Line blending under instrumental broadening")
ax.grid(True, alpha=0.25)
ax.legend()
save(fig, "instrument_broadening.pdf")

# 9. Ritz term reconstruction
true_terms = np.array([0.0, -9000.0, -16500.0, -22100.0, -26000.0])
lo = np.array([0, 0, 1, 1, 2, 2, 3])
up = np.array([1, 2, 2, 3, 3, 4, 4])
y_true = true_terms[lo] - true_terms[up]
sigma_ritz = np.full(y_true.size, 4.0)
y_meas = y_true + rng.normal(0.0, sigma_ritz)
ritz = reconstruct_ritz_terms(lo, up, y_meas, sigma_ritz, 5, 0)
fig, ax = plt.subplots(figsize=(7.2, 4.4))
indices = np.arange(true_terms.size)
ax.plot(indices, true_terms, "o-", label="true terms")
ax.errorbar(indices, ritz.term_values_m_inv, yerr=np.sqrt(np.diag(ritz.covariance)), fmt="s--", label="reconstructed")
ax.set_xlabel("Term index")
ax.set_ylabel(r"Term value (m$^{-1}$; arbitrary zero)")
ax.set_title("Ritz term-value reconstruction")
ax.grid(True, alpha=0.25)
ax.legend()
save(fig, "ritz_term_reconstruction.pdf")

h_est = -coeff[0] / (1.0 / 4.0) if False else -coeff[0]
# For y=R(1/4-x), slope=-R.
rydberg_fit = -coeff[0]
intercept_fit = coeff[1]

diagnostics = {
    "generated_figure_count": 9,
    "chapter22_regression_test_count": 19,
    "balmer_rydberg_fit_m_inverse": float(rydberg_fit),
    "balmer_fit_intercept_m_inverse": float(intercept_fit),
    "hydrogen_balmer_alpha_nm": float(series_wavelength_m(2, 3, finite_mass_rydberg(M_P)) * 1e9),
    "deuterium_minus_hydrogen_balmer_alpha_pm": float(isotope_shift_wavelength_m(2, 3) * 1e12),
    "balmer_limit_nm": float(series_limit_wavelength_m(2, R_INF) * 1e9),
    "correspondence_ratio_n100": float(ratio[-1]),
    "zeeman_shift_hz_at_1T": float(frequency_shift),
    "ritz_fit_chi_square": float(ritz.chi_square),
}
(OUT / "diagnostics.json").write_text(json.dumps(diagnostics, indent=2) + "\n", encoding="utf-8")
print(json.dumps(diagnostics, indent=2))
