"""Spectroscopy companion for Volume VIII, Chapter 52, Commit 578.

The routines are intentionally small and transparent.  Energies may be supplied
in any consistent units unless a function explicitly names a unit.  Angular
momenta are accepted as integer or half-integer quantum numbers.
"""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np

ELECTRON_MASS_U = 5.48579909065e-4
CM1_TO_GHZ = 29.9792458


def _is_half_integer(x: float, tol: float = 1e-10) -> bool:
    return abs(2.0 * x - round(2.0 * x)) < tol


def _validate_j(x: float, name: str) -> float:
    x = float(x)
    if x < 0 or not _is_half_integer(x):
        raise ValueError(f"{name} must be a nonnegative integer or half-integer")
    return x


def allowed_total_j(j1: float, j2: float) -> np.ndarray:
    """Angular-momentum addition rule |j1-j2| <= J <= j1+j2."""
    j1 = _validate_j(j1, "j1")
    j2 = _validate_j(j2, "j2")
    lo = abs(j1 - j2)
    hi = j1 + j2
    n = int(round(hi - lo)) + 1
    return lo + np.arange(n, dtype=float)


def ci_two_configuration(e1: float, e2: float, coupling: float):
    """Eigenvalues/eigenvectors of a two-configuration CI Hamiltonian."""
    h = np.array([[float(e1), float(coupling)], [float(coupling), float(e2)]])
    vals, vecs = np.linalg.eigh(h)
    return vals, vecs


def ci_gap(e1: float, e2: float, coupling: float) -> float:
    """Exact adiabatic gap for a two-state CI problem."""
    return float(np.sqrt((e1 - e2) ** 2 + 4.0 * coupling**2))


def lande_g_factor(L: float, S: float, J: float, g_s: float = 2.00231930436) -> float:
    """Lande g factor in LS coupling, retaining an explicit electron-spin g."""
    L = _validate_j(L, "L")
    S = _validate_j(S, "S")
    J = _validate_j(J, "J")
    if J == 0:
        return 0.0
    if J not in allowed_total_j(L, S):
        raise ValueError("J is not allowed by coupling L and S")
    jj = J * (J + 1.0)
    ll = L * (L + 1.0)
    ss = S * (S + 1.0)
    return float(1.0 + (g_s - 1.0) * (jj + ss - ll) / (2.0 * jj))


def ls_spin_orbit_energy(A: float, L: float, S: float, J: float, centroid: float = 0.0) -> float:
    """First-order LS-coupled spin-orbit level E_J = Ebar + A <L.S>."""
    L = _validate_j(L, "L")
    S = _validate_j(S, "S")
    J = _validate_j(J, "J")
    if J not in allowed_total_j(L, S):
        raise ValueError("J is not allowed by coupling L and S")
    k = J * (J + 1.0) - L * (L + 1.0) - S * (S + 1.0)
    return float(centroid + 0.5 * A * k)


def ls_term_energies(A: float, L: float, S: float, centroid: float = 0.0):
    js = allowed_total_j(L, S)
    es = np.array([ls_spin_orbit_energy(A, L, S, j, centroid) for j in js])
    return js, es


def statistical_centroid(js: np.ndarray, energies: np.ndarray) -> float:
    js = np.asarray(js, dtype=float)
    energies = np.asarray(energies, dtype=float)
    if js.shape != energies.shape or js.ndim != 1 or js.size == 0:
        raise ValueError("js and energies must be equal nonempty one-dimensional arrays")
    w = 2.0 * js + 1.0
    return float(np.sum(w * energies) / np.sum(w))


def fit_ls_spin_orbit(js, energies, L: float, S: float):
    """Least-squares fit of centroid and LS spin-orbit constant A."""
    js = np.asarray(js, dtype=float)
    y = np.asarray(energies, dtype=float)
    if js.shape != y.shape or js.ndim != 1 or js.size < 2:
        raise ValueError("need at least two matched J/energy values")
    x = np.array([
        0.5 * (j * (j + 1.0) - L * (L + 1.0) - S * (S + 1.0))
        for j in js
    ])
    design = np.column_stack([np.ones_like(x), x])
    coeff, *_ = np.linalg.lstsq(design, y, rcond=None)
    pred = design @ coeff
    rms = float(np.sqrt(np.mean((y - pred) ** 2)))
    return {"centroid": float(coeff[0]), "A": float(coeff[1]), "predicted": pred, "rms": rms}


