"""Computational companion for Chapter 39: Fractional Quantum Hall Effect.

The routines are intentionally compact analytic diagnostics rather than a many-body ED
package. Dimensionless defaults use e=h=hbar=1 unless an explicit constant is supplied.
"""
from __future__ import annotations
import math
import numpy as np


def magnetic_length(B, hbar=1.0, e=1.0):
    B=float(B)
    if B == 0: raise ValueError('B must be nonzero')
    return math.sqrt(float(hbar)/(abs(float(e))*abs(B)))


def coulomb_scale(B, epsilon=1.0, prefactor=1.0, hbar=1.0, e=1.0):
    eps=float(epsilon)
    if eps <= 0: raise ValueError('epsilon must be positive')
    return float(prefactor)/(eps*magnetic_length(B,hbar,e))


def landau_mixing_parameter(coulomb_energy, cyclotron_gap):
    gap=float(cyclotron_gap)
    if gap <= 0: raise ValueError('cyclotron gap must be positive')
    return float(coulomb_energy)/gap


def laughlin_sphere_flux(N, m):
    N=int(N); m=int(m)
    if N < 2 or m <= 0 or m % 2 == 0: raise ValueError('need N>=2 and positive odd m')
    return m*(N-1)


def sphere_orbitals(Nphi):
    n=int(Nphi)
    if n < 0: raise ValueError('Nphi must be nonnegative')
    return n+1


def hilbert_dimension(N, Norb):
    N=int(N); Norb=int(Norb)
    if N < 0 or Norb < N: raise ValueError('require 0 <= N <= Norb')
    return math.comb(Norb,N)


def filling_factor(N, Nphi):
    if float(Nphi) == 0: raise ValueError('Nphi must be nonzero')
    return float(N)/float(Nphi)


def pair_correlation_short_distance(r, m, lB=1.0):
    m=int(m); lB=float(lB)
    if m <= 0 or lB <= 0: raise ValueError('m and lB must be positive')
    x=np.asarray(r,dtype=float)/lB
    return np.maximum(x,0.0)**(2*m)


def quasihole_charge(m, e=1.0):
    m=int(m)
    if m <= 0: raise ValueError('m must be positive')
    return float(e)/m


def full_braid_phase(m):
    m=int(m)
    if m <= 0: raise ValueError('m must be positive')
    return 2.0*math.pi/m


def exchange_angle(m):
    return 0.5*full_braid_phase(m)


def hall_conductance(nu, e=1.0, h=1.0):
    return float(nu)*float(e)**2/float(h)


def pumped_charge(nu, flux_quanta=1.0, e=1.0):
    return float(nu)*float(flux_quanta)*float(e)


def torus_degeneracy(m):
    m=int(m)
    if m <= 0: raise ValueError('m must be positive')
    return m


def bundle_response(C, degeneracy, e=1.0, h=1.0):
    d=int(degeneracy)
    if d <= 0: raise ValueError('degeneracy must be positive')
    return float(C)/d*float(e)**2/float(h)


def uniform_trace_curvature(C):
    """Constant Tr F on a 2pi x 2pi twist torus giving total Chern number C."""
    return float(C)/(2.0*math.pi)


def chern_from_grid(curvature, dtheta_x, dtheta_y):
    F=np.asarray(curvature,dtype=float)
    return float(np.sum(F)*float(dtheta_x)*float(dtheta_y)/(2.0*math.pi))


def topological_splitting(L, xi=1.0, amplitude=1.0):
    xi=float(xi)
    if xi <= 0: raise ValueError('xi must be positive')
    return float(amplitude)*np.exp(-np.asarray(L,dtype=float)/xi)


def parent_energy(pair_weights, pseudopotentials):
    w=np.asarray(pair_weights,dtype=float); v=np.asarray(pseudopotentials,dtype=float)
    if w.shape != v.shape or np.any(w < 0) or np.any(v < 0): raise ValueError('invalid pair data')
    return float(np.dot(w,v))


def neutral_gap(ground_energy, first_excited_energy):
    gap=float(first_excited_energy)-float(ground_energy)
    if gap < -1e-12: raise ValueError('excited energy below ground energy')
    return gap


def linear_gap_extrapolation(N, gaps):
    N=np.asarray(N,dtype=float); gaps=np.asarray(gaps,dtype=float)
    if len(N) != len(gaps) or len(N) < 2 or np.any(N <= 0): raise ValueError('invalid data')
    slope, intercept=np.polyfit(1.0/N,gaps,1)
    return float(intercept), float(slope)


def spectral_flow_levels(phi, m):
    phi=np.asarray(phi,dtype=float); m=int(m)
    if m <= 0: raise ValueError('m must be positive')
    return np.vstack([j+phi for j in range(m)])


def small_q_structure_factor(q, coefficient=0.25):
    q=np.asarray(q,dtype=float)
    return float(coefficient)*q**4
