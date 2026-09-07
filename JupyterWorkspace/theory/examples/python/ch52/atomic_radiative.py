"""Radiative and external-field diagnostics for Volume VIII, Chapter 52, Commit 579.

The functions use SI units where units are explicit. Angular-momentum matrices are
dimensionless (their eigenvalues are m, not hbar*m), which makes hyperfine and
Zeeman Hamiltonians convenient in frequency units.
"""
from __future__ import annotations

import math
import numpy as np

C = 299_792_458.0
HBAR = 1.054_571_817e-34
H = 6.626_070_15e-34
EPSILON_0 = 8.854_187_8128e-12
E_CHARGE = 1.602_176_634e-19
M_E = 9.109_383_7015e-31
MU_B = 9.274_010_0783e-24
MU_B_OVER_H_HZ_T = MU_B / H


def _half_integer(x: float, name: str) -> float:
    x = float(x)
    if x < 0.0 or abs(2.0 * x - round(2.0 * x)) > 1e-10:
        raise ValueError(f"{name} must be a nonnegative integer or half-integer")
    return x


def _positive(x: float, name: str) -> float:
    x = float(x)
    if not math.isfinite(x) or x <= 0.0:
        raise ValueError(f"{name} must be positive and finite")
    return x


def e1_spontaneous_rate(omega_rad_s: float, reduced_dipole_c_m: float, J_upper: float) -> float:
    """Unpolarized E1 Einstein A coefficient from a reduced dipole matrix element.

    A_ul = omega^3 |<u||D||l>|^2 / [3 pi eps0 hbar c^3 (2 J_u + 1)].
    """
    omega = _positive(omega_rad_s, "omega_rad_s")
    ju = _half_integer(J_upper, "J_upper")
    d = abs(float(reduced_dipole_c_m))
    return float(omega**3 * d**2 / (3.0 * math.pi * EPSILON_0 * HBAR * C**3 * (2.0 * ju + 1.0)))


def absorption_oscillator_strength(
    omega_rad_s: float, reduced_dipole_c_m: float, J_lower: float
) -> float:
    """Dimensionless absorption oscillator strength for the same reduced-E1 convention."""
    omega = _positive(omega_rad_s, "omega_rad_s")
    jl = _half_integer(J_lower, "J_lower")
    d = abs(float(reduced_dipole_c_m))
    return float(
        2.0 * M_E * omega * d**2
        / (3.0 * HBAR * E_CHARGE**2 * (2.0 * jl + 1.0))
    )


def e1_rate_from_oscillator_strength(
    omega_rad_s: float, f_lu: float, J_lower: float, J_upper: float
) -> float:
    """Convert absorption oscillator strength to the E1 spontaneous rate."""
    omega = _positive(omega_rad_s, "omega_rad_s")
    f = float(f_lu)
    if f < 0.0 or not math.isfinite(f):
        raise ValueError("f_lu must be finite and nonnegative")
    jl = _half_integer(J_lower, "J_lower")
    ju = _half_integer(J_upper, "J_upper")
    gl = 2.0 * jl + 1.0
    gu = 2.0 * ju + 1.0
    prefactor = E_CHARGE**2 * omega**2 / (2.0 * math.pi * EPSILON_0 * M_E * C**3)
    return float(prefactor * (gl / gu) * f)


def einstein_b_from_a_angular_density(
    A_ul: float, omega_rad_s: float, g_lower: float = 1.0, g_upper: float = 1.0
) -> tuple[float, float]:
    """Return (B_ul, B_lu) for radiation energy density per unit angular frequency.

    Convention: A_ul/B_ul = hbar*omega^3/(pi^2*c^3), and g_l B_lu = g_u B_ul.
    """
    A = _positive(A_ul, "A_ul")
    omega = _positive(omega_rad_s, "omega_rad_s")
    gl = _positive(g_lower, "g_lower")
    gu = _positive(g_upper, "g_upper")
    B_ul = A * math.pi**2 * C**3 / (HBAR * omega**3)
    B_lu = (gu / gl) * B_ul
    return float(B_ul), float(B_lu)


def branching_fractions(partial_rates_s: np.ndarray | list[float]) -> np.ndarray:
    rates = np.asarray(partial_rates_s, dtype=float)
    if rates.ndim != 1 or rates.size == 0 or np.any(~np.isfinite(rates)) or np.any(rates < 0.0):
        raise ValueError("partial rates must be a nonempty finite nonnegative 1D array")
    total = float(np.sum(rates))
    if total <= 0.0:
        raise ValueError("at least one partial rate must be positive")
    return rates / total


def radiative_lifetime_s(partial_rates_s: np.ndarray | list[float]) -> float:
    rates = np.asarray(partial_rates_s, dtype=float)
    if rates.ndim != 1 or rates.size == 0 or np.any(~np.isfinite(rates)) or np.any(rates < 0.0):
        raise ValueError("partial rates must be a nonempty finite nonnegative 1D array")
    total = float(np.sum(rates))
    if total <= 0.0:
        raise ValueError("total decay rate must be positive")
    return 1.0 / total


