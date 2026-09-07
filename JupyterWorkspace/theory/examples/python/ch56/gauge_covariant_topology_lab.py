"""Commit 617 gauge-covariant occupied-subspace topology laboratory.

This module extends the spin-orbit lattice work of Commit 616 from diagnostics
that use a conserved-spin reference to topology of the *occupied subspace*
itself.  The primary objects are projectors, unitary parallel-transport links,
Wilson loops, hybrid-Wannier centers, and a two-occupied-band Z2 partner-switch
index that remains meaningful when Rashba coupling mixes spin.

Coordinates
-----------
We use reciprocal fractional coordinates

    k(u,v) = u b1 + v b2,

where b1,b2 are the honeycomb reciprocal primitive vectors.  The Commit-616
cell-gauge Hamiltonian is periodic under u->u+1 and v->v+1.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from itertools import permutations
from typing import Iterable

import numpy as np

from spin_orbit_lattice_lab import (
    honeycomb_geometry,
    kane_mele_bloch_hamiltonian,
    minimum_direct_gap,
    spinful_edge_weight,
    spinful_zigzag_ribbon_hamiltonian,
    z2_spin_conserving,
)


@dataclass(frozen=True)
class WilsonFlow:
    transverse: np.ndarray
    centers: np.ndarray
    unwrapped: np.ndarray
    relative_winding: int
    z2: int
    endpoint_splitting: tuple[float, float]


@dataclass(frozen=True)
class ProjectorGeometry:
    metric: np.ndarray
    curvature: float
    projector: np.ndarray


@dataclass(frozen=True)
class BulkEdgeSummary:
    z2: int
    bulk_gap: float
    ribbon_min_abs_energy: float
    ribbon_min_edge_weight: float
    edge_crossing_present: bool


def _positive_int(n: int, name: str, minimum: int = 2) -> int:
    if isinstance(n, bool) or int(n) != n or int(n) < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return int(n)


def reciprocal_k(u: float, v: float, a_nn: float = 1.0) -> np.ndarray:
    g = honeycomb_geometry(float(a_nn))
    return float(u) * g.b1 + float(v) * g.b2


def occupied_frame_fractional(
    u: float,
    v: float,
    t: float = 1.0,
    lambda_so: float = 0.06,
    lambda_r: float = 0.04,
    delta: float = 0.0,
    a_nn: float = 1.0,
) -> np.ndarray:
    k = reciprocal_k(u, v, a_nn)
    _, vec = np.linalg.eigh(
        kane_mele_bloch_hamiltonian(
            k[0], k[1], t=t, lambda_so=lambda_so, lambda_r=lambda_r, delta=delta, a_nn=a_nn
        )
    )
    return np.asarray(vec[:, :2], dtype=complex)


def occupied_projector_fractional(u: float, v: float, **kwargs) -> np.ndarray:
    frame = occupied_frame_fractional(u, v, **kwargs)
    return frame @ frame.conjugate().T


def projector_residuals(u: float, v: float, **kwargs) -> dict[str, float]:
    p = occupied_projector_fractional(u, v, **kwargs)
    return {
        "hermiticity": float(np.linalg.norm(p - p.conjugate().T)),
        "idempotency": float(np.linalg.norm(p @ p - p)),
        "trace_error": float(abs(np.trace(p) - 2.0)),
    }


def unitary_part(matrix: np.ndarray) -> np.ndarray:
    m = np.asarray(matrix, dtype=complex)
    if m.ndim != 2 or m.shape[0] != m.shape[1]:
        raise ValueError("matrix must be square")
    u, singular, vh = np.linalg.svd(m)
    if float(np.min(singular)) < 1.0e-13:
        raise RuntimeError("singular occupied-subspace overlap")
    return u @ vh


def _frames_on_loop(v: float, loop_points: int, **kwargs) -> list[np.ndarray]:
    n = _positive_int(loop_points, "loop_points", 8)
    return [occupied_frame_fractional(j / n, float(v), **kwargs) for j in range(n)]


def wilson_loop_from_frames(frames: Iterable[np.ndarray]) -> np.ndarray:
    fs = [np.asarray(f, dtype=complex) for f in frames]
    if len(fs) < 3:
        raise ValueError("at least three frames are required")
    rank = fs[0].shape[1]
    if any(f.ndim != 2 or f.shape[1] != rank for f in fs):
        raise ValueError("all frames must have the same occupied rank")
    w = np.eye(rank, dtype=complex)
    for j in range(len(fs)):
        overlap = fs[j].conjugate().T @ fs[(j + 1) % len(fs)]
        w = w @ unitary_part(overlap)
    return w


def wilson_loop_matrix(v: float, loop_points: int = 72, **kwargs) -> np.ndarray:
    return wilson_loop_from_frames(_frames_on_loop(v, loop_points, **kwargs))


def _centers_from_wilson(w: np.ndarray) -> np.ndarray:
    eig = np.linalg.eigvals(np.asarray(w, dtype=complex))
    phases = np.mod(np.angle(eig) / (2.0 * np.pi), 1.0)
    return np.sort(np.asarray(phases, dtype=float))


def wilson_loop_centers(v: float, loop_points: int = 72, **kwargs) -> np.ndarray:
    return _centers_from_wilson(wilson_loop_matrix(v, loop_points=loop_points, **kwargs))


def _circular_separation(x: float, y: float) -> float:
    d = abs(float(x) - float(y)) % 1.0
    return float(min(d, 1.0 - d))


def _circular_mean(values: np.ndarray) -> float:
    z = np.mean(np.exp(2.0j * np.pi * np.asarray(values, dtype=float)))
    if abs(z) < 1.0e-14:
        return 0.0
    return float(np.mod(np.angle(z) / (2.0 * np.pi), 1.0))


def _track_two_center_flow(raw: np.ndarray) -> tuple[np.ndarray, int, tuple[float, float]]:
    centers = np.asarray(raw, dtype=float).copy()
    if centers.ndim != 2 or centers.shape[1] != 2:
        raise ValueError("two occupied Wilson-loop centers are required")

    split0 = _circular_separation(*centers[0])
    split1 = _circular_separation(*centers[-1])
    # At a time-reversal invariant transverse line the pair should be Kramers
    # degenerate.  Replacing tiny 0/1 numerical representations by their circle
    # mean avoids an artificial unit jump in the unwrapping.
    for idx in (0, -1):
        if _circular_separation(*centers[idx]) < 5.0e-4:
            c = _circular_mean(centers[idx])
            centers[idx] = (c, c)

    unwrapped = np.empty_like(centers)
    unwrapped[0] = centers[0]
    for i in range(1, centers.shape[0]):
        candidates = []
        for perm in permutations((0, 1)):
            vals = centers[i, list(perm)]
            lifted = np.array(
                [vals[j] + round(unwrapped[i - 1, j] - vals[j]) for j in range(2)],
                dtype=float,
            )
            cost = float(np.sum((lifted - unwrapped[i - 1]) ** 2))
            candidates.append((cost, perm, lifted))
        candidates.sort(key=lambda x: (x[0], x[1]))
        unwrapped[i] = candidates[0][2]

    disp = unwrapped[-1] - unwrapped[0]
    relative = int(round(float(disp[0] - disp[1])))
    return unwrapped, relative, (split0, split1)


def wilson_loop_flow(
    transverse_points: int = 41,
    loop_points: int = 72,
    t: float = 1.0,
    lambda_so: float = 0.06,
    lambda_r: float = 0.04,
    delta: float = 0.0,
    a_nn: float = 1.0,
) -> WilsonFlow:
    nv = _positive_int(transverse_points, "transverse_points", 9)
    vs = np.linspace(0.0, 0.5, nv)
    raw = np.array(
        [
            wilson_loop_centers(
                v,
                loop_points=loop_points,
                t=t,
                lambda_so=lambda_so,
                lambda_r=lambda_r,
                delta=delta,
                a_nn=a_nn,
            )
            for v in vs
        ],
        dtype=float,
    )
    unwrapped, relative, endpoint = _track_two_center_flow(raw)
    return WilsonFlow(vs, raw, unwrapped, relative, abs(relative) % 2, endpoint)


def z2_wilson_loop(**kwargs) -> int:
    return int(wilson_loop_flow(**kwargs).z2)


def _random_unitary(rank: int, rng: np.random.Generator) -> np.ndarray:
    z = rng.normal(size=(rank, rank)) + 1j * rng.normal(size=(rank, rank))
    q, r = np.linalg.qr(z)
    phase = np.diag(r)
    phase = np.where(np.abs(phase) > 0, phase / np.abs(phase), 1.0)
    return q @ np.diag(np.conjugate(phase))


def wilson_loop_gauge_invariance_error(
    v: float = 0.37,
    loop_points: int = 48,
    seed: int = 617,
    **kwargs,
) -> float:
    frames = _frames_on_loop(v, loop_points, **kwargs)
    w0 = wilson_loop_from_frames(frames)
    rng = np.random.default_rng(int(seed))
    rotated = [f @ _random_unitary(f.shape[1], rng) for f in frames]
    w1 = wilson_loop_from_frames(rotated)
    e0 = np.linalg.eigvals(w0)
    e1 = np.linalg.eigvals(w1)
    # Match the unordered eigenvalue sets explicitly.
    errs = []
    for perm in permutations(range(len(e1))):
        errs.append(max(abs(e0[j] - e1[perm[j]]) for j in range(len(e0))))
    return float(min(errs))


def projector_geometry(
    u: float,
    v: float,
    step: float = 2.0e-4,
    **kwargs,
) -> ProjectorGeometry:
    h = float(step)
    if h <= 0.0:
        raise ValueError("step must be positive")

    def p(x: float, y: float) -> np.ndarray:
        return occupied_projector_fractional(x % 1.0, y % 1.0, **kwargs)

    p0 = p(u, v)
    du = (p(u + h, v) - p(u - h, v)) / (2.0 * h)
    dv = (p(u, v + h) - p(u, v - h)) / (2.0 * h)
    metric = np.array(
        [
            [0.5 * np.trace(du @ du).real, 0.5 * np.trace(du @ dv).real],
            [0.5 * np.trace(dv @ du).real, 0.5 * np.trace(dv @ dv).real],
        ],
        dtype=float,
    )
    comm = du @ dv - dv @ du
    curvature = float(np.real(-1j * np.trace(p0 @ comm)))
    return ProjectorGeometry(metric=metric, curvature=curvature, projector=p0)


def subspace_chordal_distance(u1: float, v1: float, u2: float, v2: float, **kwargs) -> float:
    p = occupied_projector_fractional(u1, v1, **kwargs)
    q = occupied_projector_fractional(u2, v2, **kwargs)
    return float(np.linalg.norm(p - q) / np.sqrt(2.0))


def principal_overlap_singular_values(u1: float, v1: float, u2: float, v2: float, **kwargs) -> np.ndarray:
    a = occupied_frame_fractional(u1, v1, **kwargs)
    b = occupied_frame_fractional(u2, v2, **kwargs)
    return np.linalg.svd(a.conjugate().T @ b, compute_uv=False)


def ribbon_kramers_crossing_proxy(
    width: int = 12,
    q: float = np.pi,
    count: int = 4,
    t: float = 1.0,
    lambda_so: float = 0.06,
    lambda_r: float = 0.04,
    delta: float = 0.0,
    a_nn: float = 1.0,
) -> dict[str, object]:
    n = _positive_int(width, "width", 4)
    c = _positive_int(count, "count", 2)
    h = spinful_zigzag_ribbon_hamiltonian(
        q, n, t=t, lambda_so=lambda_so, lambda_r=lambda_r, delta=delta, a_nn=a_nn
    )
    e, v = np.linalg.eigh(h)
    order = np.argsort(np.abs(e))[:c]
    weights = np.array([spinful_edge_weight(v[:, j], n) for j in order], dtype=float)
    return {
        "energies": [float(e[j]) for j in order],
        "min_abs_energy": float(np.min(np.abs(e[order]))),
        "edge_weights": [float(x) for x in weights],
        "min_edge_weight": float(np.min(weights)),
    }


def bulk_edge_correspondence_summary(
    transverse_points: int = 31,
    loop_points: int = 56,
    width: int = 12,
    mesh: int = 24,
    t: float = 1.0,
    lambda_so: float = 0.06,
    lambda_r: float = 0.04,
    delta: float = 0.0,
    a_nn: float = 1.0,
) -> BulkEdgeSummary:
    flow = wilson_loop_flow(
        transverse_points=transverse_points,
        loop_points=loop_points,
        t=t,
        lambda_so=lambda_so,
        lambda_r=lambda_r,
        delta=delta,
        a_nn=a_nn,
    )
    gap = minimum_direct_gap(
        mesh=mesh, t=t, lambda_so=lambda_so, lambda_r=lambda_r, delta=delta, a_nn=a_nn
    )
    edge = ribbon_kramers_crossing_proxy(
        width=width,
        q=np.pi,
        t=t,
        lambda_so=lambda_so,
        lambda_r=lambda_r,
        delta=delta,
        a_nn=a_nn,
    )
    present = bool(edge["min_abs_energy"] < 0.20 * gap and edge["min_edge_weight"] > 0.80)
    return BulkEdgeSummary(
        z2=flow.z2,
        bulk_gap=float(gap),
        ribbon_min_abs_energy=float(edge["min_abs_energy"]),
        ribbon_min_edge_weight=float(edge["min_edge_weight"]),
        edge_crossing_present=present,
    )


@lru_cache(maxsize=1)
def reference_summary() -> dict[str, object]:
    top_flow = wilson_loop_flow(transverse_points=41, loop_points=72, lambda_so=0.06, lambda_r=0.04, delta=0.0)
    triv_flow = wilson_loop_flow(transverse_points=41, loop_points=72, lambda_so=0.06, lambda_r=0.04, delta=0.40)
    top_edge = bulk_edge_correspondence_summary(
        transverse_points=31, loop_points=56, width=12, mesh=30, lambda_so=0.06, lambda_r=0.04, delta=0.0
    )
    triv_edge = bulk_edge_correspondence_summary(
        transverse_points=31, loop_points=56, width=12, mesh=30, lambda_so=0.06, lambda_r=0.04, delta=0.40
    )
    geo = projector_geometry(0.23, 0.31, lambda_so=0.06, lambda_r=0.04, delta=0.10)
    return {
        "topological_z2": int(top_flow.z2),
        "topological_relative_winding": int(top_flow.relative_winding),
        "topological_endpoint_splitting": [float(x) for x in top_flow.endpoint_splitting],
        "trivial_z2": int(triv_flow.z2),
        "trivial_relative_winding": int(triv_flow.relative_winding),
        "gauge_invariance_error": wilson_loop_gauge_invariance_error(
            0.37, loop_points=56, seed=617, lambda_so=0.06, lambda_r=0.04, delta=0.0
        ),
        "projector_metric_eigenvalues": [float(x) for x in np.linalg.eigvalsh(geo.metric)],
        "projector_curvature_reference": float(geo.curvature),
        "topological_bulk_edge": top_edge.__dict__,
        "trivial_bulk_edge": triv_edge.__dict__,
    }


if __name__ == "__main__":
    import json

    print(json.dumps(reference_summary(), indent=2))
