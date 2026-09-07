"""Small deterministic diagnostics for Chapter 42: Berry phase and quantum geometry."""
from __future__ import annotations
import math
import numpy as np

TWO_PI = 2.0 * math.pi


def wrap_phase(phi: float) -> float:
    """Return phase in (-pi, pi]."""
    x = (float(phi) + math.pi) % TWO_PI - math.pi
    return math.pi if np.isclose(x, -math.pi) else x


def solid_angle_cone(theta: float) -> float:
    return TWO_PI * (1.0 - math.cos(float(theta)))


def spin_half_berry_phase(theta: float, branch: int = +1) -> float:
    """Berry phase for a spin-1/2 eigenbranch around a cone.

    branch=+1 denotes the upper d.sigma eigenstate and branch=-1 the lower.
    Convention follows gamma_+- = -/+ Omega/2.
    """
    if branch not in (-1, +1):
        raise ValueError("branch must be +1 or -1")
    return -0.5 * branch * solid_angle_cone(theta)


def massive_dirac_curvature(kx, ky, mass: float, branch: int = -1):
    """F_kx,ky for H=kx*sigma_x+ky*sigma_y+m*sigma_z."""
    if branch not in (-1, +1):
        raise ValueError("branch must be +1 or -1")
    kx = np.asarray(kx, dtype=float); ky = np.asarray(ky, dtype=float)
    den = (kx*kx + ky*ky + mass*mass) ** 1.5
    if np.any(den == 0):
        raise ValueError("curvature is singular at the degeneracy")
    return -branch * float(mass) / (2.0 * den)


def anomalous_velocity_y(force_x, omega_z, hbar: float = 1.0):
    """y component of -dot{k} x Omega for F=F_x xhat and Omega=Omega_z zhat."""
    return np.asarray(force_x, dtype=float) * np.asarray(omega_z, dtype=float) / float(hbar)


def polarization_from_zak(gamma, e_magnitude: float = 1.0):
    return -float(e_magnitude) * np.asarray(gamma, dtype=float) / TWO_PI


def pumped_charge_from_chern(chern: int, e_magnitude: float = 1.0):
    return float(e_magnitude) * int(chern)


def berry_phase_discrete(states: np.ndarray) -> float:
    """Gauge-invariant link-product Berry phase for a closed list of normalized states."""
    z = np.asarray(states, dtype=complex)
    if z.ndim != 2 or z.shape[0] < 2:
        raise ValueError("states must be an N x d array")
    norms = np.linalg.norm(z, axis=1)
    if np.any(norms == 0):
        raise ValueError("zero vector is not a state")
    z = z / norms[:, None]
    prod = 1.0 + 0.0j
    for i in range(len(z)):
        ov = np.vdot(z[i], z[(i + 1) % len(z)])
        if abs(ov) < 1e-14:
            raise ValueError("neighboring states are orthogonal")
        prod *= ov / abs(ov)
    return wrap_phase(-np.angle(prod))


def ssh_lower_states(v: float, w: float, n_k: int = 401) -> np.ndarray:
    """Lower-band eigenvectors of H=(v+w cos k)sigma_x+(w sin k)sigma_y."""
    ks = np.linspace(-math.pi, math.pi, int(n_k), endpoint=False)
    out = []
    for k in ks:
        dx = v + w * math.cos(k); dy = w * math.sin(k)
        H = np.array([[0.0, dx - 1j*dy], [dx + 1j*dy, 0.0]], complex)
        _, vecs = np.linalg.eigh(H)
        out.append(vecs[:, 0])
    return np.asarray(out)


def ssh_zak_phase(v: float, w: float, n_k: int = 401) -> float:
    if np.isclose(abs(v), abs(w)):
        raise ValueError("SSH gap closes at |v|=|w|")
    return berry_phase_discrete(ssh_lower_states(v, w, n_k))


def unitary_from_hermitian_connection(A: np.ndarray, length: float = 1.0) -> np.ndarray:
    """Wilson line exp(i A L) for a constant Hermitian connection."""
    A = np.asarray(A, dtype=complex)
    if A.ndim != 2 or A.shape[0] != A.shape[1] or not np.allclose(A, A.conj().T):
        raise ValueError("A must be Hermitian")
    vals, vecs = np.linalg.eigh(A)
    return vecs @ np.diag(np.exp(1j * vals * float(length))) @ vecs.conj().T


def wilson_eigenphases(W: np.ndarray) -> np.ndarray:
    vals = np.linalg.eigvals(np.asarray(W, dtype=complex))
    phases = np.array([wrap_phase(np.angle(v)) for v in vals])
    return np.sort(phases)


def quantum_metric_sphere(theta: float) -> np.ndarray:
    s = math.sin(float(theta))
    return np.array([[0.25, 0.0], [0.0, 0.25*s*s]])


def berry_curvature_sphere(theta: float, branch: int = -1) -> float:
    if branch not in (-1, +1):
        raise ValueError("branch must be +1 or -1")
    return -0.5 * branch * math.sin(float(theta))


def two_level_metric_curvature_residual(theta: float, branch: int = -1) -> float:
    g = quantum_metric_sphere(theta)
    F = berry_curvature_sphere(theta, branch)
    return float(np.linalg.det(g) - 0.25*F*F)


def polarization_pump_branch(t, chern: int = 1):
    """Simple unwrapped polarization branch P/e=C t for one normalized cycle."""
    return int(chern) * np.asarray(t, dtype=float)
