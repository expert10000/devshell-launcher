"""Commit 645 finite-Fock-space and pairing diagnostics."""
from __future__ import annotations
import itertools, math, numpy as np

def fock_dimension(n_modes,n_particles=None):
    return 2**n_modes if n_particles is None else math.comb(n_modes,n_particles)

def fermion_basis(n_modes,n_particles):
    return [s for s in range(1<<n_modes) if s.bit_count()==n_particles]

def fermion_sign(state,mode):
    return -1 if (state & ((1<<mode)-1)).bit_count()%2 else 1

def apply_cdag_c(state,i,j):
    if not (state>>j)&1 or (state>>i)&1: return None,0
    s1=fermion_sign(state,j); st=state^(1<<j)
    s2=fermion_sign(st,i); st|=(1<<i)
    return st,s1*s2

def hubbard_matrix(L,t=1.0,U=4.0,N=2,periodic=False):
    """Spinful Hubbard chain with modes (site,spin) -> 2*site+spin."""
    basis=fermion_basis(2*L,N); idx={s:k for k,s in enumerate(basis)}
    H=np.zeros((len(basis),len(basis)),float)
    for a,s in enumerate(basis):
        for site in range(L):
            nup=(s>>(2*site))&1; ndn=(s>>(2*site+1))&1
            H[a,a]+=U*nup*ndn
        bonds=[(i,i+1) for i in range(L-1)]
        if periodic and L>2: bonds.append((L-1,0))
        for i,j in bonds:
            for spin in (0,1):
                for src,dst in ((2*j+spin,2*i+spin),(2*i+spin,2*j+spin)):
                    st,sgn=apply_cdag_c(s,dst,src)
                    if st is not None: H[idx[st],a]+=-t*sgn
    return H,basis

def tight_binding_spectrum(L,t=1.0,periodic=True):
    if periodic:
        k=2*np.pi*np.arange(L)/L
        return np.sort(-2*t*np.cos(k))
    m=np.arange(1,L+1)
    return -2*t*np.cos(np.pi*m/(L+1))

def bose_two_site_matrix(N,J=1.0,U=1.0):
    # basis |n,N-n>, n=0..N
    H=np.zeros((N+1,N+1),float)
    for n in range(N+1):
        m=N-n
        H[n,n]=0.5*U*(n*(n-1)+m*(m-1))
        if n<N:
            amp=-J*np.sqrt((n+1)*m)
            H[n+1,n]=H[n,n+1]=amp
    return H

def bose_ground_probabilities(N=2,J=1.0,U=1.0):
    H=bose_two_site_matrix(N,J,U)
    vals,vecs=np.linalg.eigh(H)
    p=np.abs(vecs[:,0])**2
    return vals[0],p

def ground_energy_hubbard(L,N,t=1.0,U=0.0):
    H,_=hubbard_matrix(L,t,U,N)
    return float(np.linalg.eigvalsh(H)[0]) if H.size else 0.0

def pair_binding_energy(L=2,t=1.0,U=-2.0):
    # Delta_pair = E2 + E0 - 2 E1; negative means bound pair.
    return ground_energy_hubbard(L,2,t,U)+ground_energy_hubbard(L,0,t,U)-2*ground_energy_hubbard(L,1,t,U)

def particle_number_blocks(n_modes):
    return np.array([math.comb(n_modes,N) for N in range(n_modes+1)],int)

def reduced_bcs_matrix(level_energies,g=0.4,npairs=1):
    """Hard-core pair basis for the reduced BCS Hamiltonian."""
    eps=np.asarray(level_energies,float); M=len(eps)
    basis=[tuple(c) for c in itertools.combinations(range(M),npairs)]
    H=np.zeros((len(basis),len(basis)),float)
    for a,occ in enumerate(basis):
        H[a,a]=2*sum(eps[i] for i in occ)-g*npairs
        occset=set(occ)
        for j in occ:
            for i in range(M):
                if i in occset: continue
                new=tuple(sorted((occset-{j})|{i}))
                b=basis.index(new)
                H[b,a]+=-g
    return H,basis
