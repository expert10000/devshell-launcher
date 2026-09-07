"""Computational companion for Volume VIII, Chapter 52, Commit 577.

Atomic units are used throughout: hbar = m_e = e^2/(4*pi*eps0) = 1.
The emphasis is transparent model diagnostics rather than production quantum
chemistry.  Helium is used because a single radial orbital already illustrates
variational screening, self-consistency, exchange bookkeeping, and correlation.
"""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np
from scipy.linalg import eigh_tridiagonal


HARTREE_TO_EV = 27.211386245988
HELIUM_HF_REFERENCE = -2.8616799956
HELIUM_NONREL_REFERENCE = -2.9037243770


def helium_variational_energy(zeta: np.ndarray | float, Z: float = 2.0) -> np.ndarray:
    """Expectation value of the full two-electron Hamiltonian for a 1s^2
    product with hydrogenic exponent zeta, in Hartree atomic units.
    """
    z = np.asarray(zeta, dtype=float)
    if np.any(z <= 0) or Z <= 0:
        raise ValueError("zeta and Z must be positive")
    return z * z - 2.0 * Z * z + 5.0 * z / 8.0


def helium_optimal_zeta(Z: float = 2.0) -> float:
    if Z <= 5.0 / 16.0:
        raise ValueError("simple positive-exponent optimum requires Z>5/16")
    return Z - 5.0 / 16.0


def helium_variational_minimum(Z: float = 2.0) -> float:
    z = helium_optimal_zeta(Z)
    return float(helium_variational_energy(z, Z))


def hydrogenic_1s_radial_probability(r: np.ndarray | float, zeta: float) -> np.ndarray:
    """Normalized radial probability P(r)=r^2 |R_1s(r)|^2."""
    rr = np.asarray(r, dtype=float)
    if np.any(rr < 0) or zeta <= 0:
        raise ValueError("require r>=0 and zeta>0")
    return 4.0 * zeta**3 * rr**2 * np.exp(-2.0 * zeta * rr)


def hydrogenic_1s_mean_radius(zeta: float) -> float:
    if zeta <= 0:
        raise ValueError("zeta must be positive")
    return 3.0 / (2.0 * zeta)


def helium_coulomb_integral_exponential(zeta: float) -> float:
    if zeta <= 0:
        raise ValueError("zeta must be positive")
    return 5.0 * zeta / 8.0


def _normalize_radial(u: np.ndarray, dr: float) -> np.ndarray:
    norm = np.sqrt(np.sum(np.asarray(u) ** 2) * dr)
    if norm <= 0 or not np.isfinite(norm):
        raise ValueError("invalid radial norm")
    return np.asarray(u, dtype=float) / norm


def spherical_direct_potential(u: np.ndarray, r: np.ndarray) -> np.ndarray:
    """Direct potential of one normalized spherical electron.

    u is normalized as integral |u|^2 dr = 1.  A rectangle-rule discretization
    is used consistently with the radial finite-difference inner product.
    """
    u = np.asarray(u, dtype=float)
    r = np.asarray(r, dtype=float)
    if u.shape != r.shape or r.ndim != 1 or r.size < 8:
        raise ValueError("u and r must be equal one-dimensional arrays")
    if np.any(r <= 0):
        raise ValueError("radial grid must exclude r=0 and stay positive")
    drs = np.diff(r)
    if not np.allclose(drs, drs[0], rtol=1e-9, atol=1e-12):
        raise ValueError("radial grid must be uniform")
    dr = float(drs[0])
    density = u * u
    inside = np.cumsum(density) * dr
    outside = np.cumsum((density / r)[::-1])[::-1] * dr
    # Current cell occurs in both rectangle sums; subtract one copy.
    return inside / r + outside - density * dr / r


def _tridiagonal_expectation(u: np.ndarray, diag: np.ndarray, off: np.ndarray) -> float:
    denom = float(np.sum(u * u))
    return float((np.sum(diag * u * u) + 2.0 * np.sum(off * u[:-1] * u[1:])) / denom)


