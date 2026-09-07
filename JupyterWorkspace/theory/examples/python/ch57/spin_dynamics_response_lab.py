"""Chapter 57 Commit 627: driven spin dynamics and response.

Conventions
-----------
hbar = 1.
Single-spin lab Hamiltonian: H(t) = (omega0/2) sigma_z + omega1 cos(omega t) sigma_x.
RWA Hamiltonian: H_RWA = 1/2 (delta sigma_z + omega1 sigma_x),
with delta = omega0 - omega and generalized Rabi frequency
Omega_R = sqrt(delta^2 + omega1^2).

Landau-Zener Hamiltonian: H(t)=1/2 v t sigma_z + 1/2 Delta_LZ sigma_x,
so P_D = exp[-pi Delta_LZ^2/(2 v)] for v>0.
"""
from __future__ import annotations
import numpy as np

SX = np.array([[0, 1], [1, 0]], dtype=complex)
SY = np.array([[0, -1j], [1j, 0]], dtype=complex)
SZ = np.array([[1, 0], [0, -1]], dtype=complex)
I2 = np.eye(2, dtype=complex)
PAULI = (SX, SY, SZ)
SPIN = tuple(0.5 * s for s in PAULI)
UP = np.array([1.0, 0.0], dtype=complex)
DOWN = np.array([0.0, 1.0], dtype=complex)
PLUS_X = (UP + DOWN) / np.sqrt(2.0)
MINUS_X = (UP - DOWN) / np.sqrt(2.0)

def normalize(psi):
    v = np.asarray(psi, dtype=complex).reshape(-1)
    n = np.linalg.norm(v)
    if n <= 0:
        raise ValueError("state norm must be positive")
    return v / n

def bloch_vector(psi):
    v = normalize(psi)
    return np.array([np.real(np.vdot(v, s @ v)) for s in PAULI], dtype=float)

def pauli_vector(vec):
    a = np.asarray(vec, dtype=float)
    if a.shape != (3,) or not np.all(np.isfinite(a)):
        raise ValueError("vector must be a finite three-vector")
    return sum(a[i] * PAULI[i] for i in range(3))

def unitary_from_omega_vector(omega_vec, time):
    a = np.asarray(omega_vec, dtype=float)
    mag = float(np.linalg.norm(a))
    t = float(time)
    if mag == 0.0:
        return I2.copy()
    n_sigma = pauli_vector(a / mag)
    angle = 0.5 * mag * t
    return np.cos(angle) * I2 - 1j * np.sin(angle) * n_sigma

def static_spin_hamiltonian(omega_vec):
    return 0.5 * pauli_vector(omega_vec)

def evolve_static(psi, omega_vec, time):
    return unitary_from_omega_vector(omega_vec, time) @ normalize(psi)

def rwa_hamiltonian(delta, omega1):
    return 0.5 * (float(delta) * SZ + float(omega1) * SX)

def generalized_rabi_frequency(delta, omega1):
    return float(np.hypot(float(delta), float(omega1)))

def rabi_excitation_probability(delta, omega1, time):
    om = generalized_rabi_frequency(delta, omega1)
    if om == 0.0:
        return 0.0
    return float((omega1 * omega1 / (om * om)) * np.sin(0.5 * om * time) ** 2)

def max_rabi_excitation(delta, omega1):
    om2 = float(delta) ** 2 + float(omega1) ** 2
    return 0.0 if om2 == 0.0 else float(float(omega1) ** 2 / om2)

def pi_pulse_time(omega1):
    o = abs(float(omega1))
    if o == 0.0:
        raise ValueError("omega1 must be nonzero")
    return float(np.pi / o)

def half_pi_pulse_time(omega1):
    return 0.5 * pi_pulse_time(omega1)

def pulse_unitary_x(theta):
    return unitary_from_omega_vector([float(theta), 0.0, 0.0], 1.0)

def free_detuning_unitary(detuning, time):
    return unitary_from_omega_vector([0.0, 0.0, float(detuning)], float(time))

def hahn_echo_unitary(detuning, tau):
    uz = free_detuning_unitary(detuning, tau)
    ux = pulse_unitary_x(np.pi)
    return uz @ ux @ uz

def state_fidelity(psi, phi):
    a = normalize(psi)
    b = normalize(phi)
    return float(abs(np.vdot(a, b)) ** 2)

def echo_refocusing_fidelity(detuning, tau, psi=PLUS_X):
    out = hahn_echo_unitary(detuning, tau) @ normalize(psi)
    # A pi_x pulse maps +x to itself up to global phase; compare with input.
    return state_fidelity(out, psi)

def kubo_chi_xx_time(time, omega0):
    t = np.asarray(time, dtype=float)
    out = 0.5 * np.sin(float(omega0) * t)
    out = np.where(t >= 0.0, out, 0.0)
    return float(out) if out.ndim == 0 else out

def absorptive_susceptibility(omega, omega0, eta):
    eta = float(eta)
    if eta <= 0:
        raise ValueError("eta must be positive")
    w = np.asarray(omega, dtype=float)
    value = 0.25 * eta / ((w - float(omega0)) ** 2 + eta * eta)
    return float(value) if value.ndim == 0 else value

