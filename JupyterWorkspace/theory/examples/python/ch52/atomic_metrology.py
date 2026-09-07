"""Quantum-defect, polarizability, AC-Stark, and metrology diagnostics.

Volume VIII, Chapter 52, Commit 580.

Atomic units are used for quantum-defect energies, dipole matrix elements,
polarizabilities, angular frequencies (equivalently photon energies because
hbar=1), and field amplitudes unless a function name explicitly says SI/Hz.
The routines are deliberately transparent textbook models rather than a
replacement for high-accuracy atomic-structure software.
"""
from __future__ import annotations

import math
from typing import Iterable

import numpy as np
from scipy.optimize import brentq

# SI constants used only by the explicit SI conversion/metrology helpers.
C = 299_792_458.0
H = 6.626_070_15e-34
HBAR = 1.054_571_817e-34
K_B = 1.380_649e-23
EPSILON_0 = 8.854_187_8128e-12
ATOMIC_FIELD_V_M = 5.142_206_747_63e11
ATOMIC_POLARIZABILITY_SI = 1.648_777_274_36e-41  # C m^2 / V = C^2 m^2 / J
HARTREE_OVER_H_HZ = 6.579_683_920_499e15


def _positive(x: float, name: str) -> float:
    x = float(x)
    if not math.isfinite(x) or x <= 0.0:
        raise ValueError(f"{name} must be positive and finite")
    return x


def effective_quantum_number(n: float, delta: float) -> float:
    """Return n* = n-delta for a quantum-defect Rydberg series."""
    n = _positive(n, "n")
    delta = float(delta)
    if not math.isfinite(delta):
        raise ValueError("delta must be finite")
    nstar = n - delta
    if nstar <= 0.0:
        raise ValueError("require n-delta > 0")
    return nstar


def quantum_defect_binding_hartree(n: float, delta: float = 0.0, z_tail: float = 1.0) -> float:
    """Binding energy relative to threshold for a Coulomb tail -z_tail/r.

    E = -z_tail^2/[2 (n-delta)^2] Hartree.
    For neutral alkali-like atoms the asymptotic tail has z_tail=1.
    """
    z = _positive(z_tail, "z_tail")
    nstar = effective_quantum_number(n, delta)
    return -0.5 * z * z / (nstar * nstar)


def ritz_quantum_defect(n: float, delta0: float, delta2: float = 0.0, delta4: float = 0.0) -> float:
    """Simple explicit Ritz expansion about n-delta0.

    delta(n) ~= delta0 + delta2/(n-delta0)^2 + delta4/(n-delta0)^4.
    This is useful as a transparent regression model for high-n series.
    """
    nstar0 = effective_quantum_number(n, delta0)
    return float(delta0 + delta2 / nstar0**2 + delta4 / nstar0**4)


def core_polarization_potential_au(
    r_au: np.ndarray | float,
    alpha_core_au: float,
    cutoff_radius_au: float,
    cutoff_power: int = 6,
) -> np.ndarray:
    """Regularized polarization tail -alpha_c f(r)/(2 r^4) in atomic units.

    f(r)=1-exp[-(r/rho)^p] removes the unphysical r^-4 singularity inside
    the ionic core.  The long-range tail remains -alpha_c/(2 r^4).
    """
    r = np.asarray(r_au, dtype=float)
    alpha = _positive(alpha_core_au, "alpha_core_au")
    rho = _positive(cutoff_radius_au, "cutoff_radius_au")
    if np.any(~np.isfinite(r)) or np.any(r <= 0.0):
        raise ValueError("r_au must contain positive finite radii")
    if int(cutoff_power) != cutoff_power or cutoff_power < 5:
        raise ValueError("cutoff_power must be an integer >= 5")
    f = -np.expm1(-(r / rho) ** int(cutoff_power))
    return -0.5 * alpha * f / r**4


def _sos_arrays(delta_e_au: Iterable[float], reduced_dipoles_au: Iterable[float]) -> tuple[np.ndarray, np.ndarray]:
    de = np.asarray(list(delta_e_au), dtype=float)
    d = np.asarray(list(reduced_dipoles_au), dtype=float)
    if de.ndim != 1 or d.ndim != 1 or de.size == 0 or de.shape != d.shape:
        raise ValueError("delta_e_au and reduced_dipoles_au must be equal nonempty 1D arrays")
    if np.any(~np.isfinite(de)) or np.any(~np.isfinite(d)) or np.any(de == 0.0):
        raise ValueError("sum-over-states data must be finite and transition energies nonzero")
    return de, d


def scalar_polarizability_static_au(
    delta_e_au: Iterable[float], reduced_dipoles_au: Iterable[float], J: float = 0.0
) -> float:
    """Scalar static E1 polarizability from a reduced-matrix-element sum."""
    J = float(J)
    if not math.isfinite(J) or J < 0.0 or abs(2.0 * J - round(2.0 * J)) > 1e-10:
        raise ValueError("J must be a nonnegative integer or half-integer")
    de, d = _sos_arrays(delta_e_au, reduced_dipoles_au)
    prefactor = 2.0 / (3.0 * (2.0 * J + 1.0))
    return float(prefactor * np.sum(d * d / de))