@dataclass(frozen=True)
class HeliumSCFResult:
    energy: float
    orbital_energy: float
    direct_energy: float
    one_electron_energy: float
    iterations: int
    converged: bool
    r: np.ndarray
    u: np.ndarray
    direct_potential: np.ndarray
    energy_history: np.ndarray


def helium_restricted_scf(
    *,
    Z: float = 2.0,
    r_max: float = 24.0,
    n_grid: int = 2400,
    mixing: float = 0.35,
    tolerance: float = 2e-10,
    max_iterations: int = 160,
    initial_zeta: float | None = None,
) -> HeliumSCFResult:
    """Restricted one-spatial-orbital SCF for the helium-like 1s^2 ground state.

    For two opposite-spin electrons occupying the same spatial orbital, the
    Hartree-Fock equations reduce to one radial equation with the direct field
    of the other electron.  This small solver is intended for diagnostics and
    converges to the helium HF limit under radial-grid refinement.
    """
    if Z <= 0 or r_max <= 0 or n_grid < 200:
        raise ValueError("invalid atomic/grid parameters")
    if not 0 < mixing <= 1:
        raise ValueError("mixing must lie in (0,1]")
    if tolerance <= 0 or max_iterations < 1:
        raise ValueError("invalid convergence parameters")

    dr = r_max / (n_grid + 1)
    r = np.arange(1, n_grid + 1, dtype=float) * dr
    z0 = float(initial_zeta if initial_zeta is not None else Z)
    if z0 <= 0:
        raise ValueError("initial_zeta must be positive")
    # u=r R for a hydrogenic 1s orbital; overall prefactor is normalized below.
    u = _normalize_radial(r * np.exp(-z0 * r), dr)

    off = np.full(n_grid - 1, -0.5 / dr**2)
    kinetic_diag = np.full(n_grid, 1.0 / dr**2)
    h_diag = kinetic_diag - Z / r

    history: list[float] = []
    converged = False
    orbital_energy = np.nan

    for iteration in range(1, max_iterations + 1):
        v_direct = spherical_direct_potential(u, r)
        f_diag = h_diag + v_direct
        vals, vecs = eigh_tridiagonal(f_diag, off, select="i", select_range=(0, 0))
        trial = _normalize_radial(vecs[:, 0], dr)
        if np.dot(trial, u) < 0:
            trial = -trial
        u = _normalize_radial((1.0 - mixing) * u + mixing * trial, dr)

        v_direct = spherical_direct_potential(u, r)
        h_expect = _tridiagonal_expectation(u, h_diag, off)
        direct = float(np.sum(u * u * v_direct) * dr)
        total = 2.0 * h_expect + direct
        history.append(total)
        orbital_energy = h_expect + direct

        if len(history) > 1 and abs(history[-1] - history[-2]) < tolerance:
            converged = True
            break

    return HeliumSCFResult(
        energy=float(history[-1]),
        orbital_energy=float(orbital_energy),
        direct_energy=float(direct),
        one_electron_energy=float(h_expect),
        iterations=iteration,
        converged=converged,
        r=r,
        u=u,
        direct_potential=v_direct,
        energy_history=np.asarray(history),
    )


def helium_approximation_ladder() -> dict[str, float]:
    """Representative full-Hamiltonian energies (Hartree) for comparison."""
    z_bare = 2.0
    return {
        "fixed_1s_full_expectation": float(helium_variational_energy(z_bare)),
        "optimized_exponential": helium_variational_minimum(),
        "hartree_fock_limit": HELIUM_HF_REFERENCE,
        "correlated_nonrelativistic": HELIUM_NONREL_REFERENCE,
    }


def correlation_energy(reference_hf: float = HELIUM_HF_REFERENCE,
                       reference_exact: float = HELIUM_NONREL_REFERENCE) -> float:
    return float(reference_exact - reference_hf)
