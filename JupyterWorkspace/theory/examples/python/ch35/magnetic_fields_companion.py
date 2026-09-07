"""Computational companion for Chapter 35: Charged Particles in Magnetic Fields.
SI-like formulas are used when physical constants are supplied; dimensionless checks may set hbar=1.
"""
from __future__ import annotations
import math
import numpy as np


def cyclotron_frequency(q, B, m):
    return abs(float(q))*abs(float(B))/float(m)


def signed_cyclotron_frequency(q, B, m):
    return float(q)*float(B)/float(m)


def cyclotron_radius(v_perp, q, B, m):
    return float(m)*abs(float(v_perp))/(abs(float(q))*abs(float(B)))


def cyclotron_trajectory(t, x0, y0, vx0, vy0, q, B, m):
    """Exact planar orbit for uniform B=B zhat, no electric field."""
    t=np.asarray(t,dtype=float); w=signed_cyclotron_frequency(q,B,m)
    if w == 0: return x0+vx0*t, y0+vy0*t
    X=x0+vy0/w; Y=y0-vx0/w
    vx=vx0*np.cos(w*t)+vy0*np.sin(w*t)
    vy=vy0*np.cos(w*t)-vx0*np.sin(w*t)
    x=X-vy/w; y=Y+vx/w
    return x,y


def guiding_center(x, y, vx, vy, q, B, m):
    w=signed_cyclotron_frequency(q,B,m)
    if w == 0: raise ValueError('B and q must be nonzero')
    return np.asarray(x)+np.asarray(vy)/w, np.asarray(y)-np.asarray(vx)/w


def exb_drift(E, B):
    E=np.asarray(E,dtype=float); B=np.asarray(B,dtype=float)
    b2=float(np.dot(B,B))
    if b2 == 0: raise ValueError('B must be nonzero')
    return np.cross(E,B)/b2


def magnetic_length(q, B, hbar=1.0):
    return math.sqrt(float(hbar)/(abs(float(q))*abs(float(B))))


def flux_quantum(q, h=2*math.pi):
    return float(h)/abs(float(q))


def flux_cell_area(q, B, h=2*math.pi):
    return flux_quantum(q,h)/abs(float(B))


def landau_state_count(area, q, B, h=2*math.pi):
    return float(area)/flux_cell_area(q,B,h)


def kinetic_momentum_commutator_scale(q, B, hbar=1.0):
    """Coefficient C in [pi_x,pi_y]=i C."""
    return float(q)*float(hbar)*float(B)


def guiding_center_commutator_scale(q, B, hbar=1.0):
    """Coefficient C in [X,Y]=i C."""
    return -float(hbar)/(float(q)*float(B))


def landau_gauge_A(x, y, B):
    x=np.asarray(x,dtype=float); y=np.asarray(y,dtype=float)
    z=np.zeros(np.broadcast(x,y).shape)
    return np.stack([z, float(B)*np.broadcast_to(x,z.shape), z],axis=-1)


def symmetric_gauge_A(x, y, B):
    x=np.asarray(x,dtype=float); y=np.asarray(y,dtype=float)
    xb,yb=np.broadcast_arrays(x,y); z=np.zeros_like(xb)
    return np.stack([-0.5*float(B)*yb,0.5*float(B)*xb,z],axis=-1)


def gauge_function_landau_to_symmetric(x,y,B):
    return -0.5*float(B)*np.asarray(x,dtype=float)*np.asarray(y,dtype=float)


def gauge_phase(q, chi, hbar=1.0):
    return np.exp(1j*float(q)*np.asarray(chi,dtype=float)/float(hbar))


def magnetic_energy(v, m):
    v=np.asarray(v,dtype=float)
    return 0.5*float(m)*np.sum(v*v,axis=-1)


def hall_drift_current_density(n, q, E, B):
    return float(n)*float(q)*exb_drift(E,B)
