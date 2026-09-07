"""Reproducible Chapter 46 diagnostics for topological superconductors.

Units are dimensionless unless a function explicitly states otherwise.  Pauli
matrices act in Nambu (tau) and spin (sigma) space as documented below.
"""
from __future__ import annotations
import numpy as np

PI=np.pi
SX=np.array([[0,1],[1,0]],complex)
SY=np.array([[0,-1j],[1j,0]],complex)
SZ=np.array([[1,0],[0,-1]],complex)
I2=np.eye(2,dtype=complex)
TX,TY,TZ=SX,SY,SZ


def uniform_bdg_spectrum(xi, delta):
    """Positive/negative uniform BdG energies sqrt(xi^2+|Delta|^2)."""
    xi=np.asarray(xi,float); E=np.sqrt(xi*xi+abs(delta)**2)
    return np.stack((-E,E),axis=-1)


def coherence_factors(xi:float, delta:complex):
    """Return |u|^2, |v|^2 for the positive-energy BCS branch."""
    E=float(np.sqrt(xi*xi+abs(delta)**2))
    if E==0: return (0.5,0.5)
    return (0.5*(1+xi/E),0.5*(1-xi/E))


def andreev_probability(energy, gap:float=1.0):
    """Ideal transparent-interface Andreev probability at T=0.

    For |E|<Delta it is unity.  Above the gap the standard transparent-interface
    coherence amplitude gives a rapidly decreasing conversion probability.
    """
    if gap<=0: raise ValueError('gap must be positive')
    E=np.abs(np.asarray(energy,float)); out=np.ones_like(E)
    m=E>=gap
    x=E[m]
    out[m]=(gap/(x+np.sqrt(np.maximum(x*x-gap*gap,0.0))))**2
    return out


def kitaev_spectrum(k, mu:float=0.0, t:float=1.0, delta:float=1.0):
    k=np.asarray(k,float)
    xi=-2*t*np.cos(k)-mu; pairing=2*delta*np.sin(k)
    E=np.sqrt(xi*xi+pairing*pairing)
    return np.stack((-E,E),axis=-1)


def kitaev_z2(mu:float,t:float=1.0):
    """Class-D Z2 index: 1 topological, 0 trivial, None at the closing."""
    b=2*abs(t)
    if np.isclose(abs(mu),b,atol=1e-12): return None
    return int(abs(mu)<b)


def kitaev_bulk_gap(mu:float,t:float=1.0,delta:float=1.0,n:int=2001):
    k=np.linspace(-PI,PI,n)
    return float(np.min(kitaev_spectrum(k,mu,t,delta)[:,1]))


def kitaev_open_bdg(n:int,mu:float=0.0,t:float=1.0,delta:float=1.0):
    """Open spinless Kitaev-chain BdG matrix in (c,c^dagger) basis."""
    if n<2: raise ValueError('n must be at least 2')
    A=np.zeros((n,n),complex); B=np.zeros((n,n),complex)
    np.fill_diagonal(A,-mu)
    for i in range(n-1):
        A[i,i+1]=A[i+1,i]=-t
        B[i,i+1]=delta; B[i+1,i]=-delta
    H=np.block([[A,B],[-B.conj(),-A.T]])
    return H


def lowest_abs_open_energy(n:int,**params):
    e=np.linalg.eigvalsh(kitaev_open_bdg(n,**params))
    return float(np.min(np.abs(e)))


def majorana_envelope(x,xi:float=5.0):
    x=np.asarray(x,float)
    if xi<=0: raise ValueError('xi must be positive')
    return np.exp(-np.abs(x)/xi)


def majorana_splitting(length,xi:float=5.0,kf:float=0.7,phase:float=0.0,amplitude:float=1.0):
    L=np.asarray(length,float)
    if xi<=0: raise ValueError('xi must be positive')
    return amplitude*np.exp(-L/xi)*np.cos(kf*L+phase)


def nanowire_hamiltonian(k:float,mu:float=0.0,t:float=1.0,alpha:float=0.6,vz:float=1.0,delta:float=0.4):
    """Minimal lattice Rashba-Zeeman-proximity nanowire BdG Hamiltonian.

    Basis convention has tau acting in Nambu space and sigma in spin space:
      H = xi tau_z + alpha sin(k) tau_z sigma_y + Vz sigma_x + Delta tau_x.
    """
    xi=2*t*(1-np.cos(k))-mu
    return (xi*np.kron(TZ,I2)+alpha*np.sin(k)*np.kron(TZ,SY)+
            vz*np.kron(I2,SX)+delta*np.kron(TX,I2))

