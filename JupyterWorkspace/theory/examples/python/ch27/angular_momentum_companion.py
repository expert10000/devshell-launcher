"""Numerical companion for Chapter 27: angular momentum and spin."""
from __future__ import annotations
import math
import numpy as np
TOL=1e-12
HBAR=1.0

I2=np.eye(2,dtype=complex)
SX=np.array([[0,1],[1,0]],complex)
SY=np.array([[0,-1j],[1j,0]],complex)
SZ=np.array([[1,0],[0,-1]],complex)
PAULI=(SX,SY,SZ)
UP=np.array([1,0],complex);DOWN=np.array([0,1],complex)

def normalize(v):
    q=np.asarray(v,dtype=complex).reshape(-1);n=np.linalg.norm(q)
    if n<TOL: raise ValueError('zero vector')
    return q/n

def commutator(a,b): return np.asarray(a)@np.asarray(b)-np.asarray(b)@np.asarray(a)
def expectation(state,a):
    q=normalize(state);return np.vdot(q,np.asarray(a,dtype=complex)@q)
def tensor(*args):
    out=np.array([1+0j])
    for a in args:out=np.kron(out,np.asarray(a,dtype=complex).reshape(-1))
    return out

def spin_operator(axis,hbar=HBAR):
    n=normalize(np.asarray(axis,dtype=float)).real
    return .5*hbar*sum(n[i]*PAULI[i] for i in range(3))

def rotation_spin_half(axis,angle):
    n=normalize(np.asarray(axis,dtype=float)).real
    ns=sum(n[i]*PAULI[i] for i in range(3))
    return math.cos(angle/2)*I2-1j*math.sin(angle/2)*ns

def bloch_vector(state):
    q=normalize(state)
    return np.array([float(np.real(expectation(q,s))) for s in PAULI])

def measurement_probabilities(state,axis):
    n=normalize(np.asarray(axis,dtype=float)).real;r=bloch_vector(state)
    p=(1+float(np.dot(n,r)))/2
    return np.array([p,1-p])

def projective_measure(state,axis,outcome=1):
    n=normalize(np.asarray(axis,dtype=float)).real
    P=.5*(I2+(1 if outcome>0 else -1)*sum(n[i]*PAULI[i] for i in range(3)))
    q=P@normalize(state);p=float(np.real(np.vdot(q,q)))
    return p,(q/np.sqrt(p) if p>TOL else q)

def angular_momentum_matrices(j,hbar=HBAR):
    n=int(round(2*j))
    if j<0 or abs(2*j-n)>1e-10: raise ValueError('j must be nonnegative integer or half-integer')
    m=np.array([j-k for k in range(n+1)],float)
    jp=np.zeros((n+1,n+1),complex)
    # columns are input |j,m>; rows are output |j,m+1>
    for col,mm in enumerate(m):
        target=mm+1
        rows=np.where(np.isclose(m,target))[0]
        if len(rows): jp[rows[0],col]=hbar*np.sqrt((j-mm)*(j+mm+1))
    jm=jp.conj().T
    jx=(jp+jm)/2;jy=(jp-jm)/(2j);jz=np.diag(hbar*m)
    return jx,jy,jz,jp,jm,m

def casimir(j,hbar=HBAR):
    jx,jy,jz,*_=angular_momentum_matrices(j,hbar)
    return jx@jx+jy@jy+jz@jz

def cg_spin_half_matrix():
    # product order uu, ud, du, dd; coupled order 1,1;1,0;1,-1;0,0 as columns
    s=1/np.sqrt(2)
    return np.array([[1,0,0,0],[0,s,0,s],[0,s,0,-s],[0,0,1,0]],complex)

def coupled_states():
    C=cg_spin_half_matrix()
    return {'triplet_plus':C[:,0],'triplet_zero':C[:,1],'triplet_minus':C[:,2],'singlet':C[:,3]}

def total_spin_squared():
    S=[.5*np.kron(p,I2)+.5*np.kron(I2,p) for p in PAULI]
    return sum(a@a for a in S)

def spin_dot(): return .25*sum(np.kron(p,p) for p in PAULI)
def correlation_matrix(state):
    q=normalize(state)
    return np.array([[float(np.real(expectation(q,np.kron(a,b)))) for b in PAULI] for a in PAULI])

def entropy_probabilities(p,base=2):
    p=np.asarray(p,float);p=p[p>TOL]
    return float(-np.sum(p*np.log(p))/np.log(base))

def y10_density(theta): return 3/(4*np.pi)*np.cos(theta)**2
