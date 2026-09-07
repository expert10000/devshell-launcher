"""Commit 649: Kitaev-chain and topological-superconductivity diagnostics."""
from __future__ import annotations
import numpy as np

def bulk_energy(k, mu, t=1.0, delta=0.6):
    k=np.asarray(k,float)
    return np.sqrt((-mu-2*t*np.cos(k))**2+(2*delta*np.sin(k))**2)

def bulk_gap(mu,t=1.0,delta=0.6,nk=4001):
    k=np.linspace(-np.pi,np.pi,nk)
    return float(np.min(bulk_energy(k,mu,t,delta)))

def topological(mu,t=1.0):
    return np.abs(np.asarray(mu,float)) < 2*abs(t)

def kitaev_bdg(L,mu,t=1.0,delta=0.6,periodic=False,disorder=None):
    h=np.zeros((L,L),complex)
    D=np.zeros((L,L),complex)
    onsite=np.full(L,-mu,float)
    if disorder is not None: onsite=onsite+np.asarray(disorder,float)
    np.fill_diagonal(h,onsite)
    for j in range(L-1):
        h[j,j+1]=h[j+1,j]=-t
        D[j,j+1]=delta
        D[j+1,j]=-delta
    if periodic and L>2:
        h[0,-1]=h[-1,0]=-t
        D[-1,0]=delta
        D[0,-1]=-delta
    return np.block([[h,D],[-D.conjugate(),-h.T]])

def spectrum(L,mu,t=1.0,delta=0.6,periodic=False,disorder=None):
    return np.linalg.eigvalsh(kitaev_bdg(L,mu,t,delta,periodic,disorder))

def min_abs_energy(*args,**kwargs):
    return float(np.min(np.abs(spectrum(*args,**kwargs))))

def lowest_mode_profile(L,mu,t=1.0,delta=0.6):
    H=kitaev_bdg(L,mu,t,delta,False)
    vals,vecs=np.linalg.eigh(H)
    v=vecs[:,np.argmin(np.abs(vals))]
    p=np.abs(v[:L])**2+np.abs(v[L:])**2
    return p/p.sum()

def winding_points(mu,t=1.0,delta=0.6,nk=500):
    k=np.linspace(-np.pi,np.pi,nk,endpoint=False)
    dz=-mu-2*t*np.cos(k)
    dy=2*delta*np.sin(k)
    return dz,dy

def winding_number(mu,t=1.0,delta=0.6,nk=4000):
    dz,dy=winding_points(mu,t,delta,nk)
    ang=np.unwrap(np.angle(dz+1j*dy))
    return int(np.rint((ang[-1]-ang[0])/(2*np.pi)))

def disorder_gap_stat(L,mu,W,t=1.0,delta=0.6,samples=24,seed=123):
    rng=np.random.default_rng(seed)
    vals=[]
    for _ in range(samples):
        dis=rng.uniform(-W/2,W/2,L)
        e=np.sort(np.abs(spectrum(L,mu,t,delta,False,dis)))
        vals.append(e[min(2,len(e)-1)])  # exclude the near-zero Majorana pair
    return float(np.median(vals))

def nanowire_critical_field(mu,delta=0.35):
    mu=np.asarray(mu,float)
    return np.sqrt(mu*mu+delta*delta)