NANOWIRE_C_UNITARY=np.kron(TY,SY)


def nanowire_phs_error(k:float,**params):
    H=nanowire_hamiltonian(k,**params); Hm=nanowire_hamiltonian(-k,**params)
    transformed=NANOWIRE_C_UNITARY@H.conj()@NANOWIRE_C_UNITARY.conj().T
    return float(np.linalg.norm(transformed+Hm))


def nanowire_topological(vz:float,mu:float,delta:float):
    critical=np.sqrt(mu*mu+delta*delta)
    if np.isclose(abs(vz),critical,atol=1e-12): return None
    return int(abs(vz)>critical)


def nanowire_gap(mu:float=0.0,t:float=1.0,alpha:float=0.6,vz:float=1.0,delta:float=0.4,n:int=1001):
    ks=np.linspace(-PI,PI,n); g=np.inf
    for k in ks:
        e=np.linalg.eigvalsh(nanowire_hamiltonian(float(k),mu,t,alpha,vz,delta))
        g=min(g,float(np.min(np.abs(e))))
    return g


def pwave_hamiltonian(kx:float,ky:float,mu:float=-2.0,t:float=1.0,delta:float=1.0):
    """Square-lattice spinless chiral p+ip BdG model."""
    dx=delta*np.sin(kx); dy=delta*np.sin(ky)
    dz=-2*t*(np.cos(kx)+np.cos(ky))-mu
    return dx*TX+dy*TY+dz*TZ


def _link(z:complex)->complex:
    a=abs(z); return 1+0j if a<1e-15 else z/a


def pwave_chern(n:int=31,mu:float=-2.0,t:float=1.0,delta:float=1.0,random_gauge_seed:int|None=None):
    """Fukui-Hatsugai-Suzuki Chern number of the occupied BdG band."""
    ks=-PI+2*PI*np.arange(n)/n
    st=np.empty((n,n,2),complex); rng=np.random.default_rng(random_gauge_seed) if random_gauge_seed is not None else None
    for i,kx in enumerate(ks):
        for j,ky in enumerate(ks):
            _,v=np.linalg.eigh(pwave_hamiltonian(float(kx),float(ky),mu,t,delta)); u=v[:,0]
            if rng is not None: u=u*np.exp(1j*rng.uniform(-PI,PI))
            st[i,j]=u
    total=0.0
    for i in range(n):
        for j in range(n):
            ip=(i+1)%n; jp=(j+1)%n
            u00,u10,u11,u01=st[i,j],st[ip,j],st[ip,jp],st[i,jp]
            loop=_link(np.vdot(u00,u10))*_link(np.vdot(u10,u11))*_link(np.vdot(u11,u01))*_link(np.vdot(u01,u00))
            total+=np.angle(loop)
    return float(total/(2*PI))


def pwave_bulk_gap(mu:float=-2.0,t:float=1.0,delta:float=1.0,n:int=121):
    ks=np.linspace(-PI,PI,n,endpoint=False); g=np.inf
    for kx in ks:
        for ky in ks:
            e=np.linalg.eigvalsh(pwave_hamiltonian(float(kx),float(ky),mu,t,delta)); g=min(g,float(np.min(np.abs(e))))
    return g


def chiral_edge_energy(k,velocity:float=1.0):
    return velocity*np.asarray(k,float)


def diii_helical_edge_energies(k,velocity:float=1.0,tr_breaking_mass:float=0.0):
    k=np.asarray(k,float); E=np.sqrt((velocity*k)**2+tr_breaking_mass**2)
    return np.stack((-E,E),axis=-1)


def thermal_majorana_units(chern:int|float):
    """kappa_xy/T in units pi^2 k_B^2/(6h)."""
    return float(chern)


def josephson_majorana_energy(phi,em:float=1.0,parity:int=1):
    """Fixed-parity topological Josephson branch E = p E_M cos(phi/2)."""
    if parity not in (-1,1): raise ValueError('parity must be +/-1')
    return parity*em*np.cos(np.asarray(phi,float)/2)
