"""Generate Commit 579 radiative/field figures and diagnostics."""
from __future__ import annotations

import json
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt

from atomic_radiative import (
    C,
    E_CHARGE,
    absorption_oscillator_strength,
    branching_fractions,
    e1_rate_from_oscillator_strength,
    e1_spontaneous_rate,
    hyperfine_zeeman_map_hz,
    natural_linewidth_hz,
    radiative_lifetime_s,
    trk_captured_fraction,
    two_level_field_map,
)

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "generated" / "ch52" / "computational"
OUT.mkdir(parents=True, exist_ok=True)


def save_rate_scaling():
    wavelengths_nm = np.linspace(300.0, 1200.0, 400)
    omega = 2.0 * np.pi * C / (wavelengths_nm * 1e-9)
    d = E_CHARGE * 5.29177210903e-11
    rates = np.array([e1_spontaneous_rate(w, d, J_upper=1) for w in omega])
    fig, ax = plt.subplots(figsize=(6.4, 4.1))
    ax.loglog(wavelengths_nm, rates)
    ax.set_xlabel("wavelength (nm)")
    ax.set_ylabel(r"$A_{ul}$ (s$^{-1}$)")
    ax.set_title("Fixed line strength: cubic frequency scaling")
    fig.tight_layout()
    fig.savefig(OUT / "e1_rate_wavelength_scaling.pdf")
    plt.close(fig)
    ratio = float(rates[0] / rates[-1])
    return {"rate_ratio_300_to_1200_nm": ratio}


def save_oscillator_strength_budget():
    strengths = np.array([0.55, 0.25, 0.12, 0.05, 0.03])
    captured, deficit = trk_captured_fraction(strengths, electron_count=1)
    labels = ["1", "2", "3", "4", "5"]
    fig, ax = plt.subplots(figsize=(6.4, 4.1))
    ax.bar(labels, strengths)
    ax.set_xlabel("model transition")
    ax.set_ylabel("oscillator strength")
    ax.set_title("Illustrative one-electron oscillator-strength budget")
    fig.tight_layout()
    fig.savefig(OUT / "oscillator_strength_budget.pdf")
    plt.close(fig)
    return {"sum": float(np.sum(strengths)), "captured_fraction": captured, "deficit": deficit}


def save_branching_network():
    rates = np.array([7.0e7, 2.0e7, 1.0e7])
    branches = branching_fractions(rates)
    tau = radiative_lifetime_s(rates)
    linewidth = natural_linewidth_hz(np.sum(rates))
    fig, ax = plt.subplots(figsize=(6.4, 4.1))
    ax.bar(["channel 1", "channel 2", "channel 3"], branches)
    ax.set_ylabel("branching fraction")
    ax.set_ylim(0.0, 0.8)
    ax.set_title(fr"$\tau={tau*1e9:.1f}$ ns, $\Delta\nu_{{nat}}={linewidth/1e6:.1f}$ MHz")
    fig.tight_layout()
    fig.savefig(OUT / "radiative_branching_network.pdf")
    plt.close(fig)
    return {"rates_s-1": rates.tolist(), "branching": branches.tolist(), "lifetime_s": tau, "linewidth_hz": linewidth}


def save_hyperfine_zeeman_map():
    fields = np.linspace(0.0, 0.08, 241)
    energies_hz = hyperfine_zeeman_map_hz(I=1.5, J=0.5, A_hfs_hz=250e6, fields_tesla=fields, g_J=2.0023)
    energies_ghz = energies_hz / 1e9
    fig, ax = plt.subplots(figsize=(6.4, 4.1))
    for i in range(energies_ghz.shape[1]):
        ax.plot(fields, energies_ghz[:, i], linewidth=1.0)
    ax.set_xlabel("magnetic field (T)")
    ax.set_ylabel(r"energy / $h$ (GHz)")
    ax.set_title(r"Hyperfine--Zeeman crossover: $I=3/2$, $J=1/2$")
    fig.tight_layout()
    fig.savefig(OUT / "hyperfine_zeeman_level_map.pdf")
    plt.close(fig)
    return {"field_max_T": float(fields[-1]), "levels": int(energies_ghz.shape[1]), "zero_field_trace_hz": float(np.sum(energies_hz[0]))}


def save_stark_avoided_crossing():
    field = np.linspace(-1.0, 1.0, 401)
    energies, weights = two_level_field_map(field, e1_0=0.0, e2_0=0.0, slope1=1.0, slope2=-1.0, coupling=0.08)
    fig, ax = plt.subplots(figsize=(6.4, 4.1))
    ax.plot(field, energies[:, 0], label=r"$E_-$")
    ax.plot(field, energies[:, 1], label=r"$E_+$")
    ax.plot(field, field, linestyle="--", linewidth=0.8, label="uncoupled")
    ax.plot(field, -field, linestyle="--", linewidth=0.8)
    ax.set_xlabel("electric-field control (model units)")
    ax.set_ylabel("energy (model units)")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(OUT / "stark_avoided_crossing_map.pdf")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.4, 4.1))
    ax.plot(field, weights[:, 0], label=r"$|1|^2$ in lower state")
    ax.plot(field, 1.0 - weights[:, 0], label=r"$|2|^2$ in lower state")
    ax.set_xlabel("electric-field control (model units)")
    ax.set_ylabel("basis weight")
    ax.set_ylim(-0.02, 1.02)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(OUT / "stark_state_character_exchange.pdf")
    plt.close(fig)
    gap = energies[:, 1] - energies[:, 0]
    return {"coupling": 0.08, "minimum_gap": float(np.min(gap)), "center_weight": float(weights[len(field)//2, 0])}


def main():
    # A/f consistency benchmark using a fixed reduced matrix element.
    omega = 2.4e15
    d = E_CHARGE * 4.2e-11
    f = absorption_oscillator_strength(omega, d, J_lower=0)
    a_direct = e1_spontaneous_rate(omega, d, J_upper=1)
    a_from_f = e1_rate_from_oscillator_strength(omega, f, J_lower=0, J_upper=1)

    diagnostics = {
        "commit": 579,
        "scope": "radiative rates, oscillator strengths, lifetimes, and external-field level maps",
        "e1_scaling": save_rate_scaling(),
        "oscillator_budget": save_oscillator_strength_budget(),
        "branching": save_branching_network(),
        "hyperfine_zeeman": save_hyperfine_zeeman_map(),
        "stark_map": save_stark_avoided_crossing(),
        "a_f_consistency": {
            "f": f,
            "A_direct": a_direct,
            "A_from_f": a_from_f,
            "relative_error": abs(a_direct - a_from_f) / a_direct,
        },
        "figures": [
            "e1_rate_wavelength_scaling.pdf",
            "oscillator_strength_budget.pdf",
            "radiative_branching_network.pdf",
            "hyperfine_zeeman_level_map.pdf",
            "stark_avoided_crossing_map.pdf",
            "stark_state_character_exchange.pdf",
        ],
    }
    (OUT / "radiative_diagnostics.json").write_text(json.dumps(diagnostics, indent=2) + "\n")
    print(json.dumps(diagnostics, indent=2))


if __name__ == "__main__":
    main()
