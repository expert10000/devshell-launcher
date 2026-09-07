"""Computational companion for Chapter 45: Topological Insulators.

The module uses a minimal four-band time-reversal-symmetric lattice Dirac model

    H(k) = sin(kx) tau_x s_z + sin(ky) tau_y
           + (m + cos(kx) + cos(ky)) tau_z + H_R,

with spinful time reversal Theta = i s_y K.  At zero Rashba coupling the two spin
blocks are time-reversed Chern insulators; for |m|<2 (away from m=0) the model is
Z2-nontrivial.  The routines deliberately separate invariant diagnostics from
finite-size and boundary acceptance models used in the chapter.
"""
from __future__ import annotations
import numpy as np

PI=np.pi
I2=np.eye(2,dtype=complex)
sx=np.array([[0,1],[1,0]],dtype=complex)
sy=np.array([[0,-1j],[1j,0]],dtype=complex)
sz=np.array([[1,0],[0,-1]],dtype=complex)
tx,ty,tz=sx.copy(),sy.copy(),sz.copy()
TR_UNITARY=np.kron(I2,1j*sy)
INVERSION=np.kron(tz,I2)


def qsh_hamiltonian(kx:float,ky:float,m:float=-1.0,rashba:float=0.0)->np.ndarray:
    """Four-band lattice BHZ/QSH Hamiltonian in orbital x spin basis."""
    H=(np.sin(kx)*np.kron(tx,sz)+np.sin(ky)*np.kron(ty,I2)
       +(m+np.cos(kx)+np.cos(ky))*np.kron(tz,I2))
    if rashba:
        H=H+rashba*(np.sin(ky)*np.kron(tx,sx)-np.sin(kx)*np.kron(tx,sy))
    return H


def tr_transform(H:np.ndarray)->np.ndarray:
    return TR_UNITARY@H.conj()@TR_UNITARY.conj().T


def time_reversal_error(kx:float,ky:float,**params)->float:
    return float(np.linalg.norm(tr_transform(qsh_hamiltonian(kx,ky,**params))-qsh_hamiltonian(-kx,-ky,**params)))


def occupied_frame(kx:float,ky:float,**params)->np.ndarray:
    e,v=np.linalg.eigh(qsh_hamiltonian(kx,ky,**params))
    return v[:,:2]


def spectrum(kx:float,ky:float,**params)->np.ndarray:
    return np.linalg.eigvalsh(qsh_hamiltonian(kx,ky,**params))


def bulk_gap(n:int=61,**params)->float:
    g=np.inf
    for i in range(n):
        kx=-PI+2*PI*i/n
        for j in range(n):
            ky=-PI+2*PI*j/n
            e=spectrum(kx,ky,**params)
            g=min(g,e[2]-e[1])
    return float(g)


def trim_mass(kx:float,ky:float,m:float)->float:
    return float(m+np.cos(kx)+np.cos(ky))


def parity_delta(kx:float,ky:float,m:float)->int:
    """Parity of the occupied Kramers pair at a TRIM for the inversion-symmetric model."""
    d=trim_mass(kx,ky,m)
    if abs(d)<1e-12: return 0
    return int(-np.sign(d))


def parity_z2(m:float)->int|None:
    ds=[parity_delta(0,0,m),parity_delta(PI,0,m),parity_delta(0,PI,m),parity_delta(PI,PI,m)]
    if 0 in ds: return None
    prod=int(np.prod(ds))
    return 0 if prod==1 else 1


def _spin_up_h(kx:float,ky:float,m:float=-1.0)->np.ndarray:
    d=np.array([np.sin(kx),np.sin(ky),m+np.cos(kx)+np.cos(ky)])
    return d[0]*tx+d[1]*ty+d[2]*tz


def _lower_state_2(h:np.ndarray)->np.ndarray:
    _,v=np.linalg.eigh(h); return v[:,0]


def _link(z:complex)->complex:
    if abs(z)<1e-14: raise ValueError('singular link')
    return z/abs(z)


