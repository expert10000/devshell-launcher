"""Numerical companion for Chapter 34: Introduction to Quantum Field Theory.
Natural units hbar=c=1 are used throughout.
"""
from __future__ import annotations
import math
import numpy as np

def relativistic_energy(p, m):
    p=np.asarray(p,dtype=float); return np.sqrt(p*p+m*m)

def bose_occupation(E,T,mu=0.0):
    x=(np.asarray(E,dtype=float)-mu)/T
    return 1.0/np.expm1(x)

def fermi_occupation(E,T,mu=0.0):
    x=(np.asarray(E,dtype=float)-mu)/T
    return 1.0/(np.exp(x)+1.0)

def scalar_propagator(p0,p,m,eps=1e-6):
    p2=np.asarray(p,dtype=float)**2
    return 1.0/(p0*p0-p2-m*m+1j*eps)

def dirac_scalar_denominator(p0,p,m,eps=1e-6):
    """Denominator shared by every component of the free Dirac propagator."""
    return scalar_propagator(p0,p,m,eps)

def equal_time_yukawa_correlation(r,m):
    r=np.asarray(r,dtype=float)
    return np.exp(-m*r)/(4.0*np.pi*np.maximum(r,1e-12))

def dyson_exponential_partial(g,t,order):
    z=-1j*g*t
    return sum(z**n/math.factorial(n) for n in range(order+1))

def wick_pairing_count(n):
    if n<0 or n%2: return 0
    if n==0: return 1
    out=1
    for k in range(n-1,0,-2): out*=k
    return out

def phi4_tree_amplitude(lam):
    return -float(lam)

def kallen(x,y,z):
    return x*x+y*y+z*z-2*x*y-2*x*z-2*y*z

def two_body_cm_momentum(s,m1,m2):
    val=kallen(s,m1*m1,m2*m2)
    return math.sqrt(max(val,0.0))/(2.0*math.sqrt(s))

def two_body_phase_space(s,m1,m2):
    return two_body_cm_momentum(s,m1,m2)/(4.0*math.pi*math.sqrt(s))

def invariant_interval(t,r):
    return t*t-r*r

def microcausal_spacelike(t,r):
    return invariant_interval(t,r)<0

def boson_number_spectrum(nmax):
    return np.arange(nmax+1,dtype=int)

def fermion_number_spectrum():
    return np.array([0,1],dtype=int)

def scalar_zero_point_energy(omega,nmodes=1):
    return 0.5*float(omega)*int(nmodes)

def charged_state_charge(nplus,nminus,q=1.0):
    return q*(nplus-nminus)

def connected_tree_loops(vertices,internal_lines):
    return internal_lines-vertices+1

def phi4_vertex_count(external_legs,loops=0):
    # For connected phi^4 graphs: 4V=2I+E and L=I-V+1.
    num=external_legs+2*loops-2
    if num<0 or num%2: raise ValueError('incompatible graph data')
    return num//2
