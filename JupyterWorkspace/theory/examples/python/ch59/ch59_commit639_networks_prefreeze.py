
"""Commit 639: few-qubit networks, crosstalk, entanglement propagation and pre-freeze diagnostics."""
from __future__ import annotations
import numpy as np
I=np.eye(2,dtype=complex);X=np.array([[0,1],[1,0]],complex);Y=np.array([[0,-1j],[1j,0]],complex);Z=np.array([[1,0],[0,-1]],complex)

def op_on(op,site,n):
    mats=[I]*n;mats=list(mats);mats[int(site)]=op
    out=mats[0]
    for m in mats[1:]:out=np.kron(out,m)
    return out

def two_site(a,i,b,j,n):
    mats=[I]*n;mats=list(mats);mats[int(i)]=a;mats[int(j)]=b
    out=mats[0]
    for m in mats[1:]:out=np.kron(out,m)
    return out

def graph_hamiltonian(n, edges, model="xy"):
    H=np.zeros((2**n,2**n),complex)
    for i,j,J in edges:
        if model=="xy": H += .5*J*(two_site(X,i,X,j,n)+two_site(Y,i,Y,j,n))
        elif model=="ising": H += J*two_site(Z,i,Z,j,n)
        elif model=="heisenberg": H += .25*J*(two_site(X,i,X,j,n)+two_site(Y,i,Y,j,n)+two_site(Z,i,Z,j,n))
        else: raise ValueError("unknown model")
    return H

def excitation_number(n):
    H=np.zeros((2**n,2**n),complex)
    for i in range(n):H += .5*(np.eye(2**n)-op_on(Z,i,n))
    return H

def basis_state(bits):
    idx=int(bits,2) if isinstance(bits,str) else int(bits)
    n=len(bits) if isinstance(bits,str) else max(1,int(np.ceil(np.log2(idx+1))))
    v=np.zeros(2**n,complex);v[idx]=1;return v

def basis_index(bits):return int(bits,2)

def hermitian_step(H,t):
    w,v=np.linalg.eigh(np.asarray(H,complex));return (v*np.exp(-1j*w*float(t)))@v.conj().T
def evolve(H,psi,t):return hermitian_step(H,t)@np.asarray(psi,complex)

def single_excitation_matrix(n,edges):
    M=np.zeros((n,n),float)
    for i,j,J in edges:M[i,j]+=J;M[j,i]+=J
    return M

def single_excitation_probabilities(n,edges,start,times):
    M=single_excitation_matrix(n,edges);psi=np.zeros(n,complex);psi[start]=1
    out=[]
    for t in np.asarray(times,float):
        out.append(np.abs(hermitian_step(M,t)@psi)**2)
    return np.asarray(out)

def ghz_state(n):
    v=np.zeros(2**n,complex);v[0]=1/np.sqrt(2);v[-1]=1/np.sqrt(2);return v

def reduced_density_one(psi,site,n):
    arr=np.asarray(psi,complex).reshape([2]*n)
    order=[site]+[i for i in range(n) if i!=site]
    A=np.transpose(arr,order).reshape(2,-1)
    return A@A.conj().T

def entropy_one(psi,site,n):
    vals=np.linalg.eigvalsh(reduced_density_one(psi,site,n)).real
    vals=np.clip(vals,0,1);nz=vals[vals>1e-15]
    return float(-np.sum(nz*np.log2(nz)))

def residual_zz_matrix(n, edges):
    H=np.zeros((2**n,2**n),complex)
    for i,j,J in edges:H+=J*two_site(Z,i,Z,j,n)
    return H

def crosstalk_phase(J,T):return float(J)*np.asarray(T,dtype=float)

def spectral_gap(H):
    e=np.sort(np.linalg.eigvalsh(np.asarray(H,complex)).real)
    return float(e[1]-e[0]) if len(e)>1 else 0.0

def hilbert_dimension(n):return 2**int(n)

def interaction_adjacency(n,edges):
    A=np.zeros((n,n),float)
    for i,j,J in edges:A[i,j]=A[j,i]=J
    return A

def refocused_average(H, toggles):
    us=[np.asarray(U,complex) for U in toggles]
    return sum(U.conj().T@H@U for U in us)/len(us)

def three_body_zzz(n=3,J=1.0):
    if n<3:raise ValueError("n must be >=3")
    return J*two_site(Z,0,Z,1,n)@op_on(Z,2,n)

def state_fidelity(a,b):return float(abs(np.vdot(np.asarray(a,complex),np.asarray(b,complex)))**2)
