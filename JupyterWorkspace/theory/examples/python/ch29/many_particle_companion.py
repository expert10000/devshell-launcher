"""Computational companion for Chapter 29: many-particle systems.

The module uses finite mode spaces to make symmetry, occupation-number algebra,
reduced density matrices, and elementary interacting models reproducible.
"""
from __future__ import annotations
from itertools import combinations
from math import comb, sqrt
import numpy as np


def bosonic_basis(total: int, modes: int) -> list[tuple[int, ...]]:
    if total < 0 or modes < 1:
        raise ValueError("total must be nonnegative and modes positive")
    out: list[tuple[int, ...]] = []
    def rec(rem: int, k: int, prefix: tuple[int, ...]) -> None:
        if k == 1:
            out.append(prefix + (rem,))
            return
        for n in range(rem + 1):
            rec(rem - n, k - 1, prefix + (n,))
    rec(total, modes, ())
    return out


def fermionic_basis(total: int, modes: int) -> list[tuple[int, ...]]:
    if total < 0 or modes < 1 or total > modes:
        raise ValueError("require 0 <= total <= modes")
    out=[]
    for occ in combinations(range(modes), total):
        row=[0]*modes
        for i in occ: row[i]=1
        out.append(tuple(row))
    return out


def bosonic_dimension(total: int, modes: int) -> int:
    if total < 0 or modes < 1: raise ValueError
    return comb(total + modes - 1, total)


def fermionic_dimension(total: int, modes: int) -> int:
    if total < 0 or modes < 1 or total > modes: raise ValueError
    return comb(modes, total)


def boson_annihilation(cutoff: int) -> np.ndarray:
    if cutoff < 1: raise ValueError
    a=np.zeros((cutoff+1, cutoff+1))
    for n in range(1, cutoff+1): a[n-1,n]=sqrt(n)
    return a


def fermion_annihilation() -> np.ndarray:
    return np.array([[0.0,1.0],[0.0,0.0]])


def number_operator_from_annihilation(a: np.ndarray) -> np.ndarray:
    a=np.asarray(a,dtype=complex)
    return a.conj().T @ a


def one_rdm_from_occupation(occupation: tuple[int, ...] | list[int]) -> np.ndarray:
    occ=np.asarray(occupation,dtype=float)
    if np.any(occ < 0): raise ValueError
    return np.diag(occ)


def slater_one_rdm(occupied_orbitals: np.ndarray) -> np.ndarray:
    c=np.asarray(occupied_orbitals,dtype=complex)
    if c.ndim != 2: raise ValueError
    gram=c.conj().T @ c
    if not np.allclose(gram,np.eye(gram.shape[0]),atol=1e-10):
        raise ValueError("columns must be orthonormal")
    return c @ c.conj().T


def natural_occupations(gamma: np.ndarray) -> np.ndarray:
    vals=np.linalg.eigvalsh(np.asarray(gamma,dtype=complex))
    return np.sort(np.real_if_close(vals))[::-1]


def g2_single_mode(n: int) -> float:
    if n < 0: raise ValueError
    if n == 0: return 0.0
    return (n*(n-1))/(n*n)


def coherent_g2() -> float:
    return 1.0


def thermal_g2() -> float:
    return 2.0


def bose_hubbard_dimer(total: int, hopping: float, interaction: float) -> tuple[np.ndarray,list[tuple[int,int]]]:
    basis=[(n,total-n) for n in range(total+1)]
    idx={s:i for i,s in enumerate(basis)}
    h=np.zeros((len(basis),len(basis)))
    for i,(n1,n2) in enumerate(basis):
        h[i,i]=0.5*interaction*(n1*(n1-1)+n2*(n2-1))
        if n2>0:
            j=idx[(n1+1,n2-1)]
            h[j,i] += -hopping*sqrt((n1+1)*n2)
        if n1>0:
            j=idx[(n1-1,n2+1)]
            h[j,i] += -hopping*sqrt(n1*(n2+1))
    return h,basis


def ground_state(h: np.ndarray) -> tuple[float,np.ndarray]:
    vals,vecs=np.linalg.eigh(np.asarray(h,dtype=float))
    return float(vals[0]),vecs[:,0]


def occupation_expectation(probabilities: np.ndarray,basis: list[tuple[int,...]]) -> np.ndarray:
    p=np.asarray(probabilities,dtype=float)
    if not np.isclose(np.sum(p),1.0): raise ValueError("probabilities must sum to one")
    return np.sum(np.asarray(basis,dtype=float)*p[:,None],axis=0)


def exchange_hole_gaussian(separation, width: float=1.0):
    if width <= 0: raise ValueError
    r=np.asarray(separation,dtype=float)
    return 1.0-np.exp(-(r/width)**2)


def density_matrix(state: np.ndarray) -> np.ndarray:
    psi=np.asarray(state,dtype=complex).reshape(-1)
    norm=np.vdot(psi,psi).real
    if norm <= 0: raise ValueError
    psi=psi/sqrt(norm)
    return np.outer(psi,psi.conj())


def partial_trace_two_qubits(rho: np.ndarray, keep: int=0) -> np.ndarray:
    r=np.asarray(rho,dtype=complex)
    if r.shape != (4,4) or keep not in (0,1): raise ValueError
    t=r.reshape(2,2,2,2)
    return np.trace(t,axis1=1 if keep==0 else 0,axis2=3 if keep==0 else 2)


def von_neumann_entropy(rho: np.ndarray, base: float=2.0) -> float:
    vals=np.linalg.eigvalsh(np.asarray(rho,dtype=complex)).real
    vals=vals[vals>1e-14]
    return float(-np.sum(vals*np.log(vals))/np.log(base))
