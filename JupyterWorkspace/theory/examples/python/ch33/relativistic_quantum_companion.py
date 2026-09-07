from __future__ import annotations
import numpy as np

def gamma_factor(beta): return 1/np.sqrt(1-np.asarray(beta)**2)
def relativistic_energy(p,m=1.0,c=1.0): return np.sqrt((np.asarray(p)*c)**2+(m*c*c)**2)
def velocity_from_p(p,m=1.0,c=1.0): return np.asarray(p)*c*c/relativistic_energy(p,m,c)
def compton_wavelength(m=1.0,hbar=1.0,c=1.0): return hbar/(m*c)
def lower_upper_ratio(p,m=1.0,c=1.0): return np.asarray(p)*c/(relativistic_energy(p,m,c)+m*c*c)
def chirality_mix_scale(m,E): return np.asarray(m)/np.asarray(E)
def fine_structure_shift(n,j,Z=1,alpha=1/137.035999084,m=1.0,c=1.0):
    return -(Z*alpha)**4*m*c*c/(2*n**3)*(1/(j+0.5)-3/(4*n))
def dirac_coulomb_energy(n,j,Z=1,alpha=1/137.035999084,m=1.0,c=1.0):
    d=np.sqrt((j+0.5)**2-(Z*alpha)**2); den=n-j-0.5+d
    return m*c*c/np.sqrt(1+(Z*alpha)**2/den**2)
def boost_current(rho,beta,c=1.0):
    g=gamma_factor(beta); return np.array([g*c*rho,-g*beta*c*rho])
def helicity_boost_flip(v,u):
    vp=(v-u)/(1-u*v); return np.sign(vp)!=np.sign(v)
def pauli_zeeman(B,q=-1.0,m=1.0,hbar=1.0,c=1.0): return abs(q)*hbar*np.asarray(B)/(m*c)
def pair_gap(m=1.0,c=1.0): return 2*m*c*c
def kg_frequency(k,m=1.0,c=1.0,hbar=1.0): return np.sqrt((c*np.asarray(k))**2+(m*c*c/hbar)**2)
def rapidity(beta): return np.arctanh(np.asarray(beta))
def beta_from_rapidity(eta): return np.tanh(np.asarray(eta))
