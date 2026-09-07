"""Computational companion for Chapter 44: Topological Bands and the Haldane Model.

The numerical routines keep the chapter conventions explicit:
- honeycomb nearest-neighbour distance a=1,
- reciprocal primitive coordinates (u,v) in [0,1)^2,
- occupied/lower-band Chern number C=+1 for M=0 and t2*sin(phi)>0,
- Hall conductivity sigma_yx = C in units of e^2/h.

The module combines a genuine two-band Haldane bulk solver with controlled continuum
edge/domain-wall diagnostics and finite-size acceptance models used in the text.
"""
from __future__ import annotations
import numpy as np

SQRT3 = np.sqrt(3.0)
TWOPI = 2.0 * np.pi

# Honeycomb nearest-neighbour vectors. Primitive Bravais vectors are a1=delta2-delta1,
# a2=delta3-delta1; the orientation has det[a1,a2] > 0.
DELTA = np.array([
    [0.0, -1.0],
    [SQRT3 / 2.0, 0.5],
    [-SQRT3 / 2.0, 0.5],
])
A1 = DELTA[1] - DELTA[0]
A2 = DELTA[2] - DELTA[0]
A_MATRIX = np.column_stack((A1, A2))
G_MATRIX = TWOPI * np.linalg.inv(A_MATRIX).T
G1 = G_MATRIX[:, 0]
G2 = G_MATRIX[:, 1]
NNN = np.array([
    DELTA[1] - DELTA[2],
    DELTA[2] - DELTA[0],
    DELTA[0] - DELTA[1],
])


def k_cart(u: float, v: float) -> np.ndarray:
    """Map reciprocal primitive coordinates to Cartesian momentum."""
    return G_MATRIX @ np.array([u, v], dtype=float)


def valley_masses(M: float, t2: float, phi: float) -> tuple[float, float]:
    """Return (m_K,m_Kprime) in the Chapter 44 convention."""
    dh = 3.0 * SQRT3 * t2 * np.sin(phi)
    return float(M - dh), float(M + dh)


def chern_from_masses(M: float, t2: float, phi: float, tol: float = 1e-12) -> float:
    """Piecewise occupied-band Chern number; NaN exactly on a valley closing."""
    mK, mKp = valley_masses(M, t2, phi)
    if abs(mK) <= tol or abs(mKp) <= tol:
        return float("nan")
    return float(0.5 * (np.sign(mKp) - np.sign(mK)))


def haldane_d(u: float, v: float, t1: float = 1.0, t2: float = 0.15,
              phi: float = np.pi / 2.0, M: float = 0.0) -> tuple[float, np.ndarray]:
    """Return scalar d0 and vector d for H=d0 I + d.sigma."""
    k = k_cart(u, v)
    f = np.exp(1j * (DELTA @ k)).sum()
    dx = t1 * f.real
    # This sign fixes the reciprocal-orientation convention used throughout Chapter 44.
    dy = t1 * f.imag
    kb = NNN @ k
    d0 = 2.0 * t2 * np.cos(phi) * np.cos(kb).sum()
    dz = M + 2.0 * t2 * np.sin(phi) * np.sin(kb).sum()
    return float(d0), np.array([dx, dy, dz], dtype=float)


def haldane_hamiltonian(u: float, v: float, **params) -> np.ndarray:
    d0, d = haldane_d(u, v, **params)
    dx, dy, dz = d
    return np.array([[d0 + dz, dx - 1j * dy],
                     [dx + 1j * dy, d0 - dz]], dtype=complex)


def band_energies(u: float, v: float, **params) -> np.ndarray:
    return np.linalg.eigvalsh(haldane_hamiltonian(u, v, **params))


def lower_state(u: float, v: float, **params) -> np.ndarray:
    _, vecs = np.linalg.eigh(haldane_hamiltonian(u, v, **params))
    return vecs[:, 0]


def normalized_link(overlap: complex) -> complex:
    if abs(overlap) < 1e-14:
        raise ValueError("singular overlap link")
    return overlap / abs(overlap)


def _gauge_rephase_grid(states: np.ndarray, seed: int | None) -> np.ndarray:
    if seed is None:
        return states
    rng = np.random.default_rng(seed)
    phase = rng.uniform(-np.pi, np.pi, states.shape[:2])
    return states * np.exp(1j * phase)[..., None]


