"""Commit 629 companion: spin transport and collective dissipation.

Transparent numerical models for textbook diagnostics.  These are deliberately
small/reference calculations rather than production many-body solvers.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import numpy as np


def spin_diffusion_length(Ds: float, T1: float) -> float:
    if Ds < 0 or T1 <= 0:
        raise ValueError("Ds must be nonnegative and T1 positive")
    return float(np.sqrt(Ds * T1))


def diffusion_packet(x, t: float, Ds: float, T1: float, sigma0: float = 0.5):
    """Normalized Gaussian packet with diffusion broadening and T1 amplitude decay."""
    x = np.asarray(x, dtype=float)
    if t < 0 or Ds < 0 or T1 <= 0 or sigma0 <= 0:
        raise ValueError("unphysical diffusion parameters")
    var = sigma0**2 + 2.0 * Ds * t
    amp = np.exp(-t / T1) * sigma0 / np.sqrt(var)
    return amp * np.exp(-0.5 * x**2 / var)


def diffusion_variance(t: float, Ds: float, sigma0: float = 0.5) -> float:
    return float(sigma0**2 + 2.0 * Ds * t)


def magnon_dispersion(k, J: float = 1.0, S: float = 0.5, a: float = 1.0, gap: float = 0.0, hbar: float = 1.0):
    k = np.asarray(k, dtype=float)
    return (gap + 2.0 * J * S * (1.0 - np.cos(k * a))) / hbar


def magnon_group_velocity(k, J: float = 1.0, S: float = 0.5, a: float = 1.0, hbar: float = 1.0):
    k = np.asarray(k, dtype=float)
    return 2.0 * J * S * a * np.sin(k * a) / hbar


def dipolar_angular_factor(theta):
    theta = np.asarray(theta, dtype=float)
    return 1.0 - 3.0 * np.cos(theta)**2


def magic_angle() -> float:
    return float(np.arccos(1.0 / np.sqrt(3.0)))


def lorentzian(omega, center: float = 0.0, gamma: float = 1.0):
    omega = np.asarray(omega, dtype=float)
    if gamma <= 0:
        raise ValueError("gamma must be positive")
    return gamma / np.pi / ((omega-center)**2 + gamma**2)


def motional_narrowing_rate(delta: float, tau_c: float) -> float:
    """Fast-fluctuation estimate 1/T2 ~ delta^2 tau_c."""
    if tau_c < 0:
        raise ValueError("tau_c must be nonnegative")
    return float(delta**2 * tau_c)


def dicke_lowering_strength(N: int, m: float) -> float:
    """Squared matrix element |<J,m-1|J_-|J,m>|^2 for J=N/2."""
    if N < 1:
        raise ValueError("N must be positive")
    J = N / 2.0
    if m < -J or m > J:
        raise ValueError("m outside Dicke ladder")
    return float((J + m) * (J - m + 1.0))


def superradiant_sech2(t, N: int, gamma: float = 1.0, t_delay: float | None = None):
    """Idealized large-N burst envelope ~ N^2 sech^2[gamma*N(t-td)/2]."""
    t = np.asarray(t, dtype=float)
    if N < 1 or gamma <= 0:
        raise ValueError("N and gamma must be positive")
    if t_delay is None:
        t_delay = np.log(max(N, 2)) / (gamma * N)
    x = 0.5 * gamma * N * (t - t_delay)
    return 0.25 * (N**2) * gamma / np.cosh(x)**2


def independent_emission(t, N: int, gamma: float = 1.0):
    t = np.asarray(t, dtype=float)
    if N < 1 or gamma <= 0:
        raise ValueError("N and gamma must be positive")
    return N * gamma * np.exp(-gamma * t)


def ornstein_uhlenbeck_spectrum(omega, delta: float = 1.0, tau_c: float = 1.0):
    """Two-sided spectrum of exponential correlation delta^2 exp(-|t|/tau_c)."""
    omega = np.asarray(omega, dtype=float)
    if tau_c <= 0:
        raise ValueError("tau_c must be positive")
    return 2.0 * delta**2 * tau_c / (1.0 + (omega * tau_c)**2)


def toggling_filter(omega, total_time: float, pulse_times):
    """Dimensionless |integral y(t) exp(i omega t) dt|^2 for instantaneous pi pulses."""
    omega = np.asarray(omega, dtype=float)
    if total_time <= 0:
        raise ValueError("total_time must be positive")
    pts = [0.0] + sorted(float(p) for p in pulse_times) + [float(total_time)]
    if any(p <= 0 or p >= total_time for p in pts[1:-1]):
        raise ValueError("pulse times must lie inside the sequence")
    y = 1.0
    integral = np.zeros_like(omega, dtype=complex)
    for a, b in zip(pts[:-1], pts[1:]):
        nz = np.abs(omega) > 1e-12
        piece = np.empty_like(omega, dtype=complex)
        piece[nz] = (np.exp(1j*omega[nz]*b) - np.exp(1j*omega[nz]*a)) / (1j*omega[nz])
        piece[~nz] = b-a
        integral += y * piece
        y *= -1.0
    return np.abs(integral)**2


def cpmg_pulse_times(total_time: float, n_pulses: int):
    if n_pulses < 1:
        raise ValueError("n_pulses must be positive")
    return [(j + 0.5) * total_time / n_pulses for j in range(n_pulses)]


def bright_dark_two_spin():
    """Return symmetric bright and antisymmetric dark single-excitation states."""
    bright = np.array([0, 1, 1, 0], dtype=complex) / np.sqrt(2)
    dark = np.array([0, 1, -1, 0], dtype=complex) / np.sqrt(2)
    return bright, dark


def collective_lowering_two_spin():
    sm = np.array([[0, 1], [0, 0]], complex)
    I = np.eye(2, dtype=complex)
    return np.kron(sm, I) + np.kron(I, sm)


def _save(fig, path):
    fig.tight_layout()
    fig.savefig(path)
    import matplotlib.pyplot as plt
    plt.close(fig)


def generate_figures(output: Path):
    import matplotlib.pyplot as plt
    output.mkdir(parents=True, exist_ok=True)

    # Spin packet diffusion
    x = np.linspace(-8, 8, 800)
    fig, ax = plt.subplots(figsize=(8.2, 4.8))
    for t in (0.0, 0.7, 1.8, 3.5):
        ax.plot(x, diffusion_packet(x, t, Ds=0.8, T1=4.0), label=fr"$t={t:g}$")
    ax.set_xlabel("$x$")
    ax.set_ylabel("$s_z(x,t)$")
    ax.set_title("Diffusive spin packet: spreading plus relaxation")
    ax.grid(alpha=0.25); ax.legend()
    _save(fig, output/"spin_packet_diffusion.pdf")

    # Magnon packet - simple spectral superposition
    x = np.linspace(-35, 35, 900)
    k = np.linspace(-np.pi, np.pi, 1400)
    k0, sigk = 0.9, 0.18
    A = np.exp(-0.5*((k-k0)/sigk)**2)
    omega = magnon_dispersion(k, J=1.0, S=0.5)
    fig, ax = plt.subplots(figsize=(8.2, 4.8))
    for t in (0.0, 6.0, 12.0):
        phase = np.exp(1j*(np.outer(x,k) - omega[None,:]*t))
        psi = np.trapezoid(A[None,:]*phase, k, axis=1)
        p = np.abs(psi)**2
        p /= p.max()
        ax.plot(x, p, label=fr"$t={t:g}$")
    ax.set_xlabel("lattice coordinate")
    ax.set_ylabel("normalized magnon packet")
    ax.set_title("Coherent exchange-mediated magnon transport")
    ax.grid(alpha=0.25); ax.legend()
    _save(fig, output/"magnon_wavepacket_transport.pdf")

    # Dipolar angular factor
    th = np.linspace(0, np.pi, 700)
    fig, ax = plt.subplots(figsize=(8.2, 4.8))
    ax.plot(th*180/np.pi, dipolar_angular_factor(th))
    ma = magic_angle()*180/np.pi
    ax.axhline(0, linewidth=0.8)
    ax.axvline(ma, linestyle="--", linewidth=1.0, label=fr"$\theta_m={ma:.2f}^\circ$")
    ax.axvline(180-ma, linestyle="--", linewidth=1.0)
    ax.set_xlabel(r"$\theta$ (degrees)")
    ax.set_ylabel(r"$1-3\cos^2\theta$")
    ax.set_title("Dipolar angular anisotropy")
    ax.grid(alpha=0.25); ax.legend()
    _save(fig, output/"dipolar_angular_factor.pdf")

    # Exchange narrowing
    w = np.linspace(-8, 8, 1000)
    fig, ax = plt.subplots(figsize=(8.2, 4.8))
    for g, lab in [(2.5, "slow exchange / broad"), (1.0, "intermediate"), (0.35, "fast exchange / narrow")]:
        ax.plot(w, lorentzian(w, gamma=g), label=lab)
    ax.set_xlabel("frequency offset")
    ax.set_ylabel("normalized line shape")
    ax.set_title("Motional/exchange narrowing")
    ax.grid(alpha=0.25); ax.legend()
    _save(fig, output/"exchange_narrowing_lines.pdf")

    # Superradiant flash
    t = np.linspace(0, 4, 900)
    fig, ax = plt.subplots(figsize=(8.2, 4.8))
    N = 12
    ind = independent_emission(t, N=N, gamma=1.0)
    sup = superradiant_sech2(t, N=N, gamma=1.0)
    ax.plot(t, ind, label="independent emission")
    ax.plot(t, sup, label="collective superradiant burst")
    ax.set_xlabel("time")
    ax.set_ylabel("emission intensity (arb. units)")
    ax.set_title("Independent decay versus the superradiant flash")
    ax.grid(alpha=0.25); ax.legend()
    _save(fig, output/"superradiant_flash.pdf")

    # Noise spectral-density channels
    w = np.linspace(-8, 8, 1200)
    fig, ax = plt.subplots(figsize=(8.2, 4.8))
    Sslow = ornstein_uhlenbeck_spectrum(w, delta=1.0, tau_c=1.2)
    Sfast = ornstein_uhlenbeck_spectrum(w, delta=0.7, tau_c=0.18)
    ax.plot(w, Sslow, label="slow longitudinal-like noise")
    ax.plot(w, Sfast, label="broad transverse-like noise")
    w0 = 3.0
    ax.axvline(0.0, linestyle="--", linewidth=1.0, label=r"$\omega=0$: dephasing")
    ax.axvline(w0, linestyle=":", linewidth=1.2, label=r"$\omega_0$: relaxation")
    ax.set_xlabel(r"$\omega$")
    ax.set_ylabel(r"$S(\omega)$")
    ax.set_title("Which parts of the bath spectrum matter?")
    ax.grid(alpha=0.25); ax.legend()
    _save(fig, output/"noise_spectral_density_channels.pdf")

    # Filter functions
    w = np.linspace(0, 35, 1200)
    T = 1.0
    fig, ax = plt.subplots(figsize=(8.2, 4.8))
    F_ramsey = toggling_filter(w, T, [])
    F_echo = toggling_filter(w, T, [T/2])
    F_cpmg = toggling_filter(w, T, cpmg_pulse_times(T, 6))
    for F, lab in [(F_ramsey, "Ramsey"), (F_echo, "Hahn echo"), (F_cpmg, "CPMG, 6 pulses")]:
        mx = max(float(F.max()), 1e-15)
        ax.plot(w, F/mx, label=lab)
    ax.set_xlabel(r"$\omega T$")
    ax.set_ylabel("normalized filter weight")
    ax.set_title("Control sequences reshape environmental-noise sensitivity")
    ax.grid(alpha=0.25); ax.legend()
    _save(fig, output/"filter_functions_ramsey_echo_cpmg.pdf")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--generate-figures", action="store_true")
    p.add_argument("--output", type=Path, default=Path("generated/ch57/computational"))
    a = p.parse_args()
    if a.generate_figures:
        generate_figures(a.output)

if __name__ == "__main__":
    main()
