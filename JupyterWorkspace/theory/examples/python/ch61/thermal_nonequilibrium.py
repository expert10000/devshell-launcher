"""Commit 651: equilibrium and nonequilibrium finite-many-body diagnostics."""
from __future__ import annotations
import numpy as np

def thermal_probabilities(energies,beta):
    E=np.asarray(energies,float); x=-beta*(E-E.min()); w=np.exp(x); return w/w.sum()

def mean_energy(energies,beta):
    E=np.asarray(energies,float); p=thermal_probabilities(E,beta); return float(np.sum(p*E))

def free_energy(energies,beta):
    E=np.asarray(energies,float)
    if beta==0: return -np.inf
    Emin=E.min(); z=np.exp(-beta*(E-Emin)).sum()
    return float(Emin-np.log(z)/beta)

def heat_capacity(energies,beta,kB=1.0):
    E=np.asarray(energies,float); p=thermal_probabilities(E,beta)
    return float(kB*beta*beta*(np.sum(p*E*E)-np.sum(p*E)**2))

def susceptibility(values,beta,kB=1.0):
    M=np.asarray(values,float); p=np.ones(len(M))/len(M)
    return float(beta*(np.sum(p*M*M)-np.sum(p*M)**2))

def loschmidt_amplitude(energies,weights,t):
    E=np.asarray(energies,float); w=np.asarray(weights,float); w=w/w.sum()
    t=np.asarray(t,float)
    return np.sum(w[:,None]*np.exp(-1j*E[:,None]*t[None,:]),axis=0)

def survival_probability(energies,weights,t):
    return np.abs(loschmidt_amplitude(energies,weights,t))**2

def entanglement_growth(t,v=0.7,Smax=4.0):
    t=np.asarray(t,float); return np.minimum(v*np.maximum(t,0),Smax)

def light_cone(r,t,v=1.4,xi=0.8):
    r=np.asarray(r,float); t=np.asarray(t,float)
    return np.exp(-np.maximum(np.abs(r)-v*t,0)/xi)

def lorentzian_spectrum(omega,lines,weights,eta=0.08):
    o=np.asarray(omega,float); lines=np.asarray(lines,float); weights=np.asarray(weights,float)
    d=o[:,None]-lines[None,:]
    return np.sum(weights[None,:]*(eta/np.pi)/(d*d+eta*eta),axis=1)

def eth_diagonal(energy,seed=1,noise=0.08):
    E=np.asarray(energy,float); rng=np.random.default_rng(seed)
    smooth=np.tanh(E/3)
    return smooth+rng.normal(scale=noise,size=E.shape)

def poisson_spacing_pdf(s): 
    s=np.asarray(s,float); return np.exp(-s)

def wigner_spacing_pdf(s):
    s=np.asarray(s,float); return 0.5*np.pi*s*np.exp(-np.pi*s*s/4)

def spacing_ratios(levels):
    e=np.sort(np.asarray(levels,float)); d=np.diff(e)
    if len(d)<2: return np.array([])
    return np.minimum(d[:-1],d[1:])/np.maximum(d[:-1],d[1:])

def thermal_correlation_length(T,xi0=8.0,T0=.5):
    T=np.asarray(T,float); return xi0/(1+T/T0)
