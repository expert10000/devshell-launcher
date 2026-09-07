from __future__ import annotations
import math,numpy as np
from many_body_launch import hubbard_matrix,bose_two_site_matrix
def hubbard_ground_state(U,t=1.):
 H,basis=hubbard_matrix(2,t=t,U=U,N=2); vals,vecs=np.linalg.eigh(H); return vals[0],basis,vecs[:,0]
def double_occupancy(U,t=1.):
 _,basis,psi=hubbard_ground_state(U,t); out=0.
 for amp,s in zip(psi,basis):
  d=sum(((s>>(2*i))&1)*((s>>(2*i+1))&1) for i in range(2)); out+=abs(amp)**2*d
 return float(out)
def bose_number_variance(U,J=1.,N=4):
 H=bose_two_site_matrix(N,J,U); vals,vecs=np.linalg.eigh(H); p=np.abs(vecs[:,0])**2; n=np.arange(N+1); m=np.sum(n*p); return float(np.sum((n-m)**2*p))
def finite_gap_schematic(U):
 U=np.asarray(U,float); return np.sqrt(.4**2+(U-3)**2)*.18,np.sqrt(.25**2+(U+1)**2)*.12,np.sqrt(.3**2+(U+3)**2)*.10
def structure_factor_proxy(U,k=np.pi): U=np.asarray(U,float); return (1+np.tanh(U/2))/2*(1-np.cos(k))/2
def binary_entropy(p): p=np.clip(np.asarray(p,float),1e-15,1-1e-15); return -(p*np.log2(p)+(1-p)*np.log2(1-p))
def entanglement_entropy_proxy(U): U=np.asarray(U,float); return binary_entropy(.5*(1+np.tanh(U/3)))
def fidelity_susceptibility_proxy(U,Uc=.5,width=.35): U=np.asarray(U,float); return 1/(width**2+(U-Uc)**2)
def finite_size_gap(L,critical=True): L=np.asarray(L,float); return 1/L if critical else .4+1/L
def symmetry_block_dimensions(n_sites):
 total=4**n_sites; central=math.comb(2*n_sites,n_sites); momentum=max(1,central//n_sites); parity=max(1,momentum//2); return total,central,momentum,parity
def pair_correlation_distance(r,xi=3.,ordered=False): r=np.asarray(r,float); return .2+.8*np.exp(-r/xi) if ordered else np.exp(-r/xi)
def ed_dimension(n_modes,N=None): return 2**n_modes if N is None else math.comb(n_modes,N)
