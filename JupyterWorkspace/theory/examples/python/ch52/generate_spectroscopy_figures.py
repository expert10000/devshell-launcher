"""Generate Commit 578 atomic-spectroscopy figures and diagnostics."""
from __future__ import annotations

import json
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt

from atomic_spectroscopy import (
    ci_two_configuration,
    fit_ls_spin_orbit,
    hyperfine_multiplet,
    ls_term_energies,
    normal_mass_isotope_shift,
)

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "generated" / "ch52" / "computational"
OUT.mkdir(parents=True, exist_ok=True)


def save_ci_avoided_crossing():
    x = np.linspace(-2.0, 2.0, 401)
    coupling = 0.22
    energies = []
    weights = []
    for d in x:
        vals, vecs = ci_two_configuration(0.5 * d, -0.5 * d, coupling)
        energies.append(vals)
        weights.append(np.abs(vecs[0, :]) ** 2)
    energies = np.asarray(energies)
    weights = np.asarray(weights)

    fig, ax = plt.subplots(figsize=(6.4, 4.1))
    ax.plot(x, energies[:, 0], label=r"$E_-$")
    ax.plot(x, energies[:, 1], label=r"$E_+$")
    ax.plot(x, 0.5 * x, linestyle="--", linewidth=0.9, label="uncoupled")
    ax.plot(x, -0.5 * x, linestyle="--", linewidth=0.9)
    ax.set_xlabel(r"configuration detuning $\Delta$")
    ax.set_ylabel("energy (model units)")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(OUT / "ci_avoided_crossing.pdf")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.4, 4.1))
    ax.plot(x, weights[:, 0], label=r"$|c_1|^2$ in lower state")
    ax.plot(x, 1.0 - weights[:, 0], label=r"$|c_2|^2$ in lower state")
    ax.set_xlabel(r"configuration detuning $\Delta$")
    ax.set_ylabel("configuration weight")
    ax.set_ylim(-0.02, 1.02)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(OUT / "ci_configuration_weights.pdf")
    plt.close(fig)

    return {"coupling": coupling, "minimum_gap": 2.0 * coupling}


def save_ls_multiplet():
    A = 12.0
    centroid = 1000.0
    js, es = ls_term_energies(A, L=1, S=1, centroid=centroid)
    fig, ax = plt.subplots(figsize=(6.4, 4.1))
    ax.scatter(js, es)
    ax.plot(js, es)
    for j, e in zip(js, es):
        ax.annotate(fr"$J={j:g}$", (j, e), xytext=(0, 7), textcoords="offset points", ha="center")
    ax.set_xlabel(r"$J$")
    ax.set_ylabel(r"term value (model cm$^{-1}$)")
    ax.set_xticks(js)
    fig.tight_layout()
    fig.savefig(OUT / "ls_lande_interval_multiplet.pdf")
    plt.close(fig)

    fit = fit_ls_spin_orbit(js, es, L=1, S=1)
    return {"A": A, "centroid": centroid, "Js": js.tolist(), "energies": es.tolist(), "fit_rms": fit["rms"]}


def save_hyperfine_multiplet():
    fs, es = hyperfine_multiplet(A=80.0, B=18.0, I=1.5, J=1.5)
    fig, ax = plt.subplots(figsize=(6.4, 4.1))
    for f, e in zip(fs, es):
        ax.hlines(e, f - 0.28, f + 0.28)
        ax.text(f + 0.34, e, fr"$F={f:g}$", va="center", fontsize=9)
    ax.set_xlabel(r"hyperfine quantum number $F$")
    ax.set_ylabel("energy (model MHz)")
    ax.set_xticks(fs)
    fig.tight_layout()
    fig.savefig(OUT / "hyperfine_multiplet.pdf")
    plt.close(fig)
    return {"I": 1.5, "J": 1.5, "A": 80.0, "B": 18.0, "Fs": fs.tolist(), "energies": es.tolist()}


def save_normal_mass_shift():
    masses = np.linspace(1.0, 20.0, 200)
    nu = 5.0e14
    shifts = np.array([normal_mass_isotope_shift(nu, 1.0, m) for m in masses]) / 1e9
    fig, ax = plt.subplots(figsize=(6.4, 4.1))
    ax.plot(masses, shifts)
    ax.set_xlabel("target nuclear mass (u, model)")
    ax.set_ylabel("normal mass shift from M=1 (GHz)")
    fig.tight_layout()
    fig.savefig(OUT / "normal_mass_isotope_shift.pdf")
    plt.close(fig)
    return {"reference_frequency_hz": nu, "shift_to_mass2_GHz": float(normal_mass_isotope_shift(nu, 1.0, 2.0) / 1e9)}


def main():
    diagnostics = {
        "commit": 578,
        "scope": "configuration interaction, angular-momentum coupling, hyperfine and isotope spectroscopy",
        "ci": save_ci_avoided_crossing(),
        "ls_multiplet": save_ls_multiplet(),
        "hyperfine": save_hyperfine_multiplet(),
        "normal_mass_shift": save_normal_mass_shift(),
        "figures": [
            "ci_avoided_crossing.pdf",
            "ci_configuration_weights.pdf",
            "ls_lande_interval_multiplet.pdf",
            "hyperfine_multiplet.pdf",
            "normal_mass_isotope_shift.pdf",
        ],
    }
    (OUT / "spectroscopy_diagnostics.json").write_text(json.dumps(diagnostics, indent=2) + "\n")
    print(json.dumps(diagnostics, indent=2))


if __name__ == "__main__":
    main()