def natural_linewidth_hz(total_rate_s: float) -> float:
    """Lifetime-limited Lorentzian FWHM in ordinary frequency."""
    return _positive(total_rate_s, "total_rate_s") / (2.0 * math.pi)


def trk_captured_fraction(oscillator_strengths: np.ndarray | list[float], electron_count: float = 1.0) -> tuple[float, float]:
    """Return (captured_fraction, deficit) relative to a TRK target N."""
    f = np.asarray(oscillator_strengths, dtype=float)
    if f.ndim != 1 or f.size == 0 or np.any(~np.isfinite(f)) or np.any(f < 0.0):
        raise ValueError("oscillator strengths must be a nonempty finite nonnegative 1D array")
    n = _positive(electron_count, "electron_count")
    captured = float(np.sum(f) / n)
    return captured, 1.0 - captured


def angular_momentum_matrices(j: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return dimensionless Jx, Jy, Jz matrices in the descending-m basis."""
    j = _half_integer(j, "j")
    dim = int(round(2.0 * j + 1.0))
    mvals = np.array([j - k for k in range(dim)], dtype=float)
    jp = np.zeros((dim, dim), dtype=complex)
    index = {round(m, 10): i for i, m in enumerate(mvals)}
    for col, m in enumerate(mvals):
        mp = m + 1.0
        key = round(mp, 10)
        if key in index:
            row = index[key]
            jp[row, col] = math.sqrt(j * (j + 1.0) - m * (m + 1.0))
    jm = jp.conj().T
    jx = 0.5 * (jp + jm)
    jy = (jp - jm) / (2.0j)
    jz = np.diag(mvals.astype(complex))
    return jx, jy, jz


def hyperfine_zeeman_hamiltonian_hz(
    I: float,
    J: float,
    A_hfs_hz: float,
    B_tesla: float,
    g_J: float,
    g_I_bohr: float = 0.0,
) -> np.ndarray:
    """Hyperfine + axial Zeeman Hamiltonian divided by h, in Hz.

    H/h = A I.J + (mu_B/h) B (g_J J_z + g_I I_z),
    with dimensionless angular-momentum matrices.
    """
    I = _half_integer(I, "I")
    J = _half_integer(J, "J")
    A = float(A_hfs_hz)
    B = float(B_tesla)
    gJ = float(g_J)
    gI = float(g_I_bohr)
    if not all(math.isfinite(x) for x in (A, B, gJ, gI)):
        raise ValueError("Hamiltonian parameters must be finite")

    Ix, Iy, Iz = angular_momentum_matrices(I)
    Jx, Jy, Jz = angular_momentum_matrices(J)
    eye_i = np.eye(Ix.shape[0], dtype=complex)
    eye_j = np.eye(Jx.shape[0], dtype=complex)
    idotj = np.kron(Ix, Jx) + np.kron(Iy, Jy) + np.kron(Iz, Jz)
    zeeman = MU_B_OVER_H_HZ_T * B * (
        gI * np.kron(Iz, eye_j) + gJ * np.kron(eye_i, Jz)
    )
    H_hz = A * idotj + zeeman
    return 0.5 * (H_hz + H_hz.conj().T)


def hyperfine_zeeman_spectrum_hz(
    I: float,
    J: float,
    A_hfs_hz: float,
    B_tesla: float,
    g_J: float,
    g_I_bohr: float = 0.0,
) -> np.ndarray:
    H_hz = hyperfine_zeeman_hamiltonian_hz(I, J, A_hfs_hz, B_tesla, g_J, g_I_bohr)
    return np.linalg.eigvalsh(H_hz).real


def hyperfine_zeeman_map_hz(
    I: float,
    J: float,
    A_hfs_hz: float,
    fields_tesla: np.ndarray,
    g_J: float,
    g_I_bohr: float = 0.0,
) -> np.ndarray:
    fields = np.asarray(fields_tesla, dtype=float)
    if fields.ndim != 1 or fields.size == 0 or np.any(~np.isfinite(fields)):
        raise ValueError("fields_tesla must be a nonempty finite 1D array")
    return np.vstack([
        hyperfine_zeeman_spectrum_hz(I, J, A_hfs_hz, b, g_J, g_I_bohr)
        for b in fields
    ])


def two_level_field_map(
    fields: np.ndarray,
    e1_0: float,
    e2_0: float,
    slope1: float,
    slope2: float,
    coupling: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Two-level field sweep; returns eigenvalues and |basis-1|^2 weights."""
    x = np.asarray(fields, dtype=float)
    if x.ndim != 1 or x.size == 0 or np.any(~np.isfinite(x)):
        raise ValueError("fields must be a nonempty finite 1D array")
    v = float(coupling)
    energies = np.empty((x.size, 2), dtype=float)
    weights = np.empty((x.size, 2), dtype=float)
    for i, field in enumerate(x):
        H2 = np.array([
            [float(e1_0) + float(slope1) * field, v],
            [v, float(e2_0) + float(slope2) * field],
        ])
        vals, vecs = np.linalg.eigh(H2)
        energies[i] = vals
        weights[i] = np.abs(vecs[0, :]) ** 2
    return energies, weights
