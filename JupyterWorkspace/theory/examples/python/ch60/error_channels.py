"""Commit 644 channel, spectroscopy, mitigation, and sensing diagnostics."""
from __future__ import annotations
import numpy as np

I=np.eye(2,dtype=complex)
X=np.array([[0,1],[1,0]],complex)
Y=np.array([[0,-1j],[1j,0]],complex)
Z=np.array([[1,0],[0,-1]],complex)
PAULI=(I,X,Y,Z)

def pauli_channel(rho, probs):
    p=np.asarray(probs,float)
    if p.shape!=(4,) or np.any(p<0) or not np.isclose(p.sum(),1): raise ValueError("probs")
    return sum(pi*(P@rho@P) for pi,P in zip(p,PAULI))

def entanglement_fidelity_pauli(probs):
    # For a Pauli channel relative to identity, Fe equals identity-Pauli weight.
    p=np.asarray(probs,float)
    return float(p[0])

def average_gate_fidelity_from_entanglement(Fe, d=2):
    return float((d*Fe+1)/(d+1))

def compose_pauli(p,q):
    """Convolution on the Pauli group modulo phase."""
    mult=np.array([[0,1,2,3],[1,0,3,2],[2,3,0,1],[3,2,1,0]])
    out=np.zeros(4)
    for i in range(4):
        for j in range(4):
            out[mult[i,j]] += p[i]*q[j]
    return out

def repeated_depolarizing_error(p, depth):
    # rho -> (1-p)rho + p I/2, so Bloch length shrinks by (1-p)^depth.
    return 1-(1-p)**depth

def correlated_dephasing_density(t, gamma=1.0, rho_c=0.8):
    """Two-qubit coherence factors for common + differential Gaussian phase noise."""
    t=np.asarray(t,float)
    common=np.exp(-gamma*(1+rho_c)*t)
    differential=np.exp(-gamma*(1-rho_c)*t)
    return common,differential

def collective_decay_rates(gamma=1.0):
    # In one-excitation Dicke basis: bright |S> decays at 2 gamma, dark |A> at 0.
    return {"symmetric":2*gamma,"antisymmetric":0.0}

def lorentzian_psd(omega, amplitude=1.0, tau_c=0.4):
    omega=np.asarray(omega,float)
    return 2*amplitude*tau_c/(1+(omega*tau_c)**2)

def ramsey_coherence(t, T2star=1.0):
    t=np.asarray(t,float); return np.exp(-(t/T2star)**2)

def echo_coherence(t, T2echo=2.0):
    t=np.asarray(t,float); return np.exp(-(t/T2echo)**3)

def zne_extrapolate(scales, values, order=1):
    scales=np.asarray(scales,float); values=np.asarray(values,float)
    coef=np.polyfit(scales,values,order)
    return float(np.polyval(coef,0.0))

def pec_sampling_overhead(error_rate, depth):
    if not (0<=error_rate<0.5): raise ValueError("error_rate")
    return float((1/(1-2*error_rate))**(2*depth))

def dephasing_fisher_information(t, omega=1.0, T2=1.0):
    """Classical FI of an optimally phased Ramsey readout, up to one-shot scale."""
    t=np.asarray(t,float)
    return t**2*np.exp(-2*t/T2)

def t1_t2_limited_coherence(t,T1,Tphi):
    t=np.asarray(t,float)
    T2=1/(1/(2*T1)+1/Tphi)
    return np.exp(-t/T2), T2

def diamond_upper_bound_pauli(probs):
    """For Pauli noise vs identity, a simple exact l1 probability expression."""
    p=np.asarray(probs,float)
    return float(2*(1-p[0]))