def spin_block_chern(n:int=31,m:float=-1.0,random_gauge_seed:int|None=None)->float:
    st=np.empty((n,n,2),complex)
    rng=np.random.default_rng(random_gauge_seed) if random_gauge_seed is not None else None
    for i in range(n):
        kx=-PI+2*PI*i/n
        for j in range(n):
            ky=-PI+2*PI*j/n
            u=_lower_state_2(_spin_up_h(kx,ky,m))
            if rng is not None: u=u*np.exp(1j*rng.uniform(-PI,PI))
            st[i,j]=u
    total=0.0
    for i in range(n):
        ip=(i+1)%n
        for j in range(n):
            jp=(j+1)%n
            u00,u10,u11,u01=st[i,j],st[ip,j],st[ip,jp],st[i,jp]
            loop=_link(np.vdot(u00,u10))*_link(np.vdot(u10,u11))*_link(np.vdot(u11,u01))*_link(np.vdot(u01,u00))
            total+=np.angle(loop)
    return float(total/(2*PI))


def spin_chern_z2(n:int=31,m:float=-1.0)->int:
    c=int(round(spin_block_chern(n,m)))
    return abs(c)%2


def _unitary_part(M:np.ndarray)->np.ndarray:
    u,_,vh=np.linalg.svd(M)
    return u@vh


def wilson_phases(ky:float,nkx:int=81,m:float=-1.0,rashba:float=0.0,random_gauge_seed:int|None=None)->np.ndarray:
    """Eigenphases of the occupied-subspace Wilson loop along kx at fixed ky."""
    frames=[]; rng=np.random.default_rng(random_gauge_seed) if random_gauge_seed is not None else None
    for i in range(nkx):
        kx=-PI+2*PI*i/nkx
        V=occupied_frame(kx,ky,m=m,rashba=rashba)
        if rng is not None:
            z=rng.normal(size=(2,2))+1j*rng.normal(size=(2,2))
            q,r=np.linalg.qr(z); d=np.diag(r); q=q@(np.diag(np.exp(-1j*np.angle(d))))
            V=V@q
        frames.append(V)
    W=np.eye(2,dtype=complex)
    for i in range(nkx):
        A=frames[i].conj().T@frames[(i+1)%nkx]
        W=W@_unitary_part(A)
    ph=np.sort(np.angle(np.linalg.eigvals(W)))
    return ph


def kramers_pair_splitting(kx:float,ky:float,**params)->float:
    e=spectrum(kx,ky,**params)
    return float(max(abs(e[1]-e[0]),abs(e[3]-e[2])))


def helical_edge_energies(k,velocity:float=1.0,hybridization:float=0.0)->np.ndarray:
    k=np.asarray(k,float); E=np.sqrt((velocity*k)**2+hybridization**2)
    return np.stack((-E,E),axis=-1)


def finite_size_gap(width,xi:float,gap0:float=1.0):
    width=np.asarray(width,float)
    if xi<=0: raise ValueError('xi must be positive')
    return 2*gap0*np.exp(-width/xi)


def penetration_depth(mass:float,hbar_v:float=1.0)->float:
    return float(np.inf if mass==0 else abs(hbar_v/mass))


def surface_dirac_energies(kx,ky,velocity:float=1.0,mass:float=0.0)->np.ndarray:
    kx=np.asarray(kx,float); ky=np.asarray(ky,float)
    E=np.sqrt((velocity**2)*(kx*kx+ky*ky)+mass*mass)
    return np.stack((-E,E),axis=-1)


def surface_spin(kx:float,ky:float,branch:int=1)->np.ndarray:
    k=np.hypot(kx,ky)
    if k==0: return np.array([0.0,0.0,0.0])
    return branch*np.array([-ky/k,kx/k,0.0])


def theta_angle(nu0:int)->float:
    if nu0 not in (0,1): raise ValueError('nu0 must be 0 or 1')
    return float(PI*nu0)


def surface_hall_from_delta_theta(delta_theta:float)->float:
    """sigma_xy in units e^2/h."""
    return float(delta_theta/(2*PI))


def conductance_channels(thickness,surface_sheet:float=2.0,bulk_per_thickness:float=0.1):
    """Simple acceptance model: total sheet conductance = two surfaces + bulk thickness term."""
    thickness=np.asarray(thickness,float)
    return surface_sheet+bulk_per_thickness*thickness
