"""Open-system spin dynamics for Volume VIII, Chapter 57, Commit 628.

Transparent textbook routines for T1 relaxation, T2/Tphi coherence, Bloch
trajectories, driven steady states, simple Kraus channels, and reproducible
vector figures.  Units are dimensionless unless specified.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import numpy as np


def thermal_excited_population(beta_hbar_omega: float) -> float:
    """Two-level Gibbs excited-state population for energies (0, hbar*omega)."""
    x = float(beta_hbar_omega)
    if x >= 0:
        e = np.exp(-x)
        return float(e / (1.0 + e))
    e = np.exp(x)
    return float(1.0 / (1.0 + e))


def equilibrium_rz(beta_hbar_omega: float) -> float:
    """Ground-minus-excited population imbalance."""
    p1 = thermal_excited_population(beta_hbar_omega)
    return float(1.0 - 2.0 * p1)


def t1_from_rates(gamma_down: float, gamma_up: float) -> float:
    rate = float(gamma_down + gamma_up)
    if rate <= 0:
        raise ValueError("sum of transition rates must be positive")
    return 1.0 / rate


def t2_from_t1_tphi(t1: float, tphi: float = np.inf) -> float:
    if t1 <= 0 or tphi <= 0:
        raise ValueError("times must be positive")
    rate = 1.0 / (2.0 * t1)
    if np.isfinite(tphi):
        rate += 1.0 / tphi
    return 1.0 / rate


def relax_rz(t, rz0: float, rz_eq: float, t1: float):
    t = np.asarray(t, dtype=float)
    return rz_eq + (rz0 - rz_eq) * np.exp(-t / t1)


def coherence_envelope(t, t2: float):
    t = np.asarray(t, dtype=float)
    return np.exp(-t / t2)


def quasistatic_gaussian_envelope(t, sigma_omega: float):
    t = np.asarray(t, dtype=float)
    return np.exp(-0.5 * (sigma_omega * t) ** 2)


def bloch_trajectory(t, r0, omega0: float, t1: float, t2: float, rz_eq: float):
    t = np.asarray(t, dtype=float)
    r0 = np.asarray(r0, dtype=float)
    if r0.shape != (3,):
        raise ValueError("r0 must have three components")
    a = np.exp(-t / t2)
    c = np.cos(omega0 * t)
    s = np.sin(omega0 * t)
    x = a * (r0[0] * c - r0[1] * s)
    y = a * (r0[0] * s + r0[1] * c)
    z = relax_rz(t, r0[2], rz_eq, t1)
    return np.column_stack([x, y, z])


def driven_steady_state(detuning, omega_rabi: float, t1: float, t2: float, rz_eq: float = 1.0):
    d = np.asarray(detuning, dtype=float)
    den = 1.0 + (d * t2) ** 2 + omega_rabi**2 * t1 * t2
    rz = rz_eq * (1.0 + (d * t2) ** 2) / den
    ry = -omega_rabi * t2 * rz / (1.0 + (d * t2) ** 2)
    rx = -d * t2 * ry
    return rx, ry, rz


def amplitude_damping_kraus(p: float):
    p = float(p)
    if not 0.0 <= p <= 1.0:
        raise ValueError("p must be in [0,1]")
    k0 = np.array([[1.0, 0.0], [0.0, np.sqrt(1.0 - p)]], dtype=complex)
    k1 = np.array([[0.0, np.sqrt(p)], [0.0, 0.0]], dtype=complex)
    return k0, k1


def apply_kraus(rho, kraus_ops):
    rho = np.asarray(rho, dtype=complex)
    out = np.zeros_like(rho)
    for k in kraus_ops:
        out += k @ rho @ k.conj().T
    return out


def density_from_bloch(r):
    r = np.asarray(r, dtype=float)
    sx = np.array([[0, 1], [1, 0]], complex)
    sy = np.array([[0, -1j], [1j, 0]], complex)
    sz = np.array([[1, 0], [0, -1]], complex)
    return 0.5 * (np.eye(2) + r[0] * sx + r[1] * sy + r[2] * sz)


def bloch_from_density(rho):
    rho = np.asarray(rho, dtype=complex)
    sx = np.array([[0, 1], [1, 0]], complex)
    sy = np.array([[0, -1j], [1j, 0]], complex)
    sz = np.array([[1, 0], [0, -1]], complex)
    return np.array([
        np.trace(rho @ sx).real,
        np.trace(rho @ sy).real,
        np.trace(rho @ sz).real,
    ])


def _sphere_wireframe(ax):
    u = np.linspace(0, 2 * np.pi, 72)
    v = np.linspace(0, np.pi, 36)
    x = np.outer(np.cos(u), np.sin(v))
    y = np.outer(np.sin(u), np.sin(v))
    z = np.outer(np.ones_like(u), np.cos(v))
    ax.plot_wireframe(x, y, z, rstride=8, cstride=8, linewidth=0.35, alpha=0.25)
    ax.plot(np.cos(u), np.sin(u), 0*u, linestyle="--", linewidth=0.8, alpha=0.55)
    ax.set_xlim(-1.05, 1.05)
    ax.set_ylim(-1.05, 1.05)
    ax.set_zlim(-1.05, 1.05)
    ax.set_box_aspect((1, 1, 1))
    ax.set_xlabel("$r_x$")
    ax.set_ylabel("$r_y$")
    ax.set_zlabel("$r_z$")


def generate_figures(output: Path):
    import matplotlib.pyplot as plt
    output.mkdir(parents=True, exist_ok=True)

    # 1. Combined Bloch trajectory.
    t = np.linspace(0, 8, 700)
    traj = bloch_trajectory(t, [1, 0, 0], omega0=3.8, t1=3.0, t2=1.35, rz_eq=0.72)
    fig = plt.figure(figsize=(8.0, 6.4))
    ax = fig.add_subplot(111, projection="3d")
    _sphere_wireframe(ax)
    ax.plot(traj[:,0], traj[:,1], traj[:,2], linewidth=2.2, label="$T_1$+$T_2$ trajectory")
    ax.scatter([traj[0,0]], [traj[0,1]], [traj[0,2]], s=45, label="initial state")
    ax.scatter([0], [0], [0.72], s=45, label="thermal equilibrium")
    ax.legend(loc="upper left")
    ax.set_title("Relaxation and decoherence in the Bloch ball")
    fig.tight_layout()
    fig.savefig(output/"bloch_open_system_trajectory.pdf")
    plt.close(fig)

    # 2. Population relaxation.
    t = np.linspace(0, 5, 500)
    fig, ax = plt.subplots(figsize=(8.0, 4.8))
    for rz_eq in (1.0, 0.75, 0.4):
        ax.plot(t, relax_rz(t, -1.0, rz_eq, 1.0), label=fr"$r_z^{{eq}}={rz_eq:g}$")
    ax.axvline(1.0, linestyle="--", linewidth=1.0, label="$T_1$")
    ax.set_xlabel("$t/T_1$")
    ax.set_ylabel("$r_z(t)$")
    ax.set_title("Longitudinal population relaxation")
    ax.legend()
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(output/"t1_population_relaxation.pdf")
    plt.close(fig)

    # 3. Coherence channels.
    t = np.linspace(0, 5, 500)
    t1 = 2.0
    tphi = 2.0
    t2 = t2_from_t1_tphi(t1, tphi)
    fig, ax = plt.subplots(figsize=(8.0, 4.8))
    ax.plot(t, coherence_envelope(t, 2*t1), label="relaxation-only coherence")
    ax.plot(t, coherence_envelope(t, tphi), label="pure-dephasing factor")
    ax.plot(t, coherence_envelope(t, t2), label="$T_2$ homogeneous envelope")
    ax.plot(t, coherence_envelope(t, t2)*quasistatic_gaussian_envelope(t, 0.85),
            label="$T_2^*$-type free induction")
    ax.set_xlabel("time")
    ax.set_ylabel("normalized transverse coherence")
    ax.set_ylim(-0.02, 1.03)
    ax.set_title("Coherence loss channels")
    ax.legend()
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(output/"coherence_decay_channels.pdf")
    plt.close(fig)

    # 4. Driven response and saturation.
    d = np.linspace(-6, 6, 700)
    fig, ax = plt.subplots(figsize=(8.0, 4.8))
    for om in (0.2, 0.8, 1.8):
        _, ry, _ = driven_steady_state(d, om, t1=2.5, t2=1.0, rz_eq=1.0)
        ax.plot(d, -ry, label=fr"$\Omega={om:g}$")
    ax.set_xlabel(r"detuning $\Delta T_2$")
    ax.set_ylabel("absorptive quadrature")
    ax.set_title("Dissipative resonance and saturation")
    ax.legend()
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(output/"dissipative_resonance_saturation.pdf")
    plt.close(fig)

    # 5. Ramsey versus echo schematic envelope.
    t = np.linspace(0, 6, 600)
    homogeneous = np.exp(-t/3.0)
    ramsey = homogeneous * np.exp(-0.5*(0.8*t)**2)
    echo = homogeneous
    fig, ax = plt.subplots(figsize=(8.0, 4.8))
    ax.plot(t, ramsey, label="Ramsey/free induction")
    ax.plot(t, echo, label="ideal Hahn-echo envelope")
    ax.axvline(3.0, linestyle="--", linewidth=1.0, label="echo time")
    ax.set_xlabel("time")
    ax.set_ylabel("normalized coherence")
    ax.set_ylim(-0.02, 1.03)
    ax.set_title("Refocusing quasistatic phase dispersion")
    ax.legend()
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(output/"ramsey_echo_refocusing.pdf")
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--generate-figures", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("generated/ch57/computational"))
    args = parser.parse_args()
    if args.generate_figures:
        generate_figures(args.output)


if __name__ == "__main__":
    main()
