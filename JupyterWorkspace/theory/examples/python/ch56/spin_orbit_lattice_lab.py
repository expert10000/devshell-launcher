"""Commit 616 full spin-orbit lattice-band laboratory for Volume VIII Chapter 56.

The module upgrades the low-energy SOC bridge of Commit 615 to a periodic
Kane--Mele-type lattice Hamiltonian.  It uses the same honeycomb convention as
``two_dimensional_sublattice_lab.py`` and a reciprocal-periodic cell gauge for
Berry/topological calculations.

Conventions
-----------
* Basis for bulk matrices: (A up, A down, B up, B down).
* ``a_nn`` is the nearest-neighbour bond length.
* Intrinsic form factor
      g(k)=2[sin(k.a1)-sin(k.a2)+sin(k.(a2-a1))]
  obeys g(K)=+3 sqrt(3), g(K')=-3 sqrt(3).
* The staggered potential is +Delta on A and -Delta on B.
* Intrinsic SOC is lambda_so g(k) sigma_z s_z.
* The nearest-neighbour Rashba hopping is
      i lambda_r (s x d_hat)_z
  on each A-to-B bond.
* Topological Chern calculations use a cell-periodic Bloch gauge, so wrapping
  across the reciprocal primitive cell is numerically well defined.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np

from two_dimensional_sublattice_lab import honeycomb_geometry, zigzag_ribbon_hamiltonian


SX = np.array([[0.0, 1.0], [1.0, 0.0]], dtype=complex)
SY = np.array([[0.0, -1.0j], [1.0j, 0.0]], dtype=complex)
SZ = np.array([[1.0, 0.0], [0.0, -1.0]], dtype=complex)
S0 = np.eye(2, dtype=complex)
SQRT3 = float(np.sqrt(3.0))


@dataclass(frozen=True)
class RashbaGapPath:
    lambda_r_values: np.ndarray
    gaps: np.ndarray
    minimum_gap: float
    z2_reference: int
    adiabatically_connected: bool


def _finite(x: float, name: str) -> float:
    value = float(x)
    if not np.isfinite(value):
        raise ValueError(f"{name} must be finite")
    return value


def _positive_int(n: int, name: str, minimum: int = 2) -> int:
    if isinstance(n, bool) or int(n) != n or int(n) < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return int(n)


def pauli_spin() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    return SX.copy(), SY.copy(), SZ.copy(), S0.copy()


def intrinsic_form_factor(kx: float, ky: float, a_nn: float = 1.0) -> float:
    g = honeycomb_geometry(a_nn)
    k = np.array([float(kx), float(ky)], dtype=float)
    return float(
        2.0
        * (
            np.sin(np.dot(k, g.a1))
            - np.sin(np.dot(k, g.a2))
            + np.sin(np.dot(k, g.a2 - g.a1))
        )
    )


def cell_structure_factor(kx: float, ky: float, a_nn: float = 1.0) -> complex:
    g = honeycomb_geometry(a_nn)
    k = np.array([float(kx), float(ky)], dtype=float)
    return complex(1.0 + np.exp(-1j * np.dot(k, g.a1)) + np.exp(-1j * np.dot(k, g.a2)))


def rashba_offdiagonal_cell(kx: float, ky: float, lambda_r: float, a_nn: float = 1.0) -> np.ndarray:
    """A-to-B Rashba block in the reciprocal-periodic cell gauge."""
    lr = _finite(lambda_r, "lambda_r")
    g = honeycomb_geometry(a_nn)
    k = np.array([float(kx), float(ky)], dtype=float)
    phases = [1.0 + 0.0j, np.exp(-1j * np.dot(k, g.a1)), np.exp(-1j * np.dot(k, g.a2))]
    block = np.zeros((2, 2), dtype=complex)
    for phase, d in zip(phases, g.delta):
        bond_spin = SX * d[1] - SY * d[0]
        block += 1j * lr * phase * bond_spin / float(a_nn)
    return block


def kane_mele_bloch_hamiltonian(
    kx: float,
    ky: float,
    t: float = 1.0,
    lambda_so: float = 0.06,
    lambda_r: float = 0.0,
    delta: float = 0.0,
    a_nn: float = 1.0,
) -> np.ndarray:
    """Full 4x4 honeycomb spin-orbit Bloch Hamiltonian in a cell gauge."""
    tt = _finite(t, "t")
    lso = _finite(lambda_so, "lambda_so")
    lr = _finite(lambda_r, "lambda_r")
    dd = _finite(delta, "delta")
    f = cell_structure_factor(kx, ky, a_nn)
    gg = intrinsic_form_factor(kx, ky, a_nn)
    off = -tt * f * S0 + rashba_offdiagonal_cell(kx, ky, lr, a_nn)
    a_block = dd * S0 + lso * gg * SZ
    b_block = -dd * S0 - lso * gg * SZ
    return np.block([[a_block, off], [off.conjugate().T, b_block]])


def kane_mele_bands(
    kx: Iterable[float] | float,
    ky: Iterable[float] | float,
    **kwargs,
) -> np.ndarray:
    x, y = np.broadcast_arrays(np.asarray(kx, dtype=float), np.asarray(ky, dtype=float))
    out = []
    for xx, yy in zip(x.ravel(), y.ravel()):
        out.append(np.linalg.eigvalsh(kane_mele_bloch_hamiltonian(xx, yy, **kwargs)))
    return np.asarray(out, dtype=float).reshape(x.shape + (4,))


def valley_mass_table(lambda_so: float = 0.06, delta: float = 0.0) -> dict[str, float]:
    lso = _finite(lambda_so, "lambda_so")
    dd = _finite(delta, "delta")
    m = 3.0 * SQRT3 * lso
    return {
        "K_up": dd + m,
        "K_down": dd - m,
        "Kprime_up": dd - m,
        "Kprime_down": dd + m,
    }


def intrinsic_bulk_gap(lambda_so: float = 0.06, delta: float = 0.0) -> float:
    masses = valley_mass_table(lambda_so, delta)
    return float(2.0 * min(abs(v) for v in masses.values()))


def critical_staggered_mass(lambda_so: float = 0.06) -> float:
    return float(3.0 * SQRT3 * abs(_finite(lambda_so, "lambda_so")))


def spin_block_hamiltonian(
    kx: float,
    ky: float,
    spin: int,
    t: float = 1.0,
    lambda_so: float = 0.06,
    delta: float = 0.0,
    a_nn: float = 1.0,
) -> np.ndarray:
    if isinstance(spin, bool) or int(spin) not in (-1, 1):
        raise ValueError("spin must be +1 or -1")
    tt = _finite(t, "t")
    lso = _finite(lambda_so, "lambda_so")
    dd = _finite(delta, "delta")
    f = cell_structure_factor(kx, ky, a_nn)
    mass = dd + int(spin) * lso * intrinsic_form_factor(kx, ky, a_nn)
    return np.array([[mass, -tt * f], [-tt * np.conjugate(f), -mass]], dtype=complex)


def spin_block_d_vector(
    kx: float,
    ky: float,
    spin: int,
    t: float = 1.0,
    lambda_so: float = 0.06,
    delta: float = 0.0,
    a_nn: float = 1.0,
) -> np.ndarray:
    f = cell_structure_factor(kx, ky, a_nn)
    mass = float(delta) + int(spin) * float(lambda_so) * intrinsic_form_factor(kx, ky, a_nn)
    return np.array([-float(t) * f.real, float(t) * f.imag, mass], dtype=float)


def spin_block_berry_curvature(
    kx: float,
    ky: float,
    spin: int,
    t: float = 1.0,
    lambda_so: float = 0.06,
    delta: float = 0.0,
    a_nn: float = 1.0,
    step: float = 1.0e-5,
) -> float:
    """Lower-band Berry curvature via the d-hat formula and central differences."""
    h = float(step)
    if h <= 0.0:
        raise ValueError("step must be positive")

    def nhat(x: float, y: float) -> np.ndarray:
        d = spin_block_d_vector(x, y, spin, t, lambda_so, delta, a_nn)
        n = float(np.linalg.norm(d))
        if n < 1.0e-13:
            raise ValueError("Berry curvature is singular at a band touching")
        return d / n

    n0 = nhat(kx, ky)
    dx = (nhat(kx + h, ky) - nhat(kx - h, ky)) / (2.0 * h)
    dy = (nhat(kx, ky + h) - nhat(kx, ky - h)) / (2.0 * h)
    return float(-0.5 * np.dot(n0, np.cross(dx, dy)))


def _normalized_overlap(a: np.ndarray, b: np.ndarray) -> complex:
    z = complex(np.vdot(a, b))
    if abs(z) < 1.0e-14:
        raise RuntimeError("vanishing Berry-link overlap")
    return z / abs(z)


def spin_chern_number(
    spin: int,
    mesh: int = 30,
    t: float = 1.0,
    lambda_so: float = 0.06,
    delta: float = 0.0,
    a_nn: float = 1.0,
) -> float:
    """Fukui-Hatsugai-Suzuki Chern number for one conserved-spin block."""
    n = _positive_int(mesh, "mesh", 6)
    g = honeycomb_geometry(a_nn)
    vec = np.empty((n, n, 2), dtype=complex)
    for i in range(n):
        for j in range(n):
            k = (i / n) * g.b1 + (j / n) * g.b2
            _, v = np.linalg.eigh(spin_block_hamiltonian(k[0], k[1], spin, t, lambda_so, delta, a_nn))
            vec[i, j] = v[:, 0]

    flux = 0.0
    for i in range(n):
        for j in range(n):
            u = vec[i, j]
            ux = vec[(i + 1) % n, j]
            uy = vec[i, (j + 1) % n]
            uxy = vec[(i + 1) % n, (j + 1) % n]
            loop = (
                _normalized_overlap(u, ux)
                * _normalized_overlap(ux, uxy)
                / (_normalized_overlap(uy, uxy) * _normalized_overlap(u, uy))
            )
            flux += float(np.angle(loop))
    return float(flux / (2.0 * np.pi))


def spin_chern_pair(mesh: int = 30, **kwargs) -> tuple[float, float]:
    return spin_chern_number(+1, mesh=mesh, **kwargs), spin_chern_number(-1, mesh=mesh, **kwargs)


def z2_spin_conserving(mesh: int = 30, **kwargs) -> int:
    cup, _ = spin_chern_pair(mesh=mesh, **kwargs)
    return int(abs(int(round(cup))) % 2)


def phase_from_masses(lambda_so: float = 0.06, delta: float = 0.0) -> str:
    dc = critical_staggered_mass(lambda_so)
    ad = abs(float(delta))
    if np.isclose(ad, dc, rtol=0.0, atol=1.0e-12):
        return "critical"
    return "topological" if ad < dc else "trivial"


def bulk_time_reversal_error(kx: float, ky: float, **kwargs) -> float:
    u = np.kron(np.eye(2, dtype=complex), 1j * SY)
    hp = kane_mele_bloch_hamiltonian(kx, ky, **kwargs)
    hm = kane_mele_bloch_hamiltonian(-kx, -ky, **kwargs)
    return float(np.max(np.abs(u @ hp.conjugate() @ u.conjugate().T - hm)))


def spin_conservation_commutator_norm(kx: float, ky: float, **kwargs) -> float:
    h = kane_mele_bloch_hamiltonian(kx, ky, **kwargs)
    sz4 = np.kron(np.eye(2, dtype=complex), SZ)
    return float(np.linalg.norm(h @ sz4 - sz4 @ h))


def minimum_direct_gap(
    mesh: int = 30,
    t: float = 1.0,
    lambda_so: float = 0.06,
    lambda_r: float = 0.0,
    delta: float = 0.0,
    a_nn: float = 1.0,
) -> float:
    n = _positive_int(mesh, "mesh", 6)
    g = honeycomb_geometry(a_nn)
    gap = np.inf
    for i in range(n):
        for j in range(n):
            k = (i / n) * g.b1 + (j / n) * g.b2
            e = np.linalg.eigvalsh(kane_mele_bloch_hamiltonian(k[0], k[1], t, lambda_so, lambda_r, delta, a_nn))
            gap = min(gap, float(e[2] - e[1]))
    return float(gap)


def occupied_subspace_chern(
    mesh: int = 18,
    t: float = 1.0,
    lambda_so: float = 0.06,
    lambda_r: float = 0.0,
    delta: float = 0.0,
    a_nn: float = 1.0,
) -> float:
    """Non-Abelian Chern number of the two occupied bands."""
    n = _positive_int(mesh, "mesh", 6)
    g = honeycomb_geometry(a_nn)
    occ = np.empty((n, n, 4, 2), dtype=complex)
    for i in range(n):
        for j in range(n):
            k = (i / n) * g.b1 + (j / n) * g.b2
            _, v = np.linalg.eigh(kane_mele_bloch_hamiltonian(k[0], k[1], t, lambda_so, lambda_r, delta, a_nn))
            occ[i, j] = v[:, :2]

    def link(a: np.ndarray, b: np.ndarray) -> complex:
        det = complex(np.linalg.det(a.conjugate().T @ b))
        if abs(det) < 1.0e-13:
            raise RuntimeError("singular occupied-subspace Berry link")
        return det / abs(det)

    total = 0.0
    for i in range(n):
        for j in range(n):
            u = occ[i, j]
            ux = occ[(i + 1) % n, j]
            uy = occ[i, (j + 1) % n]
            uxy = occ[(i + 1) % n, (j + 1) % n]
            loop = link(u, ux) * link(ux, uxy) / (link(uy, uxy) * link(u, uy))
            total += float(np.angle(loop))
    return float(total / (2.0 * np.pi))


def adiabatic_rashba_gap_path(
    lambda_r_target: float,
    steps: int = 5,
    mesh: int = 30,
    t: float = 1.0,
    lambda_so: float = 0.06,
    delta: float = 0.0,
    a_nn: float = 1.0,
) -> RashbaGapPath:
    nstep = _positive_int(steps, "steps", 2)
    target = abs(_finite(lambda_r_target, "lambda_r_target"))
    values = np.linspace(0.0, target, nstep)
    gaps = np.array(
        [minimum_direct_gap(mesh, t, lambda_so, lr, delta, a_nn) for lr in values],
        dtype=float,
    )
    z2 = z2_spin_conserving(mesh=mesh, t=t, lambda_so=lambda_so, delta=delta, a_nn=a_nn)
    minimum = float(np.min(gaps))
    return RashbaGapPath(values, gaps, minimum, z2, bool(minimum > 1.0e-6))


def spinful_zigzag_ribbon_hamiltonian(
    q: float,
    width: int,
    t: float = 1.0,
    lambda_so: float = 0.06,
    lambda_r: float = 0.0,
    delta: float = 0.0,
    a_nn: float = 1.0,
) -> np.ndarray:
    """Spinful zigzag strip, periodic along a1 and finite along a2.

    The construction is real-space exact for the chosen cell convention and
    reproduces the Commit-615 spinless ribbon spectrum twice when both SOC
    couplings vanish.
    """
    n = _positive_int(width, "width", 2)
    tt = _finite(t, "t")
    lso = _finite(lambda_so, "lambda_so")
    lr = _finite(lambda_r, "lambda_r")
    dd = _finite(delta, "delta")
    aa = float(a_nn)
    geom = honeycomb_geometry(aa)
    h = np.zeros((4 * n, 4 * n), dtype=complex)

    def sl(row: int, sub: int) -> slice:
        base = 4 * row + 2 * sub
        return slice(base, base + 2)

    for row in range(n):
        h[sl(row, 0), sl(row, 0)] += dd * S0
        h[sl(row, 1), sl(row, 1)] += -dd * S0

    # A(row) -> B(row+dm2); dm1 carries the longitudinal Bloch phase.
    neighbors = [(0, 0, geom.delta[0]), (-1, 0, geom.delta[1]), (0, -1, geom.delta[2])]
    for row in range(n):
        ia = sl(row, 0)
        for dm1, dm2, dvec in neighbors:
            other = row + dm2
            if not (0 <= other < n):
                continue
            jb = sl(other, 1)
            phase = np.exp(1j * float(q) * dm1)
            rashba = 1j * lr * (SX * dvec[1] - SY * dvec[0]) / aa
            mat = phase * (-tt * S0 + rashba)
            h[ia, jb] += mat
            h[jb, ia] += mat.conjugate().T

    # Positive NNN displacements a1, a2, a2-a1 with coefficients matching g(k).
    nnn = [(1, 0, +1.0), (0, 1, -1.0), (-1, 1, +1.0)]
    for sub in (0, 1):
        sub_sign = +1.0 if sub == 0 else -1.0
        for row in range(n):
            ii = sl(row, sub)
            for dm1, dm2, coeff in nnn:
                other = row + dm2
                if not (0 <= other < n):
                    continue
                jj = sl(other, sub)
                phase = np.exp(1j * float(q) * dm1)
                mat = phase * (-1j * lso * coeff * sub_sign) * SZ
                h[ii, jj] += mat
                h[jj, ii] += mat.conjugate().T
    return h


def spinful_ribbon_spectrum(q: Iterable[float] | float, width: int, **kwargs) -> np.ndarray:
    qq = np.asarray(q, dtype=float)
    vals = [np.linalg.eigvalsh(spinful_zigzag_ribbon_hamiltonian(x, width, **kwargs)) for x in qq.ravel()]
    return np.asarray(vals, dtype=float).reshape(qq.shape + (4 * int(width),))


def spinful_ribbon_time_reversal_error(q: float, width: int, **kwargs) -> float:
    hq = spinful_zigzag_ribbon_hamiltonian(q, width, **kwargs)
    hm = spinful_zigzag_ribbon_hamiltonian(-q, width, **kwargs)
    u = np.kron(np.eye(2 * int(width), dtype=complex), 1j * SY)
    return float(np.max(np.abs(u @ hq.conjugate() @ u.conjugate().T - hm)))


def kramers_pair_splitting(q: float, width: int, **kwargs) -> float:
    e = np.linalg.eigvalsh(spinful_zigzag_ribbon_hamiltonian(q, width, **kwargs))
    pairs = np.abs(e[0::2] - e[1::2])
    return float(np.max(pairs))


def spinful_edge_weight(vector: np.ndarray, width: int, edge_rows: int = 1) -> float:
    n = _positive_int(width, "width", 2)
    er = _positive_int(edge_rows, "edge_rows", 1)
    if 2 * er > n:
        raise ValueError("edge_rows is too large for width")
    v = np.asarray(vector, dtype=complex).reshape(-1)
    if v.size != 4 * n:
        raise ValueError("vector size does not match ribbon width")
    p = np.abs(v) ** 2
    norm = float(np.sum(p))
    if norm <= 0.0:
        raise ValueError("zero vector")
    count = 4 * er
    return float((np.sum(p[:count]) + np.sum(p[-count:])) / norm)


def spin_z_expectation(vector: np.ndarray, width: int) -> float:
    n = _positive_int(width, "width", 2)
    v = np.asarray(vector, dtype=complex).reshape(-1)
    if v.size != 4 * n:
        raise ValueError("vector size does not match ribbon width")
    op = np.kron(np.eye(2 * n, dtype=complex), SZ)
    norm = float(np.real(np.vdot(v, v)))
    if norm <= 0.0:
        raise ValueError("zero vector")
    return float(np.real(np.vdot(v, op @ v)) / norm)


def edge_state_summary(q: float, width: int = 24, count: int = 4, **kwargs) -> dict[str, object]:
    n = _positive_int(width, "width", 2)
    c = _positive_int(count, "count", 1)
    h = spinful_zigzag_ribbon_hamiltonian(q, n, **kwargs)
    e, v = np.linalg.eigh(h)
    weights = np.array([spinful_edge_weight(v[:, j], n) for j in range(v.shape[1])])
    order = np.argsort(-weights)[:c]
    return {
        "energies": [float(e[j]) for j in order],
        "edge_weights": [float(weights[j]) for j in order],
        "spin_z": [float(spin_z_expectation(v[:, j], n)) for j in order],
        "min_edge_weight": float(np.min(weights[order])),
        "mean_edge_weight": float(np.mean(weights[order])),
    }


def reference_summary() -> dict[str, object]:
    geom = honeycomb_geometry(1.0)
    top = spin_chern_pair(mesh=30, lambda_so=0.06, delta=0.0)
    trivial = spin_chern_pair(mesh=30, lambda_so=0.06, delta=0.40)
    path = adiabatic_rashba_gap_path(0.04, steps=4, mesh=30, lambda_so=0.06, delta=0.0)
    edge = edge_state_summary(np.pi - 0.15, width=24, lambda_so=0.06, lambda_r=0.02, delta=0.0)
    return {
        "gK": intrinsic_form_factor(*geom.k),
        "intrinsic_gap": intrinsic_bulk_gap(0.06, 0.0),
        "topological_spin_chern": [float(top[0]), float(top[1])],
        "trivial_spin_chern": [float(trivial[0]), float(trivial[1])],
        "rashba_path_min_gap": path.minimum_gap,
        "rashba_path_z2_reference": path.z2_reference,
        "edge_reference": edge,
    }
