"""Commit 653 quantitative SSH, Rice-Mele, and QWZ topology."""
from __future__ import annotations
import numpy as np

def ssh_bloch(k,t1,t2):
    return np.array([[0,t1+t2*np.exp(-1j*k)],[t1+t2*np.exp(1j*k),0]],complex)

def ssh_bulk_gap(t1,t2):
    return 2*abs(abs(t1)-abs(t2))

def ssh_winding_points(t1,t2,n=500):
    k=np.linspace(-np.pi,np.pi,n)
    return t1+t2*np.cos(k),t2*np.sin(k)

def ssh_open_hamiltonian(L,t1,t2):
    H=np.zeros((2*L,2*L),float)
    for j in range(L):
        H[2*j,2*j+1]=H[2*j+1,2*j]=t1
        if j<L-1: H[2*j+1,2*j+2]=H[2*j+2,2*j+1]=t2
    return H

def ssh_low_mode_profile(L,t1,t2):
    H=ssh_open_hamiltonian(L,t1,t2); e,v=np.linalg.eigh(H); psi=v[:,np.argmin(np.abs(e))]
    return np.abs(psi)**2

def rice_mele_loop(n=400):
    s=np.linspace(0,2*np.pi,n)
    delta=.7*np.cos(s); mass=.7*np.sin(s)
    pumped=(s-np.sin(s))/(2*np.pi)
    return s,delta,mass,pumped

def qwz_bloch(kx,ky,m):
    dx=np.sin(kx); dy=np.sin(ky); dz=m+np.cos(kx)+np.cos(ky)
    return np.array([[dz,dx-1j*dy],[dx+1j*dy,-dz]],complex)

def lower_eigenvector(kx,ky,m):
    _,v=np.linalg.eigh(qwz_bloch(kx,ky,m)); return v[:,0]

def lattice_chern(m,n=31,return_flux=False):
    ks=np.linspace(-np.pi,np.pi,n,endpoint=False)
    u=np.empty((n,n,2),complex)
    for i,kx in enumerate(ks):
        for j,ky in enumerate(ks): u[i,j]=lower_eigenvector(kx,ky,m)
    flux=np.zeros((n,n))
    def link(a,b):
        z=np.vdot(a,b); return z/abs(z)
    for i in range(n):
        for j in range(n):
            u00=u[i,j]; ux=u[(i+1)%n,j]; uy=u[i,(j+1)%n]; uxy=u[(i+1)%n,(j+1)%n]
            z=link(u00,ux)*link(ux,uxy)*link(uxy,uy)*link(uy,u00)
            flux[i,j]=np.angle(z)
    c=flux.sum()/(2*np.pi)
    return (c,ks,flux) if return_flux else float(c)

def qwz_expected_chern(m):
    if -2<m<0: return -1
    if 0<m<2: return 1
    return 0

def qwz_ribbon(Lx,ky,m):
    # h onsite=(m+cos ky) sz + sin ky sy; x hoppings=(sz - i sx)/2
    sz=np.array([[1,0],[0,-1]],complex); sx=np.array([[0,1],[1,0]],complex); sy=np.array([[0,-1j],[1j,0]],complex)
    onsite=(m+np.cos(ky))*sz+np.sin(ky)*sy
    hop=.5*(sz-1j*sx)
    H=np.zeros((2*Lx,2*Lx),complex)
    for x in range(Lx):
        H[2*x:2*x+2,2*x:2*x+2]=onsite
        if x<Lx-1:
            H[2*x:2*x+2,2*x+2:2*x+4]=hop
            H[2*x+2:2*x+4,2*x:2*x+2]=hop.conj().T
    return H
