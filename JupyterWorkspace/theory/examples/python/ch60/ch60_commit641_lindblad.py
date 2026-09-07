
"""Commit 641: Markovian master equations, Lindblad dynamics, and Liouvillian diagnostics."""
from __future__ import annotations
import numpy as np
I=np.eye(2,dtype=complex)
X=np.array([[0,1],[1,0]],complex)
Y=np.array([[0,-1j],[1j,0]],complex)
Z=np.array([[1,0],[0,-1]],complex)
SM=np.array([[0,1],[0,0]],complex)
SP=SM.conj().T

def lindblad_superoperator(H,jumps):
    H=np.asarray(H,complex);d=H.shape[0];Id=np.eye(d,dtype=complex)
    L=-1j*(np.kron(Id,H)-np.kron(H.T,Id))
    for J in jumps:
        J=np.asarray(J,complex);A=J.conj().T@J
        L += np.kron(J.conj(),J)-.5*np.kron(Id,A)-.5*np.kron(A.T,Id)
    return L

def vec(rho):return np.asarray(rho,complex).reshape(-1,order="F")
def unvec(v,d=2):return np.asarray(v,complex).reshape((d,d),order="F")

def evolve_liouvillian(rho0,L,t):
    L=np.asarray(L,complex);w,v=np.linalg.eig(L);vinv=np.linalg.inv(v)
    out=v@(np.exp(w*float(t))*(vinv@vec(rho0)))
    r=unvec(out,int(round(np.sqrt(len(out)))))
    return .5*(r+r.conj().T)

def amplitude_damping_liouvillian(gamma,H=None):
    if H is None:H=np.zeros((2,2),complex)
    return lindblad_superoperator(H,[np.sqrt(float(gamma))*SM])

def dephasing_liouvillian(gamma_phi,H=None):
    if H is None:H=np.zeros((2,2),complex)
    return lindblad_superoperator(H,[np.sqrt(float(gamma_phi)/2)*Z])

def driven_qubit_liouvillian(Omega,Delta,gamma1=0.0,gamma_phi=0.0):
    H=.5*float(Omega)*X+.5*float(Delta)*Z;j=[]
    if gamma1>0:j.append(np.sqrt(gamma1)*SM)
    if gamma_phi>0:j.append(np.sqrt(gamma_phi/2)*Z)
    return lindblad_superoperator(H,j)

def bloch(rho):
    r=np.asarray(rho,complex)
    return np.array([np.trace(r@X).real,np.trace(r@Y).real,np.trace(r@Z).real])

def t2_from_rates(gamma1,gamma_phi):
    rate=.5*float(gamma1)+float(gamma_phi)
    return np.inf if rate==0 else 1/rate

def t1_from_rate(gamma1):
    g=float(gamma1);return np.inf if g==0 else 1/g

def thermal_rates(gamma,beta_omega):
    gd=float(gamma);gu=gd*np.exp(-float(beta_omega));return gd,gu

def thermal_liouvillian(gamma,beta_omega,H=None):
    if H is None:H=-.5*Z
    gd,gu=thermal_rates(gamma,beta_omega)
    return lindblad_superoperator(H,[np.sqrt(gd)*SM,np.sqrt(gu)*SP])

def steady_state(L,d=2):
    w,v=np.linalg.eig(np.asarray(L,complex));i=int(np.argmin(np.abs(w)))
    r=unvec(v[:,i],d);r=.5*(r+r.conj().T);tr=np.trace(r)
    if abs(tr)<1e-14:raise ValueError("steady-state eigenvector has zero trace")
    r=r/tr
    vals,U=np.linalg.eigh(r);vals=np.clip(vals.real,0,None);r=(U*vals)@U.conj().T;r=r/np.trace(r)
    return r

def liouvillian_eigenvalues(L):return np.linalg.eigvals(np.asarray(L,complex))

def liouvillian_gap(L,tol=1e-9):
    ev=liouvillian_eigenvalues(L)
    rates=[-x.real for x in ev if abs(x)>tol and -x.real>tol]
    return float(min(rates)) if rates else 0.0

def purity(rho):r=np.asarray(rho,complex);return float(np.trace(r@r).real)

def positivity_min_eigenvalue(rho):return float(np.min(np.linalg.eigvalsh(np.asarray(rho,complex)).real))

def trace_preservation_residual(L,d=2):
    ident=np.eye(d,dtype=complex)
    # Trace preservation means vec(I)^† L = 0 in column vectorization.
    return float(np.linalg.norm(vec(ident).conj().T@np.asarray(L,complex)))

def exact_exchange_population(g,times):
    t=np.asarray(times,float);return np.cos(float(g)*t)**2

def markov_population(gamma,times):
    return np.exp(-float(gamma)*np.asarray(times,float))
