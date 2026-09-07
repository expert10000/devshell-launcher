
"""Commit 638: systematic effective-Hamiltonian engineering."""
from __future__ import annotations
import numpy as np
I=np.eye(2,dtype=complex);X=np.array([[0,1],[1,0]],complex);Y=np.array([[0,-1j],[1j,0]],complex);Z=np.array([[1,0],[0,-1]],complex)
def hermitian_step(H,t):
    w,v=np.linalg.eigh(np.asarray(H,complex));return (v*np.exp(-1j*w*float(t)))@v.conj().T
def exact_two_level(E1,E2,g):
    return np.array([[E1,g],[g,E2]],complex)
def sw_second_order(E1,E2,g):
    d=float(E1-E2)
    if abs(d)<1e-15:raise ValueError("nonzero detuning required")
    return np.diag([E1+g*g/d,E2-g*g/d]).astype(complex)
def sw_error(E1,E2,g):
    a=np.linalg.eigvalsh(exact_two_level(E1,E2,g));b=np.linalg.eigvalsh(sw_second_order(E1,E2,g))
    return float(np.max(np.abs(np.sort(a)-np.sort(b))))
def mediated_exchange(g1,g2,Delta):
    if Delta==0:raise ValueError("Delta must be nonzero")
    return float(g1*g2/Delta)
def dispersive_shift(g,Delta):
    if Delta==0:raise ValueError("Delta must be nonzero")
    return float(g*g/Delta)
def bus_single_excitation_hamiltonian(w1,w2,wr,g1,g2):
    return np.array([[w1,0,g1],[0,w2,g2],[g1,g2,wr]],complex)
def bus_population(state): return float(abs(np.asarray(state,complex)[2])**2)
def evolve(H,psi,t): return hermitian_step(H,t)@np.asarray(psi,complex)
def effective_qubit_block(w1,w2,wr,g1,g2):
    d1=w1-wr;d2=w2-wr
    if abs(d1)<1e-15 or abs(d2)<1e-15:raise ValueError("dispersive denominators must be nonzero")
    J=.5*g1*g2*(1/d1+1/d2)
    return np.array([[w1+g1*g1/d1,J],[J,w2+g2*g2/d2]],complex)
def adiabatic_elimination_population_scale(g,Delta): return float((g/Delta)**2)
def magnus_first_average(Hs,dts):
    Hs=[np.asarray(H,complex) for H in Hs];d=np.asarray(dts,float);T=float(np.sum(d))
    if len(Hs)!=len(d) or T<=0:raise ValueError("invalid segments")
    return sum(H*x for H,x in zip(Hs,d))/T
def commutator(A,B):return np.asarray(A)@np.asarray(B)-np.asarray(B)@np.asarray(A)
def magnus_second_term(Hs,dts):
    Hs=[np.asarray(H,complex) for H in Hs];d=np.asarray(dts,float);T=float(np.sum(d))
    out=np.zeros_like(Hs[0],complex)
    for j in range(len(Hs)):
        for k in range(j):
            out += (-.5j/T)*d[j]*d[k]*commutator(Hs[j],Hs[k])
    return out
def toggling_average(H, pulses):
    H=np.asarray(H,complex);us=[np.asarray(U,complex) for U in pulses]
    return sum(U.conj().T@H@U for U in us)/len(us)
def echoed_zz_average(jzz=1.0):
    H=jzz*np.kron(Z,Z);XI=np.kron(X,I)
    return toggling_average(H,[np.eye(4),XI])
def floquet_two_step(HA,HB,tau):
    return hermitian_step(HB,tau)@hermitian_step(HA,tau)
def quasienergies(U,period):
    vals=np.linalg.eigvals(np.asarray(U,complex));ph=np.angle(vals)
    return np.sort(-ph/float(period))
def exact_effective_state_error(H_exact,H_eff,psi,t):
    a=evolve(H_exact,psi,t);b=evolve(H_eff,psi,t)
    return float(1-abs(np.vdot(a,b))**2)
