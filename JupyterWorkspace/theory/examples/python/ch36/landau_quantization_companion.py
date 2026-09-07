"""Computational companion for Chapter 36: Landau Quantization.
Dimensionless defaults use hbar=e=1 unless physical constants are supplied explicitly.
"""
from __future__ import annotations
import math
import numpy as np


def magnetic_length(B, q=1.0, hbar=1.0):
    return math.sqrt(float(hbar)/(abs(float(q))*abs(float(B))))


def cyclotron_frequency(B, m=1.0, q=1.0):
    return abs(float(q))*abs(float(B))/float(m)


def landau_energy(n, B, m=1.0, q=1.0, hbar=1.0):
    return float(hbar)*cyclotron_frequency(B,m,q)*(int(n)+0.5)


def flux_quantum(q=1.0, h=2*math.pi):
    return float(h)/abs(float(q))


def flux_degeneracy(area, B, q=1.0, h=2*math.pi):
    return float(area)*abs(float(B))/flux_quantum(q,h)


def state_density(B, q=1.0, h=2*math.pi):
    return abs(float(q))*abs(float(B))/float(h)


def filling_factor(n2d, B, q=1.0, h=2*math.pi):
    return float(n2d)/state_density(B,q,h)


def guiding_center_spacing(Ly, B, q=1.0, hbar=1.0):
    lb=magnetic_length(B,q,hbar)
    return 2*math.pi*lb*lb/float(Ly)


def guiding_centers(Lx, Ly, B, q=1.0, hbar=1.0):
    dx=guiding_center_spacing(Ly,B,q,hbar)
    n=max(0,int(math.floor(float(Lx)/dx)))
    return (np.arange(n,dtype=float)+0.5)*dx


def hermite_phys(n, x):
    x=np.asarray(x,dtype=float)
    if n==0: return np.ones_like(x)
    if n==1: return 2*x
    hm2=np.ones_like(x); hm1=2*x
    for k in range(1,int(n)):
        h=2*x*hm1-2*k*hm2; hm2,hm1=hm1,h
    return hm1


def landau_gauge_orbital(n, x, X=0.0, lB=1.0):
    xi=(np.asarray(x,dtype=float)-float(X))/float(lB)
    norm=1.0/(math.sqrt((2**int(n))*math.factorial(int(n)))*math.pi**0.25*math.sqrt(float(lB)))
    return norm*hermite_phys(int(n),xi)*np.exp(-0.5*xi*xi)


def lll_radial_probability(k, r, lB=1.0):
    r=np.asarray(r,dtype=float); k=int(k); lb=float(lB)
    # radial probability density P(r) dr, normalized on [0,infinity)
    return (r/(lb*lb*math.factorial(k)))*(r*r/(2*lb*lb))**k*np.exp(-r*r/(2*lb*lb))


def zeeman_splitting(B, g=2.0, muB=0.5):
    return abs(float(g))*float(muB)*abs(float(B))


def spin_resolved_energy(n, sigma, B, m=1.0, q=1.0, hbar=1.0, g=2.0, muB=0.5):
    return landau_energy(n,B,m,q,hbar)+0.5*float(sigma)*float(g)*float(muB)*float(B)


def gaussian_broadened_dos(E, levels, gamma, weight=1.0):
    E=np.asarray(E,dtype=float); levels=np.asarray(levels,dtype=float); gamma=float(gamma)
    if gamma<=0: raise ValueError('gamma must be positive')
    pref=float(weight)/(math.sqrt(2*math.pi)*gamma)
    out=np.zeros_like(E)
    for e0 in levels: out += pref*np.exp(-0.5*((E-e0)/gamma)**2)
    return out