def hyperfine_energy(A: float, I: float, J: float, F: float, B: float = 0.0) -> float:
    """Magnetic-dipole plus electric-quadrupole hyperfine energy.

    E = A K/2 + B * [(3/4)K(K+1)-I(I+1)J(J+1)] /
        [2 I(2I-1) J(2J-1)].
    The B term vanishes automatically when I<1 or J<1.
    """
    I = _validate_j(I, "I")
    J = _validate_j(J, "J")
    F = _validate_j(F, "F")
    if F not in allowed_total_j(I, J):
        raise ValueError("F is not allowed by coupling I and J")
    K = F * (F + 1.0) - I * (I + 1.0) - J * (J + 1.0)
    e = 0.5 * A * K
    if B != 0.0 and I >= 1.0 and J >= 1.0:
        denom = 2.0 * I * (2.0 * I - 1.0) * J * (2.0 * J - 1.0)
        quad = (0.75 * K * (K + 1.0) - I * (I + 1.0) * J * (J + 1.0)) / denom
        e += B * quad
    return float(e)


def hyperfine_multiplet(A: float, I: float, J: float, B: float = 0.0):
    fs = allowed_total_j(I, J)
    es = np.array([hyperfine_energy(A, I, J, f, B) for f in fs])
    return fs, es


def reduced_mass_scale(nuclear_mass_u: float) -> float:
    """mu/m_e for an electron bound to a nucleus of mass M in unified atomic mass units."""
    M = float(nuclear_mass_u)
    if M <= 0:
        raise ValueError("nuclear mass must be positive")
    return M / (M + ELECTRON_MASS_U)


def normal_mass_isotope_shift(reference_frequency_hz: float, mass_ref_u: float, mass_target_u: float) -> float:
    """Target-minus-reference shift from reduced-mass scaling alone."""
    nu = float(reference_frequency_hz)
    if nu <= 0:
        raise ValueError("reference frequency must be positive")
    return float(nu * (reduced_mass_scale(mass_target_u) / reduced_mass_scale(mass_ref_u) - 1.0))


def isotope_shift_model(delta_inv_mass: np.ndarray | float, delta_r2: np.ndarray | float,
                        K_mass: float, F_field: float) -> np.ndarray:
    """Linear mass-plus-field isotope-shift model."""
    dm = np.asarray(delta_inv_mass, dtype=float)
    dr2 = np.asarray(delta_r2, dtype=float)
    return K_mass * dm + F_field * dr2


def transition_wavenumber(upper_cm1: float, lower_cm1: float) -> float:
    wn = float(upper_cm1) - float(lower_cm1)
    if wn <= 0:
        raise ValueError("upper term value must exceed lower term value")
    return wn


def wavenumber_to_wavelength_nm(wavenumber_cm1: float) -> float:
    wn = float(wavenumber_cm1)
    if wn <= 0:
        raise ValueError("wavenumber must be positive")
    return 1.0e7 / wn


def electric_dipole_allowed(J_lower: float, J_upper: float, parity_changes: bool) -> bool:
    """Angular/parity part of the E1 selection rule; J=0 -> J'=0 is forbidden."""
    jl = _validate_j(J_lower, "J_lower")
    ju = _validate_j(J_upper, "J_upper")
    if not parity_changes:
        return False
    d = abs(ju - jl)
    return d <= 1.0 + 1e-12 and not (jl == 0.0 and ju == 0.0)


@dataclass(frozen=True)
class SpectroscopicLine:
    lower_cm1: float
    upper_cm1: float

    @property
    def wavenumber_cm1(self) -> float:
        return transition_wavenumber(self.upper_cm1, self.lower_cm1)

    @property
    def wavelength_nm(self) -> float:
        return wavenumber_to_wavelength_nm(self.wavenumber_cm1)
