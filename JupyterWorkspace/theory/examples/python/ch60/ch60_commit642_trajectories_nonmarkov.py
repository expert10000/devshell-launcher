
"""Commit 642: quantum trajectories, measurement backaction, Zeno and non-Markovian diagnostics."""
from __future__ import annotations
import numpy as np

I=np.eye(2,dtype=complex)
X=np.array([[0,1],[1,0]],complex)
Y=np.array([[0,-1j],[1j,0]],complex)
Z=np.array([[1,0],[0,-1]],complex)
SM=np.array([[0,1],[0,0]],complex)

def density(psi):
    v=np.asarray(psi,complex);v=v/np.linalg.norm(v);return np.outer(v,v.conj())

def effective_nonhermitian(H,jumps):
    H=np.asarray(H,complex)
    loss=sum(np.asarray(J,complex).conj().T@np.asarray(J,complex) for J in jumps)
    return H-.5j*loss

def jump_probabilities(psi,jumps,dt):
    v=np.asarray(psi,complex)
    return np.array([float(dt*np.vdot(v,np.asarray(J).conj().T@np.asarray(J)@v).real) for J in jumps])

def quantum_jump_trajectory(H,jumps,psi0,dt,steps,seed=1):
    rng=np.random.default_rng(seed);psi=np.asarray(psi0,complex);psi=psi/np.linalg.norm(psi)
    Heff=effective_nonhermitian(H,jumps)
    states=[psi.copy()];jump_log=[]
    for n in range(int(steps)):
        probs=jump_probabilities(psi,jumps,dt);p=float(np.sum(probs))
        if p>1:raise ValueError("time step too large for jump approximation")
        r=rng.random()
        if r<p and p>0:
            c=np.cumsum(probs)/p;k=int(np.searchsorted(c,r/p,side="right"));k=min(k,len(jumps)-1)
            psi=np.asarray(jumps[k],complex)@psi;norm=np.linalg.norm(psi)
            if norm==0: raise ValueError("jump produced zero state")
            psi=psi/norm;jump_log.append((n,k))
        else:
            psi=(I-1j*Heff*float(dt))@psi
            psi=psi/np.linalg.norm(psi)
        states.append(psi.copy())
    return np.asarray(states),jump_log

def trajectory_density_average(H,jumps,psi0,dt,steps,ntraj=400,seed=1):
    acc=np.zeros((steps+1,2,2),complex)
    for k in range(int(ntraj)):
        st,_=quantum_jump_trajectory(H,jumps,psi0,dt,steps,seed+k)
        acc += np.einsum("ti,tj->tij",st,st.conj())
    return acc/float(ntraj)

def waiting_times(rate,n=1000,seed=1):
    return np.random.default_rng(seed).exponential(1/float(rate),int(n))

def projective_zeno_survival(Omega,total_time,n_measurements):
    N=int(n_measurements)
    if N<1:raise ValueError("n_measurements must be >=1")
    tau=float(total_time)/N
    return float(np.cos(.5*float(Omega)*tau)**(2*N))

def weak_z_measurement(rho,strength,outcome):
    r=np.asarray(rho,complex);s=float(strength)
    if not 0<=s<=1:raise ValueError("strength in [0,1]")
    if outcome not in (0,1):raise ValueError("outcome must be 0 or 1")
    # Unsharp Z measurement: E0=(I+s Z)/2, E1=(I-s Z)/2.
    E=.5*(I+(1 if outcome==0 else -1)*s*Z)
    vals,U=np.linalg.eigh(E);M=(U*np.sqrt(np.clip(vals,0,None)))@U.conj().T
    out=M@r@M.conj().T;p=float(np.trace(out).real)
    return out/p,p

def time_local_rate(t,gamma0=.3,amplitude=1.6,omega=1.2):
    return float(gamma0)*(1+float(amplitude)*np.sin(float(omega)*np.asarray(t,float)))

def dephasing_trace_distance(t,gamma0=.3,amplitude=1.6,omega=1.2):
    t=np.asarray(t,float)
    integ=float(gamma0)*(t+float(amplitude)*(1-np.cos(float(omega)*t))/float(omega))
    return np.exp(-integ)

def backflow_measure(distance):
    d=np.asarray(distance,float);inc=np.diff(d);return float(np.sum(inc[inc>0]))

def structured_reservoir_amplitude(t,gamma0=1.0,lam=.2):
    t=np.asarray(t,float)
    d=np.lib.scimath.sqrt(float(lam)**2-2*float(gamma0)*float(lam))
    G=np.exp(-float(lam)*t/2)*(np.cosh(d*t/2)+(float(lam)/d)*np.sinh(d*t/2))
    return G

def structured_reservoir_population(t,gamma0=1.0,lam=.2):
    return np.abs(structured_reservoir_amplitude(t,gamma0,lam))**2

def memory_kernel_exponential(t,lam):
    t=np.asarray(t,float);return float(lam)*np.exp(-float(lam)*t)

def no_jump_norm_proxy(rate,t):
    return np.exp(-float(rate)*np.asarray(t,float))

def photon_count_histogram(rate,total_time,ntraj=1000,seed=1):
    return np.random.default_rng(seed).poisson(float(rate)*float(total_time),int(ntraj))
