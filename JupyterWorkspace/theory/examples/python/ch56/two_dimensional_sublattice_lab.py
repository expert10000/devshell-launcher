"""Commit 615 two-dimensional sublattice laboratory for Volume VIII Chapter 56.

Conventions
-----------
* ``a_nn`` is the nearest-neighbour bond length.
* Honeycomb nearest-neighbour vectors are
  d1=a_nn(0,1), d2=a_nn(-sqrt(3)/2,-1/2), d3=a_nn(sqrt(3)/2,-1/2).
* Primitive Bravais vectors are a1=d1-d2 and a2=d1-d3.
* Nearest-neighbour graphene uses H(k)=[[Delta,-t f(k)],[-t f*(k),-Delta]].
* The zigzag ribbon uses a dimensionless longitudinal momentum q in [-pi,pi]
  and is equivalent, for each q, to an SSH-like transverse chain with
  intra-row amplitude 2 t cos(q/2) and inter-row amplitude t.
* The spin-orbit bridge is the low-energy spinful Dirac Hamiltonian near valley
  tau=+1 (K) or tau=-1 (K').  It is a bridge to the full lattice Kane--Mele
  model, not a replacement for it.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np


SQRT3 = float(np.sqrt(3.0))


@dataclass(frozen=True)
class HoneycombGeometry:
    delta: np.ndarray
    a1: np.ndarray
    a2: np.ndarray
    b1: np.ndarray
    b2: np.ndarray
    gamma: np.ndarray
    k: np.ndarray
    kp: np.ndarray
    m: np.ndarray


def _positive(value: float, name: str) -> float:
    x = float(value)
    if not np.isfinite(x) or x <= 0.0:
        raise ValueError(f"{name} must be positive and finite")
    return x


def _valley(tau: int) -> int:
    if isinstance(tau, bool) or int(tau) not in (-1, 1):
        raise ValueError("tau must be +1 or -1")
    return int(tau)


def honeycomb_geometry(a_nn: float = 1.0) -> HoneycombGeometry:
    a = _positive(a_nn, "a_nn")
    delta = a * np.array(
        [[0.0, 1.0], [-SQRT3 / 2.0, -0.5], [SQRT3 / 2.0, -0.5]],
        dtype=float,
    )
    a1 = delta[0] - delta[1]
    a2 = delta[0] - delta[2]
    amat = np.column_stack([a1, a2])
    bmat = 2.0 * np.pi * np.linalg.inv(amat).T
    b1 = bmat[:, 0]
    b2 = bmat[:, 1]
    gamma = np.zeros(2, dtype=float)
    k = np.array([4.0 * np.pi / (3.0 * SQRT3 * a), 0.0], dtype=float)
    kp = -k
    m = 0.5 * (b1 + b2)
    return HoneycombGeometry(delta, a1, a2, b1, b2, gamma, k, kp, m)


def reciprocal_dot_matrix(a_nn: float = 1.0) -> np.ndarray:
    g = honeycomb_geometry(a_nn)
    return np.array(
        [[np.dot(g.a1, g.b1), np.dot(g.a1, g.b2)],
         [np.dot(g.a2, g.b1), np.dot(g.a2, g.b2)]],
        dtype=float,
    )


def graphene_structure_factor(kx: float, ky: float, a_nn: float = 1.0) -> complex:
    g = honeycomb_geometry(a_nn)
    k = np.array([float(kx), float(ky)], dtype=float)
    return complex(np.sum(np.exp(1j * (g.delta @ k))))


def graphene_bloch_hamiltonian(
    kx: float,
    ky: float,
    t: float = 1.0,
    delta: float = 0.0,
    a_nn: float = 1.0,
) -> np.ndarray:
    f = graphene_structure_factor(kx, ky, a_nn)
    tt = float(t)
    dd = float(delta)
    if not np.isfinite(tt) or not np.isfinite(dd):
        raise ValueError("t and delta must be finite")
    return np.array([[dd, -tt * f], [-tt * np.conjugate(f), -dd]], dtype=complex)


def graphene_bands(
    kx: Iterable[float] | float,
    ky: Iterable[float] | float,
    t: float = 1.0,
    delta: float = 0.0,
    a_nn: float = 1.0,
) -> np.ndarray:
    x, y = np.broadcast_arrays(np.asarray(kx, dtype=float), np.asarray(ky, dtype=float))
    flat = []
    for xx, yy in zip(x.ravel(), y.ravel()):
        flat.append(np.linalg.eigvalsh(graphene_bloch_hamiltonian(xx, yy, t, delta, a_nn)))
    return np.asarray(flat, dtype=float).reshape(x.shape + (2,))


def graphene_band_gap(delta: float = 0.0) -> float:
    return 2.0 * abs(float(delta))


def graphene_d_vector(kx: float, ky: float, t: float = 1.0, delta: float = 0.0, a_nn: float = 1.0) -> np.ndarray:
    f = graphene_structure_factor(kx, ky, a_nn)
    tt = float(t)
    return np.array([-tt * f.real, tt * f.imag, float(delta)], dtype=float)


def pseudospin_direction(kx: float, ky: float, t: float = 1.0, delta: float = 0.0, a_nn: float = 1.0) -> np.ndarray:
    d = graphene_d_vector(kx, ky, t, delta, a_nn)
    n = float(np.linalg.norm(d))
    if n < 1.0e-14:
        raise ValueError("pseudospin direction is undefined at a band touching")
    return d / n


def fermi_velocity(t: float = 1.0, a_nn: float = 1.0, hbar: float = 1.0) -> float:
    aa = _positive(a_nn, "a_nn")
    hh = _positive(hbar, "hbar")
    return 1.5 * abs(float(t)) * aa / hh


def dirac_hamiltonian(
    qx: float,
    qy: float,
    tau: int = 1,
    t: float = 1.0,
    delta: float = 0.0,
    a_nn: float = 1.0,
) -> np.ndarray:
    """Linearized two-band Hamiltonian in energy units with hbar=1.

    The phase convention is chosen to match the exact lattice Hamiltonian near
    K_tau after a fixed sublattice gauge rotation.  Spectra and pseudospin
    winding are gauge invariant.
    """
    tv = _valley(tau)
    v = fermi_velocity(t=t, a_nn=a_nn, hbar=1.0)
    qx = float(qx)
    qy = float(qy)
    dd = float(delta)
    return np.array(
        [[dd, v * (tv * qx - 1j * qy)], [v * (tv * qx + 1j * qy), -dd]],
        dtype=complex,
    )


def lattice_dirac_spectrum_error(
    radius: float,
    samples: int = 120,
    t: float = 1.0,
    a_nn: float = 1.0,
) -> float:
    rr = _positive(radius, "radius")
    if int(samples) < 8:
        raise ValueError("samples must be at least 8")
    g = honeycomb_geometry(a_nn)
    v = fermi_velocity(t, a_nn, 1.0)
    errs = []
    for th in np.linspace(0.0, 2.0 * np.pi, int(samples), endpoint=False):
        q = rr * np.array([np.cos(th), np.sin(th)])
        exact = np.max(np.abs(graphene_bands(g.k[0] + q[0], g.k[1] + q[1], t, 0.0, a_nn)))
        linear = v * rr
        errs.append(abs(exact - linear))
    return float(max(errs))


def pseudospin_winding(
    center: Iterable[float],
    radius: float,
    samples: int = 721,
    t: float = 1.0,
    a_nn: float = 1.0,
) -> float:
    c = np.asarray(list(center), dtype=float)
    if c.shape != (2,):
        raise ValueError("center must contain two coordinates")
    rr = _positive(radius, "radius")
    if int(samples) < 16:
        raise ValueError("samples must be at least 16")
    angles = np.linspace(0.0, 2.0 * np.pi, int(samples), endpoint=True)
    phases = []
    for th in angles:
        k = c + rr * np.array([np.cos(th), np.sin(th)])
        d = graphene_d_vector(k[0], k[1], t=t, delta=0.0, a_nn=a_nn)
        phases.append(np.arctan2(d[1], d[0]))
    unwrapped = np.unwrap(np.asarray(phases))
    return float((unwrapped[-1] - unwrapped[0]) / (2.0 * np.pi))


def berry_phase_from_winding(winding: float) -> float:
    """Massless two-band Berry phase modulo 2pi in the pseudospin convention."""
    return float(np.pi * float(winding))


def zigzag_ribbon_hamiltonian(
    q: float,
    width: int,
    t: float = 1.0,
    delta: float = 0.0,
) -> np.ndarray:
    """Zigzag graphene ribbon block Hamiltonian at longitudinal q.

    Basis is A0,B0,A1,B1,... across the ribbon.  The q-dependent coupling
    A_n--B_n is -2t cos(q/2), while B_n--A_{n+1} is -t.
    """
    if isinstance(width, bool) or int(width) != width or int(width) < 2:
        raise ValueError("width must be an integer >= 2")
    n = int(width)
    tt = float(t)
    dd = float(delta)
    g = 2.0 * np.cos(float(q) / 2.0)
    h = np.zeros((2 * n, 2 * n), dtype=complex)
    for row in range(n):
        a = 2 * row
        b = a + 1
        h[a, a] = dd
        h[b, b] = -dd
        h[a, b] = h[b, a] = -tt * g
        if row < n - 1:
            an = 2 * (row + 1)
            h[b, an] = h[an, b] = -tt
    return h


def zigzag_ribbon_spectrum(q: Iterable[float] | float, width: int, t: float = 1.0, delta: float = 0.0) -> np.ndarray:
    qq = np.asarray(q, dtype=float)
    vals = [np.linalg.eigvalsh(zigzag_ribbon_hamiltonian(x, width, t, delta)) for x in qq.ravel()]
    return np.asarray(vals).reshape(qq.shape + (2 * int(width),))


def edge_weight(vector: np.ndarray, width: int, edge_rows: int = 1) -> float:
    v = np.asarray(vector, dtype=complex).reshape(-1)
    n = int(width)
    er = int(edge_rows)
    if v.size != 2 * n or er < 1 or 2 * er > n:
        raise ValueError("vector/width/edge_rows mismatch")
    prob = np.abs(v) ** 2
    norm = float(np.sum(prob))
    if norm <= 0.0:
        raise ValueError("zero vector")
    idx = list(range(2 * er)) + list(range(2 * (n - er), 2 * n))
    return float(np.sum(prob[idx]) / norm)


def ribbon_near_zero_states(q: float, width: int, t: float = 1.0, delta: float = 0.0, count: int = 2):
    h = zigzag_ribbon_hamiltonian(q, width, t, delta)
    e, u = np.linalg.eigh(h)
    order = np.argsort(np.abs(e))[: int(count)]
    return e[order], u[:, order]


def ribbon_edge_state_summary(q: float, width: int, t: float = 1.0, delta: float = 0.0, edge_rows: int = 1) -> dict[str, float]:
    e, u = ribbon_near_zero_states(q, width, t, delta, count=2)
    weights = [edge_weight(u[:, i], width, edge_rows) for i in range(u.shape[1])]
    return {
        "max_abs_energy": float(np.max(np.abs(e))),
        "min_edge_weight": float(np.min(weights)),
        "mean_edge_weight": float(np.mean(weights)),
    }


def pauli_matrices() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    s0 = np.eye(2, dtype=complex)
    sx = np.array([[0, 1], [1, 0]], dtype=complex)
    sy = np.array([[0, -1j], [1j, 0]], dtype=complex)
    sz = np.array([[1, 0], [0, -1]], dtype=complex)
    return s0, sx, sy, sz


def spinful_dirac_hamiltonian(
    qx: float,
    qy: float,
    tau: int = 1,
    t: float = 1.0,
    a_nn: float = 1.0,
    delta: float = 0.0,
    lambda_so: float = 0.0,
    lambda_r: float = 0.0,
) -> np.ndarray:
    """Low-energy 4x4 sublattice x spin bridge toward Kane--Mele bands."""
    tv = _valley(tau)
    v = fermi_velocity(t, a_nn, 1.0)
    s0, sx, sy, sz = pauli_matrices()
    # sigma matrices reuse the same representation; kron order is sublattice x spin.
    sigma0, sigmax, sigmay, sigmaz = s0, sx, sy, sz
    hkin = v * (tv * float(qx) * np.kron(sigmax, s0) + float(qy) * np.kron(sigmay, s0))
    hsub = float(delta) * np.kron(sigmaz, s0)
    hint = tv * float(lambda_so) * np.kron(sigmaz, sz)
    hr = float(lambda_r) * (tv * np.kron(sigmax, sy) - np.kron(sigmay, sx))
    return hkin + hsub + hint + hr


def intrinsic_soc_dirac_gap(lambda_so: float, delta: float = 0.0, tau: int = 1) -> float:
    tv = _valley(tau)
    masses = [float(delta) + tv * float(lambda_so), float(delta) - tv * float(lambda_so)]
    return 2.0 * min(abs(x) for x in masses)


def time_reversal_matrix_spin() -> np.ndarray:
    """Unitary part U_T of T=(I_sigma x i s_y) K."""
    s0, _, sy, _ = pauli_matrices()
    return np.kron(s0, 1j * sy)


def spinful_time_reversal_error(
    qx: float,
    qy: float,
    t: float = 1.0,
    a_nn: float = 1.0,
    delta: float = 0.0,
    lambda_so: float = 0.0,
    lambda_r: float = 0.0,
) -> float:
    """Check U_T H_K(q)^* U_T^dag = H_K'(-q)."""
    u = time_reversal_matrix_spin()
    hp = spinful_dirac_hamiltonian(qx, qy, +1, t, a_nn, delta, lambda_so, lambda_r)
    hm = spinful_dirac_hamiltonian(-qx, -qy, -1, t, a_nn, delta, lambda_so, lambda_r)
    mapped = u @ hp.conjugate() @ u.conjugate().T
    return float(np.max(np.abs(mapped - hm)))
