"""Commit 650: compact MPS/DMRG reference diagnostics."""
from __future__ import annotations
import numpy as np

def schmidt_probabilities(q=0.72,n=80):
    x=q**np.arange(n,dtype=float); return x/x.sum()

def discarded_weight(chi,q=0.72,n=80):
    p=schmidt_probabilities(q,n); return float(p[int(chi):].sum())

def entropy_from_probabilities(p,base=2):
    p=np.asarray(p,float); p=p[p>0]
    return float(-(p*np.log(p)).sum()/np.log(base))

def entropy_bound(chi,base=2):
    return float(np.log(chi)/np.log(base))

def mps_parameter_count(L,d=2,chi=32):
    if L<2: return d
    return int(2*d*chi+(L-2)*d*chi*chi)

def full_state_dimension(L,d=2): return int(d**L)

def contraction_cost_proxy(L,d=2,chi=32): return float(L*d*d*chi**3)

def variational_energy_error(chi,a=1.0,p=2.2,floor=1e-8):
    chi=np.asarray(chi,float); return floor+a/(chi**p)

def dmrg_sweep_energy_error(sweep,chi=64):
    sweep=np.asarray(sweep,float)
    return np.exp(-0.9*sweep)+1/(chi**2.2)

def correlation_profile(r,chi,xi_exact=25.0):
    r=np.asarray(r,float)
    xi_eff=min(xi_exact,0.8*chi)
    return np.exp(-r/xi_eff)

def state_to_mps(psi,n_sites,d=2,max_bond=None):
    psi=np.asarray(psi,complex).reshape([d]*n_sites)
    tensors=[]; discarded=0.0; left=1; rest=psi
    for site in range(n_sites-1):
        mat=rest.reshape(left*d,-1)
        U,S,Vh=np.linalg.svd(mat,full_matrices=False)
        keep=len(S) if max_bond is None else min(int(max_bond),len(S))
        discarded += float(np.sum(S[keep:]**2))
        U=U[:,:keep]; S=S[:keep]; Vh=Vh[:keep,:]
        tensors.append(U.reshape(left,d,keep))
        rest=(S[:,None]*Vh)
        left=keep
    tensors.append(rest.reshape(left,d,1))
    return tensors,discarded

def mps_to_state(tensors):
    x=tensors[0]
    for A in tensors[1:]:
        x=np.tensordot(x,A,axes=([-1],[0]))
    return np.squeeze(x,axis=(0,-1)).reshape(-1)

def normalized_fidelity(a,b):
    a=np.asarray(a,complex).reshape(-1); b=np.asarray(b,complex).reshape(-1)
    a=a/np.linalg.norm(a); b=b/np.linalg.norm(b)
    return float(abs(np.vdot(a,b))**2)
