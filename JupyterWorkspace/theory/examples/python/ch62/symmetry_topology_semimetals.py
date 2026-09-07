"""Commit 654 symmetry-protected topology and semimetal diagnostics."""
from __future__ import annotations
import numpy as np

def dirac_energy(k,m=0.0,v=1.0):
    k=np.asarray(k,float)
    return np.sqrt((v*k)**2+m*m)

def bhz_gap_parameter(M,A=1.0):
    M=np.asarray(M,float)
    return 2*np.abs(M)

def qsh_topological(M,B=1.0):
    M=np.asarray(M,float)
    return (M/B>0)&(M/B<4)

def qsh_edge_spectrum(k,v=1.0,gap=1.5):
    k=np.asarray(k,float)
    up=v*k
    dn=-v*k
    bulk=np.sqrt((v*k)**2+gap**2)
    return up,dn,bulk,-bulk

def wilson_helical_flow(k):
    k=np.asarray(k,float)
    a=np.pi*k
    return np.mod(a,2*np.pi),np.mod(-a,2*np.pi)

def weyl_energy(kx,ky,kz,v=(1.0,1.0,1.0)):
    return np.sqrt((v[0]*np.asarray(kx))**2+(v[1]*np.asarray(ky))**2+(v[2]*np.asarray(kz))**2)

def weyl_chirality(v=(1.0,1.0,1.0)):
    return int(np.sign(v[0]*v[1]*v[2]))

def nodal_ring_energy(kx,ky,kz,k0=1.0,vz=1.0):
    kx=np.asarray(kx,float); ky=np.asarray(ky,float); kz=np.asarray(kz,float)
    return np.sqrt((kx*kx+ky*ky-k0*k0)**2+(vz*kz)**2)

def defect_dimension_summary():
    # label, node dimension, codimension in 3D
    return [("gapped",-1,4),("Weyl point",0,3),("nodal line",1,2),("nodal surface",2,1)]
