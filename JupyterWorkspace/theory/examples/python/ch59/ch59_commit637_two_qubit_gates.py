
"""Commit 637: quantitative two-qubit entangling dynamics and gate synthesis."""
from __future__ import annotations
import numpy as np

I = np.eye(2, dtype=complex)
X = np.array([[0,1],[1,0]], dtype=complex)
Y = np.array([[0,-1j],[1j,0]], dtype=complex)
Z = np.array([[1,0],[0,-1]], dtype=complex)
P0 = np.array([[1,0],[0,0]], dtype=complex)
P1 = np.array([[0,0],[0,1]], dtype=complex)

def kron2(a,b): return np.kron(a,b)
XI, YI, ZI = kron2(X,I), kron2(Y,I), kron2(Z,I)
IX, IY, IZ = kron2(I,X), kron2(I,Y), kron2(I,Z)
XX, YY, ZZ = kron2(X,X), kron2(Y,Y), kron2(Z,Z)
ZX = kron2(Z,X)

def hermitian_step(H, t):
    w,v=np.linalg.eigh(np.asarray(H,dtype=complex))
    return (v*np.exp(-1j*w*float(t)))@v.conj().T

def two_qubit_hamiltonian(w1=0.0,w2=0.0,jxx=0.0,jyy=0.0,jzz=0.0):
    return .5*w1*ZI+.5*w2*IZ+jxx*XX+jyy*YY+jzz*ZZ

def xy_hamiltonian(J=1.0):
    return .5*float(J)*(XX+YY)

def zz_hamiltonian(J=1.0):
    return .25*float(J)*ZZ

def basis(index):
    v=np.zeros(4,complex);v[int(index)]=1;return v

def evolve(H,psi,t):
    return hermitian_step(H,t)@np.asarray(psi,dtype=complex)

def concurrence_pure(psi):
    a,b,c,d=np.asarray(psi,dtype=complex).reshape(4)
    return float(2*abs(a*d-b*c))

def reduced_density_first(psi):
    A=np.asarray(psi,dtype=complex).reshape(2,2)
    return A@A.conj().T

def entanglement_entropy(psi):
    vals=np.linalg.eigvalsh(reduced_density_first(psi)).real
    vals=np.clip(vals,0,1);nz=vals[vals>1e-15]
    return float(-np.sum(nz*np.log2(nz)))

def iswap():
    U=np.eye(4,dtype=complex);U[1,1]=0;U[2,2]=0;U[1,2]=1j;U[2,1]=1j
    return U

def sqrt_iswap():
    return hermitian_step(xy_hamiltonian(1.0), -np.pi/4)

def controlled_phase(phi=np.pi):
    return np.diag([1,1,1,np.exp(1j*float(phi))]).astype(complex)

def cz(): return controlled_phase(np.pi)

def average_gate_fidelity(U,V):
    U=np.asarray(U,complex);V=np.asarray(V,complex);d=U.shape[0]
    z=np.trace(V.conj().T@U)
    return float((abs(z)**2+d)/(d*(d+1)))

def local_z(theta1,theta2):
    z1=np.diag([np.exp(-.5j*theta1),np.exp(.5j*theta1)])
    z2=np.diag([np.exp(-.5j*theta2),np.exp(.5j*theta2)])
    return np.kron(z1,z2)

def cross_resonance_hamiltonian(zx=1.0,ix=0.0,zi=0.0,zz=0.0):
    return .5*(float(zx)*ZX+float(ix)*IX+float(zi)*ZI+float(zz)*ZZ)

def echo_cross_resonance_unitary(zx=1.0,ix=.2,zi=.1,zz=.05,total_time=np.pi/2):
    # Toy echo: simultaneous X on control between half-pulses, with drive sign reversal.
    H1=cross_resonance_hamiltonian(zx,ix,zi,zz)
    H2=cross_resonance_hamiltonian(-zx,-ix,zi,zz)
    Xc=XI
    U1=hermitian_step(H1,total_time/2)
    U2=hermitian_step(H2,total_time/2)
    return Xc@U2@Xc@U1

def bell_from_xy():
    psi=evolve(xy_hamiltonian(1.0),basis(1),np.pi/4)
    return psi

def gate_calibration_map(J_values,t_values,target=None):
    J_values=np.asarray(J_values,float);t_values=np.asarray(t_values,float)
    if target is None:
        target=hermitian_step(xy_hamiltonian(1.0),np.pi/4)
    F=np.zeros((len(t_values),len(J_values)))
    for i,t in enumerate(t_values):
        for j,J in enumerate(J_values):
            F[i,j]=average_gate_fidelity(hermitian_step(xy_hamiltonian(J),t),target)
    return F

def canonical_nonlocal_coordinates(kind):
    # Standard representative coordinates in the common Weyl chamber convention.
    k=kind.lower()
    if k in {"identity","i"}: return np.array([0.,0.,0.])
    if k in {"cnot","cz"}: return np.array([np.pi/4,0.,0.])
    if k=="iswap": return np.array([np.pi/4,np.pi/4,0.])
    if k in {"sqrt-iswap","sqrt_iswap"}: return np.array([np.pi/8,np.pi/8,0.])
    if k=="swap": return np.array([np.pi/4,np.pi/4,np.pi/4])
    raise ValueError("unknown gate kind")

def entangling_power_proxy(coords):
    c=np.asarray(coords,float)
    return float(np.sum(np.sin(2*c)**2)/3.0)

def spectator_zz_phase(jzz,t):
    return float(jzz)*np.asarray(t,dtype=float)
