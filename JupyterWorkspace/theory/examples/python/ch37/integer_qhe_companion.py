"""Computational companion for Chapter 37: Integer Quantum Hall Effect.
Dimensionless defaults use h=e=1 unless supplied explicitly.
"""
from __future__ import annotations
import math
import numpy as np

def hall_conductivity(integer, e=1.0, h=1.0):
    return float(integer)*float(e)**2/float(h)

def hall_resistance(integer, e=1.0, h=1.0):
    n=int(integer)
    if n==0: raise ValueError('integer must be nonzero')
    return float(h)/(n*float(e)**2)

def filling_factor(n2d, B, e=1.0, h=1.0):
    return float(n2d)*float(h)/(abs(float(e))*abs(float(B)))

def conductivity_tensor(sxx, sxy):
    return np.array([[float(sxx), float(sxy)],[-float(sxy), float(sxx)]])

def resistivity_tensor(sxx, sxy):
    sxx=float(sxx); sxy=float(sxy); d=sxx*sxx+sxy*sxy
    if d==0: raise ValueError('singular conductivity tensor')
    return np.array([[sxx,-sxy],[sxy,sxx]])/d

def plateau_integer(nu):
    return int(max(0,math.floor(float(nu)+1e-12)))

def gaussian_broadened_dos(E, centers, gamma, weights=None):
    E=np.asarray(E,dtype=float); centers=np.asarray(centers,dtype=float); gamma=float(gamma)
    if gamma<=0: raise ValueError('gamma must be positive')
    if weights is None: weights=np.ones(len(centers))
    weights=np.asarray(weights,dtype=float)
    out=np.zeros_like(E); pref=1.0/(math.sqrt(2*math.pi)*gamma)
    for c,w in zip(centers,weights): out += w*pref*np.exp(-0.5*((E-c)/gamma)**2)
    return out

def localized_tail_weight(E, center, gamma, mobility_halfwidth):
    E=np.asarray(E,dtype=float); x=np.abs(E-float(center))
    return np.where(x>float(mobility_halfwidth), np.exp(-0.5*(x/float(gamma))**2), 0.0)

def kubo_integer_conductivity(filled_levels, e=1.0, h=1.0):
    return hall_conductivity(int(filled_levels),e,h)

def flux_guiding_center_shift(delta_flux, B, Ly):
    return -float(delta_flux)/(float(B)*float(Ly))

def pumped_charge(filled_levels, flux_quanta=1.0, e=1.0):
    return float(filled_levels)*float(flux_quanta)*float(e)

def chern_hall_conductivity(C, e=1.0, h=1.0):
    return hall_conductivity(int(C),e,h)

def four_terminal_resistances(integer, rxx=0.0, e=1.0, h=1.0):
    return float(rxx), hall_resistance(integer,e,h)

def edge_group_velocity(dE_dk, hbar=1.0):
    return float(dE_dk)/float(hbar)

def thermal_smearing(E, mu=0.0, kT=1.0):
    E=np.asarray(E,dtype=float); kT=float(kT)
    if kT<=0: raise ValueError('kT must be positive')
    x=(E-float(mu))/(2*kT)
    return 1.0/(4*kT*np.cosh(x)**2)