def scalar_polarizability_dynamic_au(
    photon_energy_au: float,
    delta_e_au: Iterable[float],
    reduced_dipoles_au: Iterable[float],
    J: float = 0.0,
    resonance_guard: float = 1e-10,
) -> float:
    """Undamped scalar dynamic E1 polarizability alpha_0(omega).

    photon_energy_au is hbar*omega in Hartree (numerically omega in a.u.).
    The expression is intended away from resonances; a guard rejects a pole.
    """
    w = float(photon_energy_au)
    if not math.isfinite(w) or w < 0.0:
        raise ValueError("photon_energy_au must be finite and nonnegative")
    J = float(J)
    if not math.isfinite(J) or J < 0.0 or abs(2.0 * J - round(2.0 * J)) > 1e-10:
        raise ValueError("J must be a nonnegative integer or half-integer")
    de, d = _sos_arrays(delta_e_au, reduced_dipoles_au)
    denom = de * de - w * w
    scale = np.maximum(de * de, 1.0)
    if np.any(np.abs(denom) <= resonance_guard * scale):
        raise ValueError("dynamic polarizability evaluated too close to a resonance")
    prefactor = 2.0 / (3.0 * (2.0 * J + 1.0))
    return float(prefactor * np.sum(de * d * d / denom))


def differential_polarizability_dynamic_au(
    photon_energy_au: float,
    lower_data: tuple[Iterable[float], Iterable[float], float],
    upper_data: tuple[Iterable[float], Iterable[float], float],
) -> float:
    de_l, d_l, j_l = lower_data
    de_u, d_u, j_u = upper_data
    return (
        scalar_polarizability_dynamic_au(photon_energy_au, de_u, d_u, j_u)
        - scalar_polarizability_dynamic_au(photon_energy_au, de_l, d_l, j_l)
    )


def find_magic_photon_energy_au(
    bracket_au: tuple[float, float],
    lower_data: tuple[Iterable[float], Iterable[float], float],
    upper_data: tuple[Iterable[float], Iterable[float], float],
) -> float:
    """Root of Delta alpha(omega)=alpha_upper-alpha_lower inside a pole-free bracket."""
    lo, hi = map(float, bracket_au)
    if not (0.0 <= lo < hi):
        raise ValueError("bracket must satisfy 0 <= lo < hi")
    f = lambda w: differential_polarizability_dynamic_au(w, lower_data, upper_data)
    return float(brentq(f, lo, hi, xtol=1e-14, rtol=1e-13, maxiter=200))


def ac_stark_shift_hartree(alpha_au: float, field_amplitude_au: float) -> float:
    """Cycle-averaged scalar AC Stark shift for E(t)=E0 cos(omega t)."""
    alpha = float(alpha_au)
    e0 = float(field_amplitude_au)
    if not math.isfinite(alpha) or not math.isfinite(e0):
        raise ValueError("alpha and field amplitude must be finite")
    return -0.25 * alpha * e0 * e0


def ac_stark_shift_hz(alpha_au: float, field_amplitude_v_m: float) -> float:
    e_au = float(field_amplitude_v_m) / ATOMIC_FIELD_V_M
    return ac_stark_shift_hartree(alpha_au, e_au) * HARTREE_OVER_H_HZ


def intensity_to_field_amplitude_v_m(intensity_w_m2: float) -> float:
    intensity = float(intensity_w_m2)
    if not math.isfinite(intensity) or intensity < 0.0:
        raise ValueError("intensity_w_m2 must be finite and nonnegative")
    return math.sqrt(2.0 * intensity / (C * EPSILON_0))


def blackbody_mean_square_field_v2_m2(temperature_k: float) -> float:
    """Mean-square electric field of ideal blackbody radiation."""
    t = _positive(temperature_k, "temperature_k")
    energy_density = math.pi**2 * (K_B * t) ** 4 / (15.0 * HBAR**3 * C**3)
    return energy_density / EPSILON_0


def bbr_clock_shift_hz(delta_alpha_au: float, temperature_k: float) -> float:
    """Static-approximation differential blackbody Stark shift in Hz.

    Delta E = -(1/2) Delta alpha <E^2>. Dynamic BBR corrections are omitted.
    """
    da_si = float(delta_alpha_au) * ATOMIC_POLARIZABILITY_SI
    e2 = blackbody_mean_square_field_v2_m2(temperature_k)
    return float(-0.5 * da_si * e2 / H)


def fractional_frequency_shift(shift_hz: float, clock_frequency_hz: float) -> float:
    nu = _positive(clock_frequency_hz, "clock_frequency_hz")
    shift = float(shift_hz)
    if not math.isfinite(shift):
        raise ValueError("shift_hz must be finite")
    return shift / nu


def quality_factor(clock_frequency_hz: float, linewidth_hz: float) -> float:
    return _positive(clock_frequency_hz, "clock_frequency_hz") / _positive(linewidth_hz, "linewidth_hz")


def uncertainty_quadrature(components: Iterable[float]) -> float:
    values = np.asarray(list(components), dtype=float)
    if values.ndim != 1 or values.size == 0 or np.any(~np.isfinite(values)) or np.any(values < 0.0):
        raise ValueError("uncertainty components must be a nonempty finite nonnegative 1D array")
    return float(np.sqrt(np.sum(values * values)))
