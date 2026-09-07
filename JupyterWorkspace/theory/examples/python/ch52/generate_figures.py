"""Generate Commit 577 Chapter 52 computational figures and diagnostics."""
from __future__ import annotations

import json
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt

from atomic_many_electron import (
    HELIUM_HF_REFERENCE,
    HELIUM_NONREL_REFERENCE,
    correlation_energy,
    helium_approximation_ladder,
    helium_optimal_zeta,
    helium_restricted_scf,
    helium_variational_energy,
    hydrogenic_1s_radial_probability,
)

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "generated" / "ch52" / "computational"
OUT.mkdir(parents=True, exist_ok=True)


def save_variational_curve():
    z = np.linspace(1.0, 2.35, 320)
    e = helium_variational_energy(z)
    zstar = helium_optimal_zeta()
    fig, ax = plt.subplots(figsize=(6.4, 4.1))
    ax.plot(z, e, label=r"$E(\zeta)$")
    ax.scatter([zstar], [helium_variational_energy(zstar)], label=r"minimum $\zeta_*=27/16$")
    ax.scatter([2.0], [helium_variational_energy(2.0)], label=r"bare $Z=2$")
    ax.set_xlabel(r"orbital exponent $\zeta$")
    ax.set_ylabel(r"energy $E/E_h$")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(OUT / "helium_variational_curve.pdf")
    plt.close(fig)


def save_radial_relaxation():
    r = np.linspace(0.0, 6.0, 500)
    fig, ax = plt.subplots(figsize=(6.4, 4.1))
    ax.plot(r, hydrogenic_1s_radial_probability(r, 2.0), label=r"bare $\zeta=2$")
    ax.plot(r, hydrogenic_1s_radial_probability(r, helium_optimal_zeta()), label=r"screened $\zeta=27/16$")
    ax.set_xlabel(r"radius $r/a_0$")
    ax.set_ylabel(r"radial probability $P(r)$")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(OUT / "helium_radial_relaxation.pdf")
    plt.close(fig)


def save_scf_and_ladder():
    res = helium_restricted_scf(n_grid=2400, r_max=24.0, tolerance=2e-10)
    iterations = np.arange(1, res.energy_history.size + 1)
    fig, ax = plt.subplots(figsize=(6.4, 4.1))
    ax.plot(iterations, res.energy_history, marker="o", markersize=2.5, label="radial SCF")
    ax.axhline(HELIUM_HF_REFERENCE, linestyle="--", label="HF limit reference")
    ax.set_xlabel("SCF iteration")
    ax.set_ylabel(r"total energy $E/E_h$")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(OUT / "helium_scf_convergence.pdf")
    plt.close(fig)

    ladder = helium_approximation_ladder()
    names = ["fixed 1s", "optimized exp.", "HF limit", "correlated"]
    values = [
        ladder["fixed_1s_full_expectation"],
        ladder["optimized_exponential"],
        ladder["hartree_fock_limit"],
        ladder["correlated_nonrelativistic"],
    ]
    x = np.arange(len(names))
    fig, ax = plt.subplots(figsize=(6.4, 4.1))
    ax.plot(x, values, marker="o")
    ax.set_xticks(x, names)
    ax.set_ylabel(r"energy $E/E_h$")
    for xx, yy in zip(x, values):
        ax.annotate(f"{yy:.4f}", (xx, yy), xytext=(0, 7), textcoords="offset points", ha="center", fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "helium_approximation_ladder.pdf")
    plt.close(fig)
    return res


def main():
    save_variational_curve()
    save_radial_relaxation()
    res = save_scf_and_ladder()
    diagnostics = {
        "commit": 577,
        "units": "Hartree atomic units",
        "helium": {
            "optimal_single_exponential_zeta": helium_optimal_zeta(),
            "single_exponential_energy": float(helium_variational_energy(helium_optimal_zeta())),
            "scf_energy": res.energy,
            "scf_orbital_energy": res.orbital_energy,
            "scf_direct_energy": res.direct_energy,
            "scf_iterations": res.iterations,
            "scf_converged": res.converged,
            "hf_reference": HELIUM_HF_REFERENCE,
            "nonrelativistic_correlated_reference": HELIUM_NONREL_REFERENCE,
            "correlation_energy_reference": correlation_energy(),
        },
        "figures": [
            "helium_variational_curve.pdf",
            "helium_radial_relaxation.pdf",
            "helium_scf_convergence.pdf",
            "helium_approximation_ladder.pdf",
        ],
    }
    (OUT / "diagnostics.json").write_text(json.dumps(diagnostics, indent=2) + "\n")
    print(json.dumps(diagnostics, indent=2))


if __name__ == "__main__":
    main()
