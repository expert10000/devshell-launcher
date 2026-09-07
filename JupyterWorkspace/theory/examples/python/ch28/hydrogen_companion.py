"""Numerical companion for Chapter 28: the hydrogen atom.

Unless stated otherwise, radial coordinates use reduced-mass Bohr-radius units
and energies use the corresponding hydrogenic Rydberg scale.
"""
from __future__ import annotations
import math
import numpy as np
from scipy.integrate import quad
from scipy.special import eval_genlaguerre, factorial
from scipy.linalg import eigh_tridiagonal
RYDBERG_EV = 13.605693122994
HC_EV_NM = 1239.8419843320026
TOL = 1e-12

def validate_quantum_numbers(n:int,l:int,m:int|None=None)->None:
    if int(n)!=n or n<1: raise ValueError('n must be a positive integer')
    if int(l)!=l or l<0 or l>=n: raise ValueError('l must satisfy 0 <= l < n')
    if m is not None and (int(m)!=m or abs(m)>l): raise ValueError('m must satisfy |m| <= l')

def reduced_mass_ratio(nuclear_mass_in_electron_masses:float)->float:
    M=float(nuclear_mass_in_electron_masses)
    if M<=0: raise ValueError('nuclear mass must be positive')
    return M/(1.0+M)

def bohr_radius_scale(Z:float=1.0,mu_ratio:float=1.0)->float:
    if Z<=0 or mu_ratio<=0: raise ValueError('Z and mu_ratio must be positive')
    return 1.0/(Z*mu_ratio)

def energy_au(n:int,Z:float=1.0,mu_ratio:float=1.0)->float:
    validate_quantum_numbers(n,0)
    return -0.5*mu_ratio*Z**2/n**2

def energy_ev(n:int,Z:float=1.0,mu_ratio:float=1.0)->float:
    return -RYDBERG_EV*mu_ratio*Z**2/n**2

def transition_energy_ev(ni:int,nf:int,Z:float=1.0,mu_ratio:float=1.0)->float:
    if ni==nf: return 0.0
    return abs(energy_ev(ni,Z,mu_ratio)-energy_ev(nf,Z,mu_ratio))

def transition_wavelength_nm(ni:int,nf:int,Z:float=1.0,mu_ratio:float=1.0)->float:
    e=transition_energy_ev(ni,nf,Z,mu_ratio)
    if e<=0: raise ValueError('transition energy must be nonzero')
    return HC_EV_NM/e

def radial(n:int,l:int,r,Z:float=1.0,mu_ratio:float=1.0):
    validate_quantum_numbers(n,l)
    r=np.asarray(r,dtype=float)
    if np.any(r<0): raise ValueError('r must be nonnegative')
    zeff=Z*mu_ratio
    rho=2.0*zeff*r/n
    pref=(2.0*zeff/n)**1.5*math.sqrt(float(factorial(n-l-1,exact=True))/(2.0*n*float(factorial(n+l,exact=True))))
    return pref*np.exp(-rho/2.0)*rho**l*eval_genlaguerre(n-l-1,2*l+1,rho)

def radial_probability(n:int,l:int,r,Z:float=1.0,mu_ratio:float=1.0):
    rr=np.asarray(r,dtype=float)
    return rr**2*np.abs(radial(n,l,rr,Z,mu_ratio))**2

def radial_normalization(n:int,l:int,Z:float=1.0,mu_ratio:float=1.0)->float:
    f=lambda x: float(radial_probability(n,l,x,Z,mu_ratio))
    return quad(f,0,np.inf,epsabs=2e-11,epsrel=2e-11,limit=300)[0]

def radial_overlap(n1:int,l1:int,n2:int,l2:int,Z:float=1.0,mu_ratio:float=1.0)->float:
    if l1!=l2: return 0.0
    f=lambda x: float(radial(n1,l1,x,Z,mu_ratio)*radial(n2,l2,x,Z,mu_ratio)*x*x)
    return quad(f,0,np.inf,epsabs=2e-10,epsrel=2e-10,limit=300)[0]

def radial_dipole_integral(n1:int,l1:int,n2:int,l2:int,Z:float=1.0,mu_ratio:float=1.0)->float:
    f=lambda x: float(radial(n1,l1,x,Z,mu_ratio)*radial(n2,l2,x,Z,mu_ratio)*x**3)
    return quad(f,0,np.inf,epsabs=2e-9,epsrel=2e-9,limit=400)[0]

def expectation_r(n:int,l:int,Z:float=1.0,mu_ratio:float=1.0)->float:
    validate_quantum_numbers(n,l); a=bohr_radius_scale(Z,mu_ratio)
    return 0.5*a*(3*n*n-l*(l+1))

def expectation_r2(n:int,l:int,Z:float=1.0,mu_ratio:float=1.0)->float:
    validate_quantum_numbers(n,l); a=bohr_radius_scale(Z,mu_ratio)
    return 0.5*a*a*n*n*(5*n*n+1-3*l*(l+1))

def expectation_inv_r(n:int,l:int,Z:float=1.0,mu_ratio:float=1.0)->float:
    validate_quantum_numbers(n,l)
    return Z*mu_ratio/(n*n)

def virial_components_ev(n:int,Z:float=1.0,mu_ratio:float=1.0):
    E=energy_ev(n,Z,mu_ratio)
    return -E,2*E

def radial_nodes(n:int,l:int)->int:
    validate_quantum_numbers(n,l); return n-l-1

def angular_nodes(l:int)->int:
    if int(l)!=l or l<0: raise ValueError('l must be nonnegative integer')
    return l

def shell_degeneracy(n:int,include_spin:bool=False)->int:
    validate_quantum_numbers(n,0); return n*n*(2 if include_spin else 1)

def dipole_allowed(li:int,mi:int,lf:int,mf:int)->bool:
    validate_quantum_numbers(max(li+1,1),li,mi);validate_quantum_numbers(max(lf+1,1),lf,mf)
    return abs(lf-li)==1 and abs(mf-mi)<=1

def cumulative_radial_probability(n:int,l:int,R:float,Z:float=1.0,mu_ratio:float=1.0)->float:
    if R<0: raise ValueError('R must be nonnegative')
    f=lambda x: float(radial_probability(n,l,x,Z,mu_ratio))
    return quad(f,0,R,epsabs=2e-10,epsrel=2e-10,limit=300)[0]

def most_probable_radius(n:int,l:int,Z:float=1.0,mu_ratio:float=1.0,points:int=20000)->float:
    rmax=max(20.0,8.0*n*n)*bohr_radius_scale(Z,mu_ratio)
    r=np.linspace(0,rmax,points)
    return float(r[np.argmax(radial_probability(n,l,r,Z,mu_ratio))])

def finite_difference_s_energies(grid_points:int=1800,rmax:float=120.0,levels:int=4,Z:float=1.0):
    if grid_points<100 or rmax<=0 or levels<1: raise ValueError('invalid grid')
    h=rmax/(grid_points+1); r=h*np.arange(1,grid_points+1)
    diag=1.0/h**2-Z/r
    off=np.full(grid_points-1,-0.5/h**2)
    vals=eigh_tridiagonal(diag,off,select='i',select_range=(0,levels-1),check_finite=False)[0]
    return vals
