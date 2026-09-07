from __future__ import annotations
import numpy as np

def inversion_polarization(delta):
    delta=np.asarray(delta,float); return 0.25*(1-np.tanh(8*delta))

def wannier_center_flow(lam):
    lam=np.asarray(lam,float); return np.mod(0.5+np.arctan2(np.sin(2*np.pi*lam),0.35+np.cos(2*np.pi*lam))/(2*np.pi),1.0)

def parity_indicator(m):
    m=np.asarray(m,float); return np.where(m<0,-1,1)

def bbh_bulk_gap(gamma,lam=1.0):
    gamma=np.asarray(gamma,float); return 2*np.abs(np.abs(lam)-np.abs(gamma))

def bbh_corner_density(L=12,xi=1.4):
    x=np.arange(L); X,Y=np.meshgrid(x,x,indexing="ij")
    c=np.exp(-(X+Y)/xi)+np.exp(-((L-1-X)+Y)/xi)+np.exp(-(X+(L-1-Y))/xi)+np.exp(-((L-1-X)+(L-1-Y))/xi)
    return c/c.sum()

def quadrupole_invariant(gamma,lam=1.0):
    gamma=np.asarray(gamma,float); return np.where(np.abs(gamma)<np.abs(lam),0.5,0.0)

def corner_mode_splitting(perturbation,symmetry_breaking=False):
    x=np.asarray(perturbation,float); return (0.03+0.08*x*x) if not symmetry_breaking else (0.03+0.75*np.abs(x))
