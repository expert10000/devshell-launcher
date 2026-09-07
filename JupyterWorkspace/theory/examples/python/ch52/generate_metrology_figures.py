"""Generate Commit 580 quantum-defect/polarizability/metrology figures and diagnostics."""
from __future__ import annotations

import json
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt

from atomic_metrology import (
    ac_stark_shift_hz,
    bbr_clock_shift_hz,
    blackbody_mean_square_field_v2_m2,
    core_polarization_potential_au,
    differential_polarizability_dynamic_au,
    find_magic_photon_energy_au,
    fractional_frequency_shift,
    quantum_defect_binding_hartree,
    ritz_quantum_defect,
    scalar_polarizability_dynamic_au,
    scalar_polarizability_static_au,
    uncertainty_quadrature,
)

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "generated" / "ch52" / "computational"
OUT.mkdir(parents=True, exist_ok=True)

LOWER = ([0.080, 0.135, 0.210], [2.20, 1.10, 0.55], 0.0)
UPPER = ([0.065, 0.160, 0.235], [1.45, 2.00, 0.45], 0.0)
MAGIC_BRACKET = (0.050, 0.055)


def save_quantum_defect_series():
    n = np.arange(5, 31, dtype=float)
    e_h = np.array([quantum_defect_binding_hartree(x, 0.0) for x in n])
    e_s = np.array([quantum_defect_binding_hartree(x, 1.30) for x in n])
    e_d = np.array([quantum_defect_binding_hartree(x, 0.05) for x in n])
    fig, ax = plt.subplots(figsize=(6.4, 4.1))
    ax.plot(n, -e_h, label=r"hydrogenic $\delta=0$")
    ax.plot(n, -e_s, label=r"penetrating series $\delta=1.30$")
    ax.plot(n, -e_d, label=r"weak-defect series $\delta=0.05$")
    ax.set_yscale("log")
    ax.set_xlabel("principal quantum number n")
    ax.set_ylabel("binding energy |E| (Hartree)")
    ax.set_title("Quantum defect reorganizes a Rydberg series")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(OUT / "quantum_defect_rydberg_series.pdf")
    plt.close(fig)
    return {
        "n10_hydrogenic_hartree": float(quantum_defect_binding_hartree(10, 0.0)),
        "n10_delta1_hartree": float(quantum_defect_binding_hartree(10, 1.0)),
        "ritz_delta_n30": float(ritz_quantum_defect(30, 1.30, 0.18, -0.03)),
    }


def save_core_polarization():
    r = np.linspace(0.08, 12.0, 600)
    alpha_c = 5.0
    rho = 1.5
    regularized = core_polarization_potential_au(r, alpha_c, rho)
    tail = -0.5 * alpha_c / r**4
    fig, ax = plt.subplots(figsize=(6.4, 4.1))
    ax.plot(r, regularized, label="regularized model")
    ax.plot(r, tail, linestyle="--", label=r"$-\alpha_c/(2r^4)$ tail")
    ax.set_xlim(0.0, 8.0)
    ax.set_ylim(-0.7, 0.05)
    ax.set_xlabel(r"radius ($a_0$)")
    ax.set_ylabel("polarization potential (Hartree)")
    ax.set_title("Core polarization: correct tail, finite core")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(OUT / "core_polarization_regularization.pdf")
    plt.close(fig)
    return {
        "alpha_core_au": alpha_c,
        "cutoff_radius_au": rho,
        "long_range_relative_error_r30": float(abs(core_polarization_potential_au(30.0, alpha_c, rho) / (-0.5 * alpha_c / 30.0**4) - 1.0)),
    }