def chern_fukui(n: int = 31, random_gauge_seed: int | None = None, **params) -> float:
    """Gauge-invariant lattice Chern number on the reciprocal primitive torus."""
    if n < 5:
        raise ValueError("mesh too small")
    states = np.empty((n, n, 2), dtype=complex)
    for i in range(n):
        for j in range(n):
            states[i, j] = lower_state(i / n, j / n, **params)
    states = _gauge_rephase_grid(states, random_gauge_seed)
    total = 0.0
    for i in range(n):
        ip = (i + 1) % n
        for j in range(n):
            jp = (j + 1) % n
            u00, u10 = states[i, j], states[ip, j]
            u11, u01 = states[ip, jp], states[i, jp]
            loop = (normalized_link(np.vdot(u00, u10)) *
                    normalized_link(np.vdot(u10, u11)) *
                    normalized_link(np.vdot(u11, u01)) *
                    normalized_link(np.vdot(u01, u00)))
            total += np.angle(loop)
    return float(total / TWOPI)


def berry_curvature_uv(u: float, v: float, du: float = 1e-4, **params) -> float:
    """Lower-band curvature F_uv from the d-hat texture in primitive coordinates."""
    def nh(a, b):
        _, d = haldane_d(a % 1.0, b % 1.0, **params)
        return d / np.linalg.norm(d)
    n0 = nh(u, v)
    d_u = (nh(u + du, v) - nh(u - du, v)) / (2.0 * du)
    d_v = (nh(u, v + du) - nh(u, v - du)) / (2.0 * du)
    # Minus sign matches the occupied-band Chern convention fixed by the link algorithm.
    return float(-0.5 * np.dot(n0, np.cross(d_u, d_v)))


def gap_scan(n: int = 60, **params) -> tuple[float, float]:
    """Return (minimum direct gap, indirect gap) over an n x n reciprocal mesh."""
    min_direct = np.inf
    min_upper = np.inf
    max_lower = -np.inf
    for i in range(n):
        for j in range(n):
            e = band_energies(i / n, j / n, **params)
            min_direct = min(min_direct, e[1] - e[0])
            min_upper = min(min_upper, e[1])
            max_lower = max(max_lower, e[0])
    return float(min_direct), float(min_upper - max_lower)


def edge_dispersion(k, velocity: float = 1.0, chirality: int = 1):
    return chirality * velocity * np.asarray(k, dtype=float)


def edge_crossing_index(velocities) -> int:
    v = np.asarray(velocities, dtype=float)
    return int(np.sum(v > 0) - np.sum(v < 0))


def domain_wall_profile(y, m0: float = 1.0, lam: float = 1.0,
                        hbar_v: float = 1.0) -> np.ndarray:
    """Normalized |psi|^2 for m(y)=m0 tanh(y/lam)."""
    y = np.asarray(y, dtype=float)
    p = abs(m0) * lam / hbar_v
    amp = np.cosh(y / lam) ** (-p)
    prob = amp * amp
    norm = np.trapezoid(prob, y)
    if norm <= 0:
        raise ValueError("invalid normalization grid")
    return prob / norm


def penetration_depth(mass: float, hbar_v: float = 1.0) -> float:
    if mass == 0:
        return float("inf")
    return float(abs(hbar_v / mass))


def finite_width_gap(width, xi: float, gap0: float = 1.0):
    width = np.asarray(width, dtype=float)
    if xi <= 0:
        raise ValueError("xi must be positive")
    return 2.0 * gap0 * np.exp(-width / xi)


def local_marker_profile(x, length: float, C: float = 1.0, xi: float = 1.0):
    """Acceptance-model morphology: interior C plateau with boundary compensation onset.

    This is not a replacement for a projector local-marker calculation. It is a controlled
    finite-size profile used to test windowing and bulk-vs-edge acceptance logic.
    """
    x = np.asarray(x, dtype=float)
    d = np.minimum(x, length - x)
    return C * (1.0 - np.exp(-np.maximum(d, 0.0) / xi))


def hall_sigma_yx(C: float) -> float:
    """Hall conductivity in units e^2/h in the Chapter 44 convention."""
    return float(C)


def hall_sigma_xy(C: float) -> float:
    return -float(C)
