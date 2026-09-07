from __future__ import annotations
import numpy as np
I2=np.eye(2,dtype=complex);X=np.array([[0,1],[1,0]],complex);Y=np.array([[0,-1j],[1j,0]],complex);Z=np.array([[1,0],[0,-1]],complex)
def kron(a,b):return np.kron(np.asarray(a,complex),np.asarray(b,complex))
def exchange_hamiltonian(J=1.0):return .25*float(J)*(kron(X,X)+kron(Y,Y)+kron(Z,Z))
def xy_hamiltonian(J=1.0):return .5*float(J)*(kron(X,X)+kron(Y,Y))
def zz_hamiltonian(J=1.0):return .5*float(J)*kron(Z,Z)
def hermitian_step(H,t):
 w,v=np.linalg.eigh(np.asarray(H,complex));return (v*np.exp(-1j*w*float(t)))@v.conj().T
def state_fidelity(a,b):
 a=np.asarray(a,complex);b=np.asarray(b,complex);return float(abs(np.vdot(a,b))**2/(np.vdot(a,a).real*np.vdot(b,b).real))
def concurrence_pure(psi):
 p=np.asarray(psi,complex).reshape(4);a,b,c,d=p;return float(2*abs(a*d-b*c))
def reduced_density_first(psi):
 p=np.asarray(psi,complex).reshape(2,2);return p@p.conj().T
def entanglement_entropy(psi):
 rho=reduced_density_first(psi);w=np.linalg.eigvalsh(rho).real;w=np.clip(w,1e-15,1);return float(-np.sum(w*np.log2(w)))
def iswap_unitary(theta=np.pi/2):
 c=np.cos(theta);s=np.sin(theta);U=np.eye(4,dtype=complex);U[1,1]=c;U[2,2]=c;U[1,2]=-1j*s;U[2,1]=-1j*s;return U
def controlled_phase(phi=np.pi):
 return np.diag([1,1,1,np.exp(1j*float(phi))]).astype(complex)
def dispersive_shift(g,delta):
 if delta==0:raise ValueError('delta must be nonzero')
 return float(g)**2/float(delta)
def sw_two_level_effective(E1,E2,g):
 d=float(E1)-float(E2)
 if d==0:raise ValueError('nondegenerate SW denominator required')
 shift=float(g)**2/d
 return np.array([[float(E1)+shift,0],[0,float(E2)-shift]],complex)
def exact_two_level(E1,E2,g):return np.array([[float(E1),float(g)],[float(g),float(E2)]],complex)
def cross_resonance_hamiltonian(zx=1.0,ix=0.0,zi=0.0,zz=0.0):
 return .5*(float(zx)*kron(Z,X)+float(ix)*kron(I2,X)+float(zi)*kron(Z,I2)+float(zz)*kron(Z,Z))
def bell_state():return np.array([1,0,0,1],complex)/np.sqrt(2)
def swap_population_trace(times,J=1.0):
 psi=np.array([0,1,0,0],complex);P=[]
 H=xy_hamiltonian(J)
 for t in np.asarray(times,float):P.append(abs((hermitian_step(H,t)@psi)[2])**2)
 return np.asarray(P)
def entanglement_trace(times,J=1.0):
 psi=np.array([0,1,0,0],complex);H=xy_hamiltonian(J);return np.array([entanglement_entropy(hermitian_step(H,t)@psi) for t in np.asarray(times,float)])