def susceptibility_peak_value(eta):
    eta = float(eta)
    if eta <= 0:
        raise ValueError("eta must be positive")
    return float(1.0 / (4.0 * eta))

def kron(a, b):
    return np.kron(a, b)

def singlet_state():
    return normalize(np.kron(UP, DOWN) - np.kron(DOWN, UP))

def triplet_zero_state():
    return normalize(np.kron(UP, DOWN) + np.kron(DOWN, UP))

def exchange_hamiltonian(J=1.0):
    return 0.25 * float(J) * sum(np.kron(s, s) for s in PAULI)

def exchange_unitary(J, time):
    H = exchange_hamiltonian(J)
    vals, vecs = np.linalg.eigh(H)
    return (vecs * np.exp(-1j * vals * float(time))) @ vecs.conj().T

def swap_operator():
    return np.array([
        [1, 0, 0, 0],
        [0, 0, 1, 0],
        [0, 1, 0, 0],
        [0, 0, 0, 1],
    ], dtype=complex)

def global_phase_aligned_error(U, V):
    U = np.asarray(U, dtype=complex)
    V = np.asarray(V, dtype=complex)
    overlap = np.trace(V.conj().T @ U)
    if abs(overlap) == 0:
        return float(np.linalg.norm(U - V))
    phase = overlap / abs(overlap)
    return float(np.linalg.norm(U - phase * V))

def swap_time(J):
    j = abs(float(J))
    if j == 0:
        raise ValueError("J must be nonzero")
    return float(np.pi / j)

def sqrt_swap_time(J):
    return 0.5 * swap_time(J)

def gradient_operator():
    return 0.5 * (np.kron(SZ, I2) - np.kron(I2, SZ))

def singlet_triplet_gradient_matrix_element():
    s = singlet_state()
    t0 = triplet_zero_state()
    return complex(np.vdot(s, gradient_operator() @ t0))

def driven_exchange_hamiltonian(J, gradient):
    return exchange_hamiltonian(J) + float(gradient) * gradient_operator()

def st_subspace_hamiltonian(J, gradient):
    s = singlet_state()
    t = triplet_zero_state()
    H = driven_exchange_hamiltonian(J, gradient)
    B = np.column_stack([s, t])
    return B.conj().T @ H @ B

def landau_zener_hamiltonian(time, sweep_rate, gap):
    return 0.5 * (float(sweep_rate) * float(time) * SZ + float(gap) * SX)

def landau_zener_diabatic_probability(sweep_rate, gap):
    v = float(sweep_rate)
    d = float(gap)
    if v <= 0:
        raise ValueError("sweep_rate must be positive")
    return float(np.exp(-np.pi * d * d / (2.0 * v)))

def two_level_step_unitary(omega_vec, dt):
    return unitary_from_omega_vector(omega_vec, dt)

def propagate_landau_zener(sweep_rate, gap, tmax=10.0, steps=4000):
    v = float(sweep_rate)
    d = float(gap)
    T = float(tmax)
    n = int(steps)
    if v <= 0 or T <= 0 or n < 2:
        raise ValueError("sweep_rate, tmax, and steps must be positive")
    dt = 2.0 * T / n
    psi = UP.copy()  # diabatic state |up> at large negative time
    for k in range(n):
        tm = -T + (k + 0.5) * dt
        psi = two_level_step_unitary([d, 0.0, v * tm], dt) @ psi
    psi = normalize(psi)
    return {
        "psi": psi,
        "diabatic_survival": float(abs(np.vdot(UP, psi)) ** 2),
        "norm": float(np.vdot(psi, psi).real),
    }

def reference_summary():
    omega1 = 2.0
    tpi = pi_pulse_time(omega1)
    U_swap = exchange_unitary(0.8, swap_time(0.8))
    U_sqrt = exchange_unitary(0.8, sqrt_swap_time(0.8))
    lz_formula = landau_zener_diabatic_probability(2.0, 1.0)
    lz_num = propagate_landau_zener(2.0, 1.0, tmax=12.0, steps=6000)
    return {
        "rabi_pi_probability": rabi_excitation_probability(0.0, omega1, tpi),
        "detuned_max_probability": max_rabi_excitation(1.0, 2.0),
        "echo_fidelity": echo_refocusing_fidelity(1.7, 2.3),
        "susceptibility_peak_eta_0p2": susceptibility_peak_value(0.2),
        "swap_error": global_phase_aligned_error(U_swap, swap_operator()),
        "sqrt_swap_squared_error": global_phase_aligned_error(U_sqrt @ U_sqrt, swap_operator()),
        "st_gradient_matrix_element": [singlet_triplet_gradient_matrix_element().real, singlet_triplet_gradient_matrix_element().imag],
        "lz_formula_v2_gap1": lz_formula,
        "lz_numerical_v2_gap1": lz_num["diabatic_survival"],
        "lz_norm": lz_num["norm"],
    }

if __name__ == "__main__":
    import json
    print(json.dumps(reference_summary(), indent=2))
