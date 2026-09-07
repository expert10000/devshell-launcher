"""Chapter 49 strongly correlated matter computational companion."""
from __future__ import annotations
import math
import numpy as np


def critical_scaling_variable(delta, size: float, nu: float):
    if size <= 0 or nu <= 0:
        raise ValueError("size and nu must be positive")
    return np.asarray(delta, dtype=float) * float(size) ** (1.0 / float(nu))


def correction_aware_observable(delta, size: float, nu: float, omega: float, correction_amplitude: float = 0.2):
    if size <= 0 or nu <= 0 or omega <= 0:
        raise ValueError("size, nu and omega must be positive")
    x = critical_scaling_variable(delta, size, nu)
    return np.tanh(x) + float(correction_amplitude) * float(size) ** (-float(omega))


def linear_rg_flow(u0, y: float, ell):
    return np.asarray(u0, dtype=float) * np.exp(float(y) * np.asarray(ell, dtype=float))


def classify_rg_direction(y: float, tol: float = 1e-12) -> str:
    if y > tol:
        return "relevant"
    if y < -tol:
        return "irrelevant"
    return "marginal"


def green_zero_frequency_from_hamiltonian(hamiltonian):
    h = np.asarray(hamiltonian, dtype=complex)
    if h.ndim != 2 or h.shape[0] != h.shape[1]:
        raise ValueError("hamiltonian must be square")
    if not np.allclose(h, h.conj().T):
        raise ValueError("hamiltonian must be Hermitian")
    return -np.linalg.inv(h)


def topological_hamiltonian_from_green(green0):
    g = np.asarray(green0, dtype=complex)
    if g.ndim != 2 or g.shape[0] != g.shape[1]:
        raise ValueError("green function must be square")
    return -np.linalg.inv(g)


def inverse_condition_number(matrix) -> float:
    a = np.asarray(matrix, dtype=complex)
    c = np.linalg.cond(a)
    if not np.isfinite(c) or c == 0:
        return 0.0
    return float(1.0 / c)


def z2_wilson_loop(links) -> int:
    a = np.asarray(links, dtype=int).ravel()
    if a.size == 0 or not np.all(np.isin(a, (-1, 1))):
        raise ValueError("Z2 links must be a nonempty sequence of +/-1")
    return int(np.prod(a))


def area_law_wilson(area, string_tension: float):
    if string_tension < 0:
        raise ValueError("string tension must be nonnegative")
    a = np.asarray(area, dtype=float)
    if np.any(a < 0):
        raise ValueError("areas must be nonnegative")
    return np.exp(-float(string_tension) * a)


def fit_string_tension(areas, wilson_values) -> float:
    a = np.asarray(areas, dtype=float); w = np.asarray(wilson_values, dtype=float)
    if a.size < 2 or a.shape != w.shape or np.any(w <= 0) or np.any(w > 1):
        raise ValueError("need matching positive Wilson-loop data")
    slope, _ = np.polyfit(a, -np.log(w), 1)
    return float(slope)


def nonfermi_self_energy(omega, prefactor: float = 1.0, exponent: float = 2.0/3.0):
    if prefactor < 0 or exponent <= 0:
        raise ValueError("prefactor and exponent must be positive")
    w = np.asarray(omega, dtype=float)
    return -1j * float(prefactor) * np.abs(w) ** float(exponent)


def quasiparticle_decay_ratio(omega: float, prefactor: float = 1.0, exponent: float = 2.0/3.0) -> float:
    if omega == 0:
        raise ValueError("omega must be nonzero")
    return float(abs(nonfermi_self_energy(float(omega), prefactor, exponent).imag) / abs(float(omega)))


def omega_t_variable(omega, temperature: float, k_b: float = 1.0):
    if temperature <= 0 or k_b <= 0:
        raise ValueError("temperature and k_b must be positive")
    return np.asarray(omega, dtype=float) / (float(k_b) * float(temperature))


def omega_t_response(omega, temperature: float, exponent_x: float = 0.5, k_b: float = 1.0):
    x = omega_t_variable(omega, temperature, k_b)
    return float(temperature) ** (-float(exponent_x)) / (1.0 + x*x)


def planckian_rate(temperature: float, alpha: float = 1.0, k_b: float = 1.0, hbar: float = 1.0) -> float:
    if temperature < 0 or alpha < 0 or k_b <= 0 or hbar <= 0:
        raise ValueError("invalid Planckian parameters")
    return float(alpha * k_b * temperature / hbar)


def nodal_gap(theta, delta0: float = 1.0, harmonic: int = 2):
    if harmonic <= 0:
        raise ValueError("harmonic must be positive")
    return float(delta0) * np.cos(int(harmonic) * np.asarray(theta, dtype=float))


def dirac_density_of_states(energy, v_f: float, v_delta: float, degeneracy: float = 4.0):
    if v_f <= 0 or v_delta <= 0 or degeneracy <= 0:
        raise ValueError("velocities and degeneracy must be positive")
    e = np.asarray(energy, dtype=float)
    return float(degeneracy) * np.abs(e) / (2.0 * math.pi * float(v_f) * float(v_delta))


def moire_length(lattice_constant: float, twist_angle_radians: float) -> float:
    if lattice_constant <= 0 or twist_angle_radians == 0:
        raise ValueError("lattice constant must be positive and twist nonzero")
    return float(lattice_constant / (2.0 * abs(math.sin(twist_angle_radians / 2.0))))


def moire_projection_hierarchy(width: float, interaction: float, remote_gap: float, tolerance: float = 0.3):
    if width < 0 or interaction <= 0 or remote_gap <= 0 or tolerance <= 0:
        raise ValueError("invalid energy scales")
    r_flat = width / interaction
    r_mix = interaction / remote_gap
    return float(r_flat), float(r_mix), bool(r_flat < tolerance and r_mix < tolerance)


def floquet_prethermal_time(drive_frequency: float, local_scale: float, prefactor: float = 1.0) -> float:
    if drive_frequency <= 0 or local_scale <= 0 or prefactor <= 0:
        raise ValueError("all scales must be positive")
    return float(prefactor * math.exp(drive_frequency / local_scale))


def leading_pairing_eigenpair(kernel):
    k = np.asarray(kernel, dtype=float)
    if k.ndim != 2 or k.shape[0] != k.shape[1] or not np.allclose(k, k.T):
        raise ValueError("kernel must be a real symmetric square matrix")
    vals, vecs = np.linalg.eigh(-k)
    idx = int(np.argmax(vals))
    v = vecs[:, idx]
    pivot = int(np.argmax(np.abs(v)))
    if v[pivot] < 0:
        v = -v
    return float(vals[idx]), v
