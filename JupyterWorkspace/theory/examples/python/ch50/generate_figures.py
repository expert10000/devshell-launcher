"""Generate Chapter 50 computational comparison figures and diagnostics."""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from hamiltonian_model_comparison import (
    anharmonic_convergence,
    anharmonic_spectrum,
    effective_error_sweep,
    flux_ring_energies,
    flux_ring_ground_state_current,
    flux_ring_ground_state_energy,
    two_level_energies,
    two_level_ground_character,
)

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "generated" / "ch50" / "computational"
OUT.mkdir(parents=True, exist_ok=True)


def save(name: str) -> None:
    plt.tight_layout()
    plt.savefig(OUT / name, bbox_inches="tight")
    plt.close()


def avoided_crossing_spectral_flow() -> None:
    detuning = np.linspace(-4.0, 4.0, 401)
    levels = two_level_energies(detuning, coupling=1.0)
    plt.figure(figsize=(6.2, 4.0))
    plt.plot(detuning, levels[:, 0], label=r"$E_-$")
    plt.plot(detuning, levels[:, 1], label=r"$E_+$")
    plt.axvline(0.0, linewidth=0.8, linestyle="--")
    plt.xlabel(r"detuning $\delta/g$")
    plt.ylabel(r"energy $E/g$")
    plt.title("Two-level avoided crossing")
    plt.legend()
    save("avoided_crossing_spectral_flow.pdf")


def avoided_crossing_character() -> None:
    detuning = np.linspace(-5.0, 5.0, 401)
    character = two_level_ground_character(detuning, coupling=1.0)
    plt.figure(figsize=(6.2, 4.0))
    plt.plot(detuning, character)
    plt.axhline(0.0, linewidth=0.8)
    plt.axvline(0.0, linewidth=0.8, linestyle="--")
    plt.xlabel(r"detuning $\delta/g$")
    plt.ylabel(r"ground-state $\langle\sigma_z\rangle$")
    plt.title("Eigenvector flow through the avoided crossing")
    save("avoided_crossing_character.pdf")


def anharmonic_convergence_plot() -> None:
    dims, errors = anharmonic_convergence([6, 8, 10, 12, 16, 20, 24, 32], 0.1, levels=4)
    plt.figure(figsize=(6.2, 4.0))
    plt.semilogy(dims, errors, marker="o")
    plt.xlabel("oscillator-basis dimension N")
    plt.ylabel("max error in first four levels")
    plt.title(r"Basis-truncation convergence for $\lambda=0.1$")
    save("anharmonic_oscillator_convergence.pdf")


def anharmonic_parameter_sweep() -> None:
    strengths = np.linspace(0.0, 0.25, 126)
    spectra = np.array([anharmonic_spectrum(40, lam, 4) for lam in strengths])
    plt.figure(figsize=(6.2, 4.0))
    for index in range(4):
        plt.plot(strengths, spectra[:, index], label=fr"$E_{index}$")
    plt.xlabel(r"quartic strength $\lambda$")
    plt.ylabel(r"energy $E/(\hbar\omega)$")
    plt.title("Anharmonic oscillator parameter sweep")
    plt.legend(ncol=2)
    save("anharmonic_oscillator_parameter_sweep.pdf")


def ring_spectral_flow() -> None:
    phi = np.linspace(-0.5, 1.5, 501)
    n = np.arange(-2, 4)
    energies = flux_ring_energies(phi, n)
    ground = flux_ring_ground_state_energy(phi)
    plt.figure(figsize=(6.2, 4.0))
    for j, nj in enumerate(n):
        plt.plot(phi, energies[:, j], linewidth=1.0, label=fr"$n={nj}$")
    plt.plot(phi, ground, linewidth=2.2, label="ground envelope")
    plt.xlabel(r"reduced flux $\phi=\Phi/\Phi_0$")
    plt.ylabel(r"energy $E/E_0$")
    plt.ylim(0.0, 3.0)
    plt.title("Flux-threaded ring spectral flow")
    plt.legend(ncol=3, fontsize=8)
    save("flux_ring_spectral_flow.pdf")


def ring_persistent_current() -> None:
    phi = np.linspace(-0.49, 1.49, 600)
    current = flux_ring_ground_state_current(phi)
    plt.figure(figsize=(6.2, 4.0))
    plt.plot(phi, current)
    plt.axhline(0.0, linewidth=0.8)
    plt.xlabel(r"reduced flux $\phi=\Phi/\Phi_0$")
    plt.ylabel(r"dimensionless current $-\partial(E/E_0)/\partial\phi$")
    plt.title("Ground-state persistent-current response")
    save("flux_ring_persistent_current.pdf")


def effective_model_error_plot() -> tuple[np.ndarray, np.ndarray, float]:
    gaps, errors = effective_error_sweep(np.geomspace(3.0, 80.0, 80))
    slope = float(np.polyfit(np.log(gaps[-30:]), np.log(errors[-30:]), 1)[0])
    plt.figure(figsize=(6.2, 4.0))
    plt.loglog(gaps, errors, marker="o", markevery=8, label="exact vs effective")
    reference = errors[-1] * (gaps[-1] / gaps) ** 2
    plt.loglog(gaps, reference, linestyle="--", label=r"$\propto \Delta^{-2}$")
    plt.xlabel(r"eliminated-state gap $\Delta$")
    plt.ylabel("maximum low-energy eigenvalue error")
    plt.title("Controlled improvement of a down-folded Hamiltonian")
    plt.legend()
    save("effective_hamiltonian_error.pdf")
    return gaps, errors, slope


def main() -> None:
    avoided_crossing_spectral_flow()
    avoided_crossing_character()
    anharmonic_convergence_plot()
    anharmonic_parameter_sweep()
    ring_spectral_flow()
    ring_persistent_current()
    gaps, errors, slope = effective_model_error_plot()

    e_quartic = anharmonic_spectrum(40, 0.1, 4)
    diagnostics = {
        "companion": "Chapter 50 quantitative Hamiltonian model comparison",
        "two_level": {
            "coupling": 1.0,
            "minimum_gap": float(two_level_energies(0.0, 1.0)[1] - two_level_energies(0.0, 1.0)[0]),
            "character_at_detuning_plus_5": float(two_level_ground_character(5.0, 1.0)),
        },
        "anharmonic_oscillator": {
            "quartic_strength": 0.1,
            "basis_dimension": 40,
            "first_four_energies_hbar_omega": [float(x) for x in e_quartic],
        },
        "flux_ring": {
            "periodicity_check_max_error": float(
                np.max(
                    np.abs(
                        flux_ring_ground_state_energy(np.linspace(-0.4, 0.4, 41))
                        - flux_ring_ground_state_energy(np.linspace(0.6, 1.4, 41))
                    )
                )
            ),
        },
        "effective_model": {
            "error_at_gap_20": float(np.interp(20.0, gaps, errors)),
            "large_gap_loglog_slope": slope,
        },
        "generated_figures": 7,
    }
    (OUT / "diagnostics.json").write_text(json.dumps(diagnostics, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
