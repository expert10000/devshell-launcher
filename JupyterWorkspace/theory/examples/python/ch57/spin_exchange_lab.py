from __future__ import annotations
import numpy as np

SX=np.array([[0,1],[1,0]],dtype=complex)
SY=np.array([[0,-1j],[1j,0]],dtype=complex)
SZ=np.array([[1,0],[0,-1]],dtype=complex)
I2=np.eye(2,dtype=complex)
PAULI=(SX,SY,SZ)
UP=np.array([1,0],dtype=complex)
DOWN=np.array([0,1],dtype=complex)

def normalize_state(psi):
    v=np.asarray(psi,dtype=complex).reshape(-1); n=np.linalg.norm(v)
    if n<=0: raise ValueError('State norm must be positive.')
    return v/n

def spin_hamiltonian(B,gamma=1.0):
    b=np.asarray(B,dtype=float)
    if b.shape!=(3,) or not np.all(np.isfinite(b)): raise ValueError('B must be a finite three-vector.')
    return -0.5*float(gamma)*sum(b[i]*PAULI[i] for i in range(3))

def zeeman_energies(B,gamma=1.0): return np.linalg.eigvalsh(spin_hamiltonian(B,gamma))

def larmor_frequency(B,gamma=1.0):
    b=np.asarray(B,dtype=float)
    if b.shape!=(3,) or not np.all(np.isfinite(b)): raise ValueError('B must be a finite three-vector.')
    return float(abs(gamma)*np.linalg.norm(b))

def spin_unitary(B,time,gamma=1.0):
    b=np.asarray(B,dtype=float); mag=np.linalg.norm(b)
    if mag==0: return I2.copy()
    n=b/mag; a=0.5*float(gamma)*mag*float(time); ns=sum(n[i]*PAULI[i] for i in range(3))
    return np.cos(a)*I2+1j*np.sin(a)*ns

def evolve_spinor(psi,B,time,gamma=1.0): return spin_unitary(B,time,gamma)@normalize_state(psi)

def bloch_vector(psi):
    v=normalize_state(psi)
    return np.array([np.real(np.vdot(v,s@v)) for s in PAULI],dtype=float)

def resonance_detuning(omega_drive,B0,gamma=1.0): return float(omega_drive-abs(gamma)*abs(B0))

def two_spin_operator(single,which):
    a=np.asarray(single,dtype=complex)
    if a.shape!=(2,2): raise ValueError('single must be 2x2.')
    if which==1:return np.kron(a,I2)
    if which==2:return np.kron(I2,a)
    raise ValueError('which must be 1 or 2.')

def total_spin_squared():
    components=[0.5*(two_spin_operator(s,1)+two_spin_operator(s,2)) for s in PAULI]
    return sum(a@a for a in components)

def singlet_triplet_states():
    uu=np.kron(UP,UP);ud=np.kron(UP,DOWN);du=np.kron(DOWN,UP);dd=np.kron(DOWN,DOWN)
    return {'S':(ud-du)/np.sqrt(2.0),'T+':uu,'T0':(ud+du)/np.sqrt(2.0),'T-':dd}

def exchange_hamiltonian(J=1.0): return 0.25*float(J)*sum(np.kron(s,s) for s in PAULI)

def exchange_energies(J=1.0): return {'singlet':-0.75*float(J),'triplet':0.25*float(J)}

def exchange_gap(J=1.0): return float(J)

def swap_operator():
    P=np.zeros((4,4),dtype=complex)
    for a in range(2):
        for b in range(2): P[2*b+a,2*a+b]=1.0
    return P

def singlet_projector():
    s=singlet_triplet_states()['S']; return np.outer(s,s.conj())

def triplet_projector(): return np.eye(4,dtype=complex)-singlet_projector()

def reference_summary():
    B=np.array([0.0,0.0,2.0]);e=zeeman_energies(B,gamma=1.5);st=singlet_triplet_states();Hex=exchange_hamiltonian(0.8)
    return {'zeeman_energies':e.tolist(),'zeeman_gap':float(e[1]-e[0]),'larmor_frequency':larmor_frequency(B,gamma=1.5),
            'singlet_s2':float(np.real(np.vdot(st['S'],total_spin_squared()@st['S']))),
            'triplet_s2':float(np.real(np.vdot(st['T0'],total_spin_squared()@st['T0']))),
            'exchange_eigenvalues':np.linalg.eigvalsh(Hex).tolist(),'exchange_gap':exchange_gap(0.8)}

if __name__=='__main__':
    import json; print(json.dumps(reference_summary(),indent=2))
