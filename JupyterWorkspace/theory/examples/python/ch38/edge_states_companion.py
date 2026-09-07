"""Computational companion for Chapter 38: Edge States and Bulk--Boundary Correspondence.

Dimensionless defaults use e=h=hbar=1 unless explicit SI constants are supplied.  The
functions are intentionally small so that each numerical diagnostic can be compared with
an analytic identity from the chapter.
"""
from __future__ import annotations
import math
import numpy as np


def magnetic_length(B, hbar=1.0, e=1.0):
    B=float(B)
    if B == 0: raise ValueError('B must be nonzero')
    return math.sqrt(float(hbar)/(abs(float(e))*abs(B)))


def guiding_center(k, lB=1.0, orientation=-1.0):
    return float(orientation)*float(lB)**2*np.asarray(k,dtype=float)


def smooth_edge_dispersion(k, E0=0.5, gradient=0.2, lB=1.0, orientation=-1.0):
    Y=guiding_center(k,lB,orientation)
    return float(E0)+float(gradient)*Y


def group_velocity_from_slope(dE_dk, hbar=1.0):
    return np.asarray(dE_dk,dtype=float)/float(hbar)


def smooth_edge_velocity(gradient, lB=1.0, hbar=1.0, orientation=-1.0):
    return float(orientation)*float(lB)**2*float(gradient)/float(hbar)


def landauer_current(delta_v, transmission=1.0, e=1.0, h=1.0):
    T=float(transmission)
    if not 0.0 <= T <= 1.0: raise ValueError('transmission must lie in [0,1]')
    return float(e)**2/float(h)*T*float(delta_v)


def multichannel_conductance(transmissions, e=1.0, h=1.0):
    T=np.asarray(transmissions,dtype=float)
    if np.any((T<0)|(T>1)): raise ValueError('transmissions must lie in [0,1]')
    return float(e)**2/float(h)*float(np.sum(T))


def chiral_ring_currents(voltages, channels=1, e=1.0, h=1.0, direction=1):
    v=np.asarray(voltages,dtype=float); n=len(v)
    if n < 2: raise ValueError('need at least two contacts')
    if direction not in (-1,1): raise ValueError('direction must be +/-1')
    G=float(channels)*float(e)**2/float(h)
    incoming=np.roll(v,1 if direction==1 else -1)
    return G*(v-incoming)


def ideal_hall_probe_voltages(Vs, Vd, contacts=6, source=0, drain=3, direction=1):
    if contacts < 4: raise ValueError('need at least four contacts')
    if source == drain: raise ValueError('source and drain must differ')
    if direction not in (-1,1): raise ValueError('direction must be +/-1')
    v=np.full(contacts,np.nan); v[source]=float(Vs); v[drain]=float(Vd)
    i=source
    while True:
        i=(i+direction)%contacts
        if i==drain: break
        v[i]=float(Vs)
    i=drain
    while True:
        i=(i+direction)%contacts
        if i==source: break
        v[i]=float(Vd)
    return v


def hall_resistance_from_channels(channels, e=1.0, h=1.0):
    N=int(channels)
    if N <= 0: raise ValueError('channels must be positive')
    return float(h)/(N*float(e)**2)


def qpc_conductance(transmissions, e=1.0, h=1.0):
    return multichannel_conductance(transmissions,e,h)


def equilibration_potential(potentials, weights=None):
    p=np.asarray(potentials,dtype=float)
    if weights is None: weights=np.ones_like(p)
    w=np.asarray(weights,dtype=float)
    if p.shape != w.shape or np.any(w<0) or np.sum(w)==0: raise ValueError('invalid weights')
    return float(np.sum(w*p)/np.sum(w))


def equilibration_profile(x, mu1, mu2, length):
    x=np.asarray(x,dtype=float); length=float(length)
    if length <= 0: raise ValueError('length must be positive')
    mean=0.5*(float(mu1)+float(mu2)); diff=0.5*(float(mu1)-float(mu2))*np.exp(-x/length)
    return mean+diff, mean-diff


def interedge_tunneling_scale(separation, lB=1.0):
    lB=float(lB)
    if lB <= 0: raise ValueError('lB must be positive')
    s=np.asarray(separation,dtype=float)
    return np.exp(-0.5*(s/lB)**2)


def bulk_boundary_index(C_left, C_right):
    return int(C_left)-int(C_right)


def reconstructed_edge_index(n_plus, n_minus):
    return int(n_plus)-int(n_minus)


def spectral_flow_levels(phi, offsets=(0,1,2,3), chirality=1.0):
    phi=np.asarray(phi,dtype=float)
    return np.vstack([float(o)+float(chirality)*phi for o in offsets])


def pumped_charge(C, flux_quanta=1.0, e=1.0):
    return float(C)*float(flux_quanta)*float(e)


def local_filling(n2d, B, e=1.0, h=1.0):
    B=float(B)
    if B == 0: raise ValueError('B must be nonzero')
    return np.asarray(n2d,dtype=float)*float(h)/(abs(float(e))*abs(B))


def incompressible_mask(nu, tolerance=0.08):
    nu=np.asarray(nu,dtype=float); tolerance=float(tolerance)
    if tolerance < 0: raise ValueError('tolerance must be nonnegative')
    return np.abs(nu-np.rint(nu)) <= tolerance


def edge_current_increment(delta_mu, channels=1, e=1.0, h=1.0):
    return float(channels)*float(e)/float(h)*float(delta_mu)
