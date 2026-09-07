"""Numerical companion for Chapter 26: Hilbert spaces and composite systems."""
from __future__ import annotations
import numpy as np

TOL=1e-12

def normalize(v):
    v=np.asarray(v,dtype=complex).reshape(-1)
    n=np.linalg.norm(v)
    if n<TOL: raise ValueError("zero vector cannot be normalized")
    return v/n

def inner(u,v): return np.vdot(np.asarray(u,dtype=complex),np.asarray(v,dtype=complex))

def gram_matrix(vectors):
    V=[np.asarray(v,dtype=complex).reshape(-1) for v in vectors]
    return np.array([[inner(u,v) for v in V] for u in V],dtype=complex)

def gram_schmidt(vectors):
    out=[]
    for v in vectors:
        w=np.asarray(v,dtype=complex).reshape(-1).copy()
        for q in out: w-=inner(q,w)*q
        if np.linalg.norm(w)>TOL: out.append(normalize(w))
    return np.column_stack(out) if out else np.empty((0,0),complex)

def projector(v):
    q=normalize(v); return np.outer(q,q.conj())

def subspace_projector(columns):
    Q=gram_schmidt(np.asarray(columns,dtype=complex).T)
    return Q@Q.conj().T

def is_unitary(U,tol=1e-10):
    U=np.asarray(U,dtype=complex); return U.ndim==2 and U.shape[0]==U.shape[1] and np.allclose(U.conj().T@U,np.eye(U.shape[0]),atol=tol)

def basis_coordinates(state,basis_columns):
    B=np.asarray(basis_columns,dtype=complex); return B.conj().T@np.asarray(state,dtype=complex)

def reconstruct(coords,basis_columns): return np.asarray(basis_columns,dtype=complex)@np.asarray(coords,dtype=complex)

def tensor(*vectors):
    out=np.array([1.0+0j])
    for v in vectors: out=np.kron(out,np.asarray(v,dtype=complex).reshape(-1))
    return out

def density(state):
    q=normalize(state); return np.outer(q,q.conj())

def partial_trace(rho,dims,trace_over):
    da,db=dims; rho=np.asarray(rho,dtype=complex).reshape(da,db,da,db)
    if trace_over in (1,'B','b'): return np.trace(rho,axis1=1,axis2=3)
    if trace_over in (0,'A','a'): return np.trace(rho,axis1=0,axis2=2)
    raise ValueError("trace_over must identify A or B")

def schmidt_coefficients(state,dims):
    da,db=dims; C=normalize(state).reshape(da,db)
    s=np.linalg.svd(C,compute_uv=False)
    return np.sort(np.real_if_close(s*s))[::-1]

def entanglement_entropy(state,dims,base=np.e):
    lam=schmidt_coefficients(state,dims); lam=lam[lam>TOL]
    return float(-np.sum(lam*np.log(lam))/np.log(base))

def purity(rho):
    rho=np.asarray(rho,dtype=complex); return float(np.real_if_close(np.trace(rho@rho)))

def fidelity_pure(psi,phi): return float(abs(inner(normalize(psi),normalize(phi)))**2)

def unitary_from_hermitian(H,t,hbar=1.0):
    H=np.asarray(H,dtype=complex)
    vals,vecs=np.linalg.eigh(H)
    return (vecs*np.exp(-1j*vals*t/hbar))@vecs.conj().T

def expectation(state,A):
    q=normalize(state); return inner(q,np.asarray(A,dtype=complex)@q)

def bell_state(label='phi+'):
    z=np.array([1,0],complex); o=np.array([0,1],complex)
    table={'phi+':tensor(z,z)+tensor(o,o),'phi-':tensor(z,z)-tensor(o,o),
           'psi+':tensor(z,o)+tensor(o,z),'psi-':tensor(z,o)-tensor(o,z)}
    if label not in table: raise ValueError(label)
    return normalize(table[label])

def correlation_matrix(state):
    X=np.array([[0,1],[1,0]],complex);Y=np.array([[0,-1j],[1j,0]],complex);Z=np.diag([1,-1]).astype(complex)
    pauli=[X,Y,Z]
    return np.array([[np.real(expectation(state,np.kron(a,b))) for b in pauli] for a in pauli])
