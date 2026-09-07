"""Computational companion for Chapter 25: operators and measurement.

The module uses finite-dimensional complex arrays to make operator algebra,
spectra, uncertainty, projective measurements, density operators, partial
traces, and simple decoherence channels reproducible.  It is intentionally
small enough to audit line by line.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

import numpy as np

HBAR = 1.054_571_817e-34


def _matrix(a: np.ndarray | Sequence[Sequence[complex]]) -> np.ndarray:
    arr = np.asarray(a, dtype=complex)
    if arr.ndim != 2 or arr.shape[0] != arr.shape[1] or np.any(~np.isfinite(arr)):
        raise ValueError("operator must be a finite square matrix")
    return arr


def _state(psi: np.ndarray | Sequence[complex]) -> np.ndarray:
    arr = np.asarray(psi, dtype=complex)
    if arr.ndim != 1 or arr.size < 1 or np.any(~np.isfinite(arr)):
        raise ValueError("state must be a finite one-dimensional vector")
    norm = float(np.vdot(arr, arr).real)
    if norm <= 0.0:
        raise ValueError("state norm must be positive")
    return arr / np.sqrt(norm)


def is_hermitian(operator: np.ndarray, atol: float = 1e-12) -> bool:
    a = _matrix(operator)
    return bool(np.allclose(a, a.conj().T, atol=atol, rtol=0.0))


def commutator(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    aa, bb = _matrix(a), _matrix(b)
    if aa.shape != bb.shape:
        raise ValueError("operators must have equal dimensions")
    return aa @ bb - bb @ aa


def anticommutator(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    aa, bb = _matrix(a), _matrix(b)
    if aa.shape != bb.shape:
        raise ValueError("operators must have equal dimensions")
    return aa @ bb + bb @ aa


def expectation(psi: np.ndarray, operator: np.ndarray) -> complex:
    state, a = _state(psi), _matrix(operator)
    if a.shape[0] != state.size:
        raise ValueError("state and operator dimensions differ")
    return complex(np.vdot(state, a @ state))


def variance(psi: np.ndarray, operator: np.ndarray) -> float:
    state, a = _state(psi), _matrix(operator)
    mean = expectation(state, a)
    centered = a - mean * np.eye(a.shape[0])
    value = np.vdot(centered @ state, centered @ state).real
    return float(max(value, 0.0))


def robertson_bound(psi: np.ndarray, a: np.ndarray, b: np.ndarray) -> float:
    state = _state(psi)
    value = expectation(state, commutator(a, b))
    return float(abs(value) / 2.0)


def schrodinger_bound_squared(psi: np.ndarray, a: np.ndarray, b: np.ndarray) -> float:
    state, aa, bb = _state(psi), _matrix(a), _matrix(b)
    da = aa - expectation(state, aa) * np.eye(aa.shape[0])
    db = bb - expectation(state, bb) * np.eye(bb.shape[0])
    comm = expectation(state, commutator(aa, bb))
    cov = expectation(state, anticommutator(da, db))
    return float((abs(comm) ** 2 + abs(cov) ** 2) / 4.0)


@dataclass(frozen=True)
class Spectrum:
    values: np.ndarray
    vectors: np.ndarray


def spectral_decomposition(operator: np.ndarray) -> Spectrum:
    a = _matrix(operator)
    if not is_hermitian(a):
        raise ValueError("spectral decomposition requires a Hermitian operator")
    values, vectors = np.linalg.eigh(a)
    return Spectrum(values=values.real, vectors=vectors)


def projectors_from_operator(operator: np.ndarray, tol: float = 1e-10) -> tuple[np.ndarray, list[np.ndarray]]:
    spec = spectral_decomposition(operator)
    values: list[float] = []
    projectors: list[np.ndarray] = []
    for value, vec in zip(spec.values, spec.vectors.T):
        if values and abs(value - values[-1]) <= tol:
            projectors[-1] += np.outer(vec, vec.conj())
        else:
            values.append(float(value))
            projectors.append(np.outer(vec, vec.conj()))
    return np.asarray(values), projectors


def projective_probabilities(psi: np.ndarray, projectors: Iterable[np.ndarray]) -> np.ndarray:
    state = _state(psi)
    probs = []
    for p in projectors:
        pp = _matrix(p)
        if pp.shape[0] != state.size:
            raise ValueError("projector dimension mismatch")
        probs.append(float(np.vdot(state, pp @ state).real))
    result = np.asarray(probs)
    if np.any(result < -1e-10):
        raise ValueError("negative probability indicates invalid projectors")
    return np.clip(result, 0.0, None)


def project_state(psi: np.ndarray, projector: np.ndarray) -> tuple[float, np.ndarray]:
    state, p = _state(psi), _matrix(projector)
    branch = p @ state
    probability = float(np.vdot(branch, branch).real)
    if probability <= 0.0:
        raise ValueError("selected outcome has zero probability")
    return probability, branch / np.sqrt(probability)


def sequential_probability(psi: np.ndarray, first: np.ndarray, second: np.ndarray) -> float:
    state, p, q = _state(psi), _matrix(first), _matrix(second)
    amp = q @ p @ state
    return float(np.vdot(amp, amp).real)


def density_from_pure(psi: np.ndarray) -> np.ndarray:
    state = _state(psi)
    return np.outer(state, state.conj())


def density_from_ensemble(states: Sequence[np.ndarray], weights: Sequence[float]) -> np.ndarray:
    if len(states) != len(weights) or not states:
        raise ValueError("states and weights must have equal nonzero length")
    w = np.asarray(weights, dtype=float)
    if np.any(w < 0.0) or not np.isclose(w.sum(), 1.0):
        raise ValueError("weights must be nonnegative and sum to one")
    normalized = [_state(s) for s in states]
    dim = normalized[0].size
    if any(s.size != dim for s in normalized):
        raise ValueError("all states must have equal dimension")
    rho = np.zeros((dim, dim), dtype=complex)
    for weight, state in zip(w, normalized):
        rho += weight * np.outer(state, state.conj())
    return rho


def validate_density(rho: np.ndarray, atol: float = 1e-10) -> bool:
    r = _matrix(rho)
    eig = np.linalg.eigvalsh((r + r.conj().T) / 2.0)
    return bool(is_hermitian(r, atol) and np.isclose(np.trace(r), 1.0, atol=atol) and eig.min() >= -atol)


def density_expectation(rho: np.ndarray, operator: np.ndarray) -> complex:
    r, a = _matrix(rho), _matrix(operator)
    if r.shape != a.shape or not validate_density(r):
        raise ValueError("invalid density operator or dimension mismatch")
    return complex(np.trace(r @ a))


def purity(rho: np.ndarray) -> float:
    r = _matrix(rho)
    if not validate_density(r):
        raise ValueError("invalid density operator")
    return float(np.trace(r @ r).real)


def von_neumann_entropy(rho: np.ndarray, base: float = 2.0) -> float:
    r = _matrix(rho)
    if not validate_density(r) or base <= 0.0 or np.isclose(base, 1.0):
        raise ValueError("invalid density operator or logarithm base")
    eig = np.clip(np.linalg.eigvalsh(r), 0.0, 1.0)
    nz = eig[eig > 1e-15]
    return float(-np.sum(nz * np.log(nz)) / np.log(base))


def partial_trace(rho: np.ndarray, dims: tuple[int, int], trace_over: int) -> np.ndarray:
    r = _matrix(rho)
    da, db = dims
    if da * db != r.shape[0] or trace_over not in (0, 1):
        raise ValueError("dimensions or subsystem selector are invalid")
    reshaped = r.reshape(da, db, da, db)
    if trace_over == 0:
        return np.trace(reshaped, axis1=0, axis2=2)
    return np.trace(reshaped, axis1=1, axis2=3)


def pauli_matrices() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    sx = np.array([[0, 1], [1, 0]], dtype=complex)
    sy = np.array([[0, -1j], [1j, 0]], dtype=complex)
    sz = np.array([[1, 0], [0, -1]], dtype=complex)
    return sx, sy, sz


def bloch_density(vector: Sequence[float]) -> np.ndarray:
    r = np.asarray(vector, dtype=float)
    if r.shape != (3,) or np.linalg.norm(r) > 1.0 + 1e-12:
        raise ValueError("Bloch vector must have length at most one")
    sx, sy, sz = pauli_matrices()
    return 0.5 * (np.eye(2) + r[0] * sx + r[1] * sy + r[2] * sz)


def bloch_vector(rho: np.ndarray) -> np.ndarray:
    r = _matrix(rho)
    if r.shape != (2, 2) or not validate_density(r):
        raise ValueError("rho must be a valid qubit density operator")
    return np.asarray([density_expectation(r, s).real for s in pauli_matrices()])


def dephase(rho: np.ndarray, coherence_factor: float) -> np.ndarray:
    r = _matrix(rho)
    if not validate_density(r) or not (0.0 <= coherence_factor <= 1.0):
        raise ValueError("invalid density operator or coherence factor")
    out = r.copy()
    for i in range(r.shape[0]):
        for j in range(r.shape[1]):
            if i != j:
                out[i, j] *= coherence_factor
    return out


def nearest_physical_qubit(vector: Sequence[float]) -> np.ndarray:
    r = np.asarray(vector, dtype=float)
    if r.shape != (3,) or np.any(~np.isfinite(r)):
        raise ValueError("vector must have three finite components")
    norm = np.linalg.norm(r)
    if norm > 1.0:
        r = r / norm
    return bloch_density(r)
