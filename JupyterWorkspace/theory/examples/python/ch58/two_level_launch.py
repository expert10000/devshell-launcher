"""Commit 631 Chapter 58 launch companion."""
from __future__ import annotations
import argparse
from pathlib import Path
import numpy as np


def avoided_energies(epsilon, g):
    epsilon = np.asarray(epsilon, dtype=float)
    gap = np.sqrt(epsilon**2 + 4.0*g**2)
    return -0.5*gap, 0.5*gap


def avoided_minimum_gap(g):
    return 2.0*abs(float(g))


def rabi_probability(t, omega_rabi, detuning=0.0):
    t = np.asarray(t, dtype=float)
    eff = np.sqrt(omega_rabi**2 + detuning**2)
    if eff == 0:
        return np.zeros_like(t)
    return (omega_rabi**2/eff**2) * np.sin(0.5*eff*t)**2


def landau_zener_diabatic_probability(g, sweep_rate, hbar=1.0):
    if sweep_rate <= 0 or hbar <= 0:
        raise ValueError("sweep_rate and hbar must be positive")
    return float(np.exp(-2.0*np.pi*g**2/(hbar*sweep_rate)))


def pauli_decomposition(H):
    H = np.asarray(H, dtype=complex)
    if H.shape != (2,2):
        raise ValueError("H must be 2x2")
    I = np.eye(2, dtype=complex)
    sx = np.array([[0,1],[1,0]], complex)
    sy = np.array([[0,-1j],[1j,0]], complex)
    sz = np.array([[1,0],[0,-1]], complex)
    h0 = 0.5*np.trace(H)
    comps = np.array([
        np.trace(H@sx).real,
        np.trace(H@sy).real,
        np.trace(H@sz).real,
    ]) / 2.0
    return h0, comps


def generate_figures(output: Path):
    import matplotlib.pyplot as plt
    output.mkdir(parents=True, exist_ok=True)

    eps = np.linspace(-6, 6, 700)
    fig, ax = plt.subplots(figsize=(8.0, 4.8))
    ax.plot(eps, 0.5*eps, linestyle="--", label="diabatic level")
    ax.plot(eps, -0.5*eps, linestyle="--")
    em, ep = avoided_energies(eps, g=1.0)
    ax.plot(eps, ep, label="adiabatic upper level")
    ax.plot(eps, em, label="adiabatic lower level")
    ax.set_xlabel(r"detuning $\epsilon$")
    ax.set_ylabel("energy")
    ax.set_title("Two-level avoided crossing")
    ax.grid(alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(output/"avoided_crossing.pdf")
    plt.close(fig)

    t = np.linspace(0, 8*np.pi, 900)
    fig, ax = plt.subplots(figsize=(8.0, 4.8))
    ax.plot(t, rabi_probability(t, 1.0, 0.0), label="on resonance")
    ax.plot(t, rabi_probability(t, 1.0, 0.7), label=r"detuned: $\Delta=0.7\Omega_R$")
    ax.plot(t, rabi_probability(t, 1.0, 1.5), label=r"detuned: $\Delta=1.5\Omega_R$")
    ax.set_xlabel("time")
    ax.set_ylabel(r"$P_e(t)$")
    ax.set_ylim(-0.03, 1.03)
    ax.set_title("Ideal driven two-level Rabi oscillations")
    ax.grid(alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(output/"rabi_oscillations.pdf")
    plt.close(fig)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--generate-figures", action="store_true")
    p.add_argument("--output", type=Path, default=Path("generated/ch58/computational"))
    a = p.parse_args()
    if a.generate_figures:
        generate_figures(a.output)


if __name__ == "__main__":
    main()
