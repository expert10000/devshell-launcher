
"""Commit 640 numerical companion: open-system foundations and quantum channels."""
from __future__ import annotations
import numpy as np

I2 = np.eye(2, dtype=complex)
X = np.array([[0, 1], [1, 0]], dtype=complex)
Y = np.array([[0, -1j], [1j, 0]], dtype=complex)
Z = np.array([[1, 0], [0, -1]], dtype=complex)

def density(psi):
    v = np.asarray(psi, dtype=complex).reshape(-1)
    n = np.linalg.norm(v)
    if n == 0:
        raise ValueError("state vector must be nonzero")
    v = v / n
    return np.outer(v, v.conj())

def purity(rho):
    r = np.asarray(rho, dtype=complex)
    return float(np.trace(r @ r).real)

def von_neumann_entropy(rho):
    vals = np.linalg.eigvalsh(np.asarray(rho, dtype=complex)).real
    vals = np.clip(vals, 0.0, 1.0)
    nz = vals[vals > 1e-15]
    return float(-np.sum(nz * np.log2(nz)))

def partial_trace_bipartite(rho, dims, trace_over):
    da, db = map(int, dims)
    r = np.asarray(rho, dtype=complex).reshape(da, db, da, db)
    if trace_over == 0:
        return np.trace(r, axis1=0, axis2=2)
    if trace_over == 1:
        return np.trace(r, axis1=1, axis2=3)
    raise ValueError("trace_over must be 0 or 1")

def bell_state():
    return np.array([1, 0, 0, 1], dtype=complex) / np.sqrt(2)

def schmidt_coefficients(psi, dims):
    da, db = map(int, dims)
    A = np.asarray(psi, dtype=complex).reshape(da, db)
    return np.linalg.svd(A, compute_uv=False)

def amplitude_damping_kraus(gamma):
    g = float(gamma)
    if not 0 <= g <= 1:
        raise ValueError("gamma must be in [0,1]")
    return [
        np.array([[1, 0], [0, np.sqrt(1-g)]], dtype=complex),
        np.array([[0, np.sqrt(g)], [0, 0]], dtype=complex),
    ]

def phase_damping_kraus(lam):
    p = float(lam)
    if not 0 <= p <= 1:
        raise ValueError("lambda must be in [0,1]")
    return [np.array([[1,0],[0,np.sqrt(1-p)]],dtype=complex), np.array([[0,0],[0,np.sqrt(p)]],dtype=complex)]

def depolarizing_kraus(p):
    q = float(p)
    if not 0 <= q <= 1:
        raise ValueError("p must be in [0,1]")
    return [
        np.sqrt(1 - 3*q/4) * I2,
        np.sqrt(q/4) * X,
        np.sqrt(q/4) * Y,
        np.sqrt(q/4) * Z,
    ]

def apply_channel(rho, kraus):
    r = np.asarray(rho, dtype=complex)
    out = np.zeros_like(r)
    for K in kraus:
        K = np.asarray(K, dtype=complex)
        out += K @ r @ K.conj().T
    return out

def kraus_completeness(kraus):
    ks = [np.asarray(K, dtype=complex) for K in kraus]
    d = ks[0].shape[1]
    return sum(K.conj().T @ K for K in ks)

def bloch_vector(rho):
    r = np.asarray(rho, dtype=complex)
    return np.array([np.trace(r @ X).real, np.trace(r @ Y).real, np.trace(r @ Z).real])

def purification_from_density(rho):
    vals, vecs = np.linalg.eigh(np.asarray(rho, dtype=complex))
    vals = np.clip(vals.real, 0, None)
    d = len(vals)
    psi = np.zeros(d*d, dtype=complex)
    for i, lam in enumerate(vals):
        if lam > 0:
            psi += np.sqrt(lam) * np.kron(vecs[:, i], np.eye(d)[:, i])
    return psi / np.linalg.norm(psi)

def unitary_dilation_amplitude_damping(gamma):
    g = float(gamma)
    if not 0 <= g <= 1:
        raise ValueError("gamma must be in [0,1]")
    U = np.eye(4, dtype=complex)
    c, s = np.sqrt(1-g), np.sqrt(g)
    U[2,2] = c; U[1,2] = s
    U[2,1] = -s; U[1,1] = c
    return U

def trace_distance(rho, sigma):
    d = np.asarray(rho, complex) - np.asarray(sigma, complex)
    return float(0.5 * np.sum(np.abs(np.linalg.eigvalsh(d))))

def channel_population_curve(gammas):
    rho1 = np.array([[0,0],[0,1]], dtype=complex)
    return np.array([apply_channel(rho1, amplitude_damping_kraus(g))[1,1].real for g in gammas])

def channel_coherence_curve(lams):
    plus = density(np.array([1,1], complex))
    return np.array([abs(apply_channel(plus, phase_damping_kraus(x))[0,1]) for x in lams])
