"""Chapter 40 computational companion: composite fermions, partons, and anyons.

Dimensionless conventions use |e|=h=1 unless explicitly supplied.  The routines are
small analytic diagnostics intended for regression and pedagogy, not a many-body solver.
"""
from __future__ import annotations
import math
import numpy as np


def jain_fraction(p, s=1, branch=1):
    p=int(p); s=int(s); branch=int(branch)
    if p <= 0 or s <= 0 or branch not in (-1,1): raise ValueError('require p,s>0 and branch=+/-1')
    den=2*s*p+branch
    if den == 0: raise ValueError('singular Jain denominator')
    return p/den


def effective_field_ratio(nu, s=1):
    return 1.0-2.0*int(s)*float(nu)


def effective_filling(nu, s=1):
    r=effective_field_ratio(nu,s)
    if abs(r) < 1e-14: return math.inf
    return float(nu)/r


def finite_effective_flux(N, Nphi, s=1):
    N=int(N); s=int(s)
    if N < 1 or s < 1: raise ValueError('require N,s positive')
    return int(Nphi)-2*s*(N-1)


def positive_jain_shift(p, s=1):
    p=int(p); s=int(s)
    if p <= 0 or s <= 0: raise ValueError('require p,s positive')
    return p+2*s


def cf_fermi_wavevector(density):
    n=float(density)
    if n < 0: raise ValueError('density must be nonnegative')
    return math.sqrt(4.0*math.pi*n)


def parton_filling(fillings):
    ns=np.asarray(fillings,dtype=float)
    if ns.ndim != 1 or len(ns)==0 or np.any(ns==0): raise ValueError('nonzero signed fillings required')
    inv=float(np.sum(1.0/ns))
    if abs(inv)<1e-14: raise ValueError('singular reciprocal filling sum')
    return 1.0/inv


def parton_charges(fillings, electron_charge=-1.0):
    ns=np.asarray(fillings,dtype=float); nu=parton_filling(ns)
    return float(electron_charge)*nu/ns


def jain_kmatrix(p, s=1):
    p=int(p); s=int(s)
    if p <= 0 or s <= 0: raise ValueError('require p,s positive')
    return np.eye(p,dtype=int)+2*s*np.ones((p,p),dtype=int)


def kmatrix_filling(K, t):
    K=np.asarray(K,dtype=float); t=np.asarray(t,dtype=float)
    return float(t @ np.linalg.solve(K,t))


def anyon_charge(K, t, ell, e=1.0):
    K=np.asarray(K,dtype=float); t=np.asarray(t,dtype=float); ell=np.asarray(ell,dtype=float)
    return float(e)*(t @ np.linalg.solve(K,ell))


def anyon_exchange_angle(K, ell):
    K=np.asarray(K,dtype=float); ell=np.asarray(ell,dtype=float)
    return math.pi*float(ell @ np.linalg.solve(K,ell))


def anyon_mutual_phase(K, ell, ell2):
    K=np.asarray(K,dtype=float); ell=np.asarray(ell,dtype=float); ell2=np.asarray(ell2,dtype=float)
    return 2.0*math.pi*float(ell @ np.linalg.solve(K,ell2))


def torus_degeneracy(K):
    d=float(np.linalg.det(np.asarray(K,dtype=float)))
    return int(round(abs(d)))


def local_particle_shift(ell, K, n):
    return np.asarray(ell,dtype=int)+np.asarray(K,dtype=int)@np.asarray(n,dtype=int)


def ising_fusion_space_dimension(n_sigma, fixed_total=True):
    n=int(n_sigma)
    if n < 0 or n % 2: raise ValueError('use an even number of sigma anyons')
    if n == 0: return 1
    return 2**(n//2-1) if fixed_total else 2**(n//2)


def ising_braid_generators():
    R12=np.array([[1.0+0j,0j],[0j,1j]])
    F=np.array([[1.0,1.0],[1.0,-1.0]],dtype=complex)/math.sqrt(2.0)
    R23=F.conj().T@R12@F
    return R12,R23


def braid_commutator_norm():
    a,b=ising_braid_generators()
    return float(np.linalg.norm(a@b-b@a))


def moore_read_fundamental_charge(e=1.0):
    return float(e)/4.0


def read_rezayi_filling(k, M=1):
    k=int(k); M=int(M)
    if k <= 0 or M < 0: raise ValueError('require k>0 and M>=0')
    return k/(k*M+2.0)