def save_polarizability_magic():
    magic = find_magic_photon_energy_au(MAGIC_BRACKET, LOWER, UPPER)
    # Stay below the first model resonance at 0.065 Hartree.
    w = np.linspace(0.0, 0.0615, 450)
    a_l = np.array([scalar_polarizability_dynamic_au(x, *LOWER[:2], J=LOWER[2]) for x in w])
    a_u = np.array([scalar_polarizability_dynamic_au(x, *UPPER[:2], J=UPPER[2]) for x in w])
    fig, ax = plt.subplots(figsize=(6.4, 4.1))
    ax.plot(w, a_l, label="lower clock state")
    ax.plot(w, a_u, label="upper clock state")
    ax.axvline(magic, linestyle="--", linewidth=1.0, label="magic condition")
    ax.set_xlabel(r"photon energy $\hbar\omega$ (Hartree)")
    ax.set_ylabel(r"scalar $\alpha_0(\omega)$ (a.u.)")
    ax.set_title("Dynamic polarizability crossing")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(OUT / "dynamic_polarizability_magic_crossing.pdf")
    plt.close(fig)

    detuning = np.linspace(-0.006, 0.006, 401)
    w2 = magic + detuning
    da = np.array([differential_polarizability_dynamic_au(x, LOWER, UPPER) for x in w2])
    e0_v_m = 1.0e5
    shifts = np.array([ac_stark_shift_hz(x, e0_v_m) for x in da])
    fig, ax = plt.subplots(figsize=(6.4, 4.1))
    ax.plot(detuning, shifts)
    ax.axhline(0.0, linewidth=0.8)
    ax.axvline(0.0, linestyle="--", linewidth=0.8)
    ax.set_xlabel(r"detuning from magic photon energy (Hartree)")
    ax.set_ylabel("differential AC Stark shift (Hz)")
    ax.set_title("Residual clock shift around a magic condition")
    fig.tight_layout()
    fig.savefig(OUT / "magic_detuning_clock_shift.pdf")
    plt.close(fig)

    return {
        "magic_photon_energy_au": float(magic),
        "differential_alpha_at_magic_au": float(differential_polarizability_dynamic_au(magic, LOWER, UPPER)),
        "lower_static_alpha_au": float(scalar_polarizability_static_au(*LOWER[:2], J=LOWER[2])),
        "upper_static_alpha_au": float(scalar_polarizability_static_au(*UPPER[:2], J=UPPER[2])),
        "field_amplitude_v_m_for_shift_map": e0_v_m,
    }


def save_bbr_scaling():
    t = np.linspace(200.0, 500.0, 301)
    delta_alpha = 25.0
    shifts = np.array([bbr_clock_shift_hz(delta_alpha, x) for x in t])
    fig, ax = plt.subplots(figsize=(6.4, 4.1))
    ax.plot(t, shifts)
    ax.set_xlabel("temperature (K)")
    ax.set_ylabel("static-approximation BBR shift (Hz)")
    ax.set_title(r"Blackbody Stark shift: leading $T^4$ scaling")
    fig.tight_layout()
    fig.savefig(OUT / "blackbody_shift_t4_scaling.pdf")
    plt.close(fig)
    e300 = blackbody_mean_square_field_v2_m2(300.0)
    e600 = blackbody_mean_square_field_v2_m2(600.0)
    return {
        "delta_alpha_au": delta_alpha,
        "mean_square_field_300K_v2_m2": float(e300),
        "t4_ratio_600_to_300": float(e600 / e300),
        "shift_300K_hz": float(bbr_clock_shift_hz(delta_alpha, 300.0)),
    }


def save_metrology_budget():
    # Illustrative fractional 1-sigma uncertainties, deliberately not tied to a
    # specific species or published clock evaluation.
    labels = ["BBR", "lattice", "Zeeman", "density", "probe", "dc Stark"]
    u = np.array([2.2, 1.4, 1.0, 0.8, 0.5, 0.4]) * 1e-18
    total = uncertainty_quadrature(u)
    fig, ax = plt.subplots(figsize=(6.4, 4.1))
    ax.bar(labels, u / 1e-18)
    ax.set_ylabel(r"fractional uncertainty ($10^{-18}$)")
    ax.set_title(fr"Illustrative systematic budget; quadrature total = {total/1e-18:.2f}$\times10^{{-18}}$")
    ax.tick_params(axis="x", rotation=25)
    fig.tight_layout()
    fig.savefig(OUT / "illustrative_clock_uncertainty_budget.pdf")
    plt.close(fig)
    return {
        "components_fractional": u.tolist(),
        "quadrature_total_fractional": float(total),
    }


def main():
    qd = save_quantum_defect_series()
    core = save_core_polarization()
    magic = save_polarizability_magic()
    bbr = save_bbr_scaling()
    budget = save_metrology_budget()
    diagnostics = {
        "commit": 580,
        "scope": "quantum defects, core polarization, dynamic polarizability, magic trapping, and precision metrology",
        "quantum_defect": qd,
        "core_polarization": core,
        "magic": magic,
        "blackbody": bbr,
        "uncertainty_budget": budget,
        "fractional_shift_example": fractional_frequency_shift(0.5, 5.0e14),
        "figures": [
            "quantum_defect_rydberg_series.pdf",
            "core_polarization_regularization.pdf",
            "dynamic_polarizability_magic_crossing.pdf",
            "magic_detuning_clock_shift.pdf",
            "blackbody_shift_t4_scaling.pdf",
            "illustrative_clock_uncertainty_budget.pdf",
        ],
    }
    (OUT / "metrology_diagnostics.json").write_text(json.dumps(diagnostics, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(diagnostics, indent=2))


if __name__ == "__main__":
    main()
