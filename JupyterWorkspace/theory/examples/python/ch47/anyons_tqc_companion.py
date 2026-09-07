"""Reproducible Chapter 47 diagnostics for anyons and topological quantum computation.

The module fixes one standard vertex gauge and counterclockwise exchange convention
for Ising and Fibonacci braid data.  Physical comparisons use phase-insensitive
quantities whenever an isolated logical global phase is irrelevant.
"""
from __future__ import annotations
from itertools import product
import math
import numpy as np

PI=np.pi
I2=np.eye(2,dtype=complex)


def golden_ratio()->float:
    return (1.0+math.sqrt(5.0))/2.0


def fibonacci_total_dimension()->float:
    ph=golden_ratio()
    return math.sqrt(1.0+ph*ph)


def fibonacci_fusion_dimensions(n:int)->tuple[int,int]:
    """Return (paths to total 1, paths to total tau) for n tau anyons."""
    if n<1: raise ValueError('n must be at least 1')
    a,b=0,1
    for _ in range(1,n):
        a,b=b,a+b
    return a,b


def fibonacci_f_matrix()->np.ndarray:
    ph=golden_ratio()
    return np.array([[1/ph,1/math.sqrt(ph)],[1/math.sqrt(ph),-1/ph]],complex)


def fibonacci_r_matrix()->np.ndarray:
    return np.diag([np.exp(-4j*PI/5),np.exp(3j*PI/5)]).astype(complex)


def fibonacci_braid_generators()->tuple[np.ndarray,np.ndarray]:
    F=fibonacci_f_matrix(); b1=fibonacci_r_matrix(); b2=F.conj().T@b1@F
    return b1,b2


def ising_braid_generators()->tuple[np.ndarray,np.ndarray]:
    F=np.array([[1,1],[1,-1]],complex)/math.sqrt(2)
    b1=np.diag([np.exp(-1j*PI/8),np.exp(3j*PI/8)]).astype(complex)
    b2=F.conj().T@b1@F
    return b1,b2


def braid_relation_residual(b1:np.ndarray,b2:np.ndarray)->float:
    return float(np.linalg.norm(b1@b2@b1-b2@b1@b2))


def projective_distance(u:np.ndarray,v:np.ndarray)->float:
    """Phase-insensitive distance sqrt(1-|Tr(U^dag V)|/d) for equal-size unitaries."""
    u=np.asarray(u,complex); v=np.asarray(v,complex)
    if u.shape!=v.shape or u.ndim!=2 or u.shape[0]!=u.shape[1]: raise ValueError('square matrices of same size required')
    d=u.shape[0]
    x=abs(np.trace(u.conj().T@v))/d
    return float(math.sqrt(max(0.0,1.0-min(1.0,x))))


def _generator_map(kind:str='fibonacci')->dict[int,np.ndarray]:
    if kind=='fibonacci': b1,b2=fibonacci_braid_generators()
    elif kind=='ising': b1,b2=ising_braid_generators()
    else: raise ValueError('kind must be fibonacci or ising')
    return {1:b1,-1:b1.conj().T,2:b2,-2:b2.conj().T}


def braid_word_unitary(word,kind:str='fibonacci')->np.ndarray:
    """Apply letters left-to-right in chronological order: U <- B_letter U."""
    g=_generator_map(kind); U=I2.copy()
    for letter in word:
        if letter not in g: raise ValueError('letters must be +/-1 or +/-2')
        U=g[letter]@U
    return U


def reduced_braid_words(max_depth:int):
    """Yield identity and words with no immediate generator/inverse cancellation."""
    if max_depth<0: raise ValueError('max_depth must be nonnegative')
    yield ()
    frontier=[()]
    letters=(1,-1,2,-2)
    for _ in range(max_depth):
        new=[]
        for w in frontier:
            for a in letters:
                if w and a==-w[-1]: continue
                ww=w+(a,); yield ww; new.append(ww)
        frontier=new


def best_braid_approximation(target:np.ndarray,max_depth:int,kind:str='fibonacci'):
    best=(float('inf'),(),I2.copy())
    for w in reduced_braid_words(max_depth):
        U=braid_word_unitary(w,kind)
        d=projective_distance(target,U)
        if d<best[0]-1e-15: best=(d,w,U)
    return best


def bloch_vector(state:np.ndarray)->np.ndarray:
    z=np.asarray(state,complex).reshape(2)
    z=z/np.linalg.norm(z)
    a,b=z
    return np.array([2*np.real(np.conj(a)*b),2*np.imag(np.conj(a)*b),abs(a)**2-abs(b)**2],float)


def braid_orbit_bloch(max_depth:int,kind:str='fibonacci')->np.ndarray:
    ket0=np.array([1,0],complex); pts=[]
    for w in reduced_braid_words(max_depth):
        pts.append(bloch_vector(braid_word_unitary(w,kind)@ket0))
    return np.asarray(pts)


def distinct_projective_orbit_count(max_depth:int,kind:str='fibonacci',decimals:int=7)->int:
    pts=braid_orbit_bloch(max_depth,kind)
    return len({tuple(np.round(x,decimals)) for x in pts})


def forced_success_probability(p:float,attempts:int)->float:
    if not 0<=p<=1: raise ValueError('p must lie in [0,1]')
    if attempts<0: raise ValueError('attempts must be nonnegative')
    return float(1-(1-p)**attempts)


def expected_forced_attempts(p:float)->float:
    if not 0<p<=1: raise ValueError('p must lie in (0,1]')
    return 1.0/p


def magic_state_phase_fidelity(delta:float)->float:
    return float(math.cos(delta/2.0)**2)


def leakage_survival(p_leak:float,operations:int)->float:
    if not 0<=p_leak<=1: raise ValueError('p_leak must lie in [0,1]')
    if operations<0: raise ValueError('operations must be nonnegative')
    return float((1-p_leak)**operations)


def poisoning_probability(time:float,tau:float)->float:
    if time<0 or tau<=0: raise ValueError('time >= 0 and tau > 0 required')
    return float(1-math.exp(-time/tau))


def adiabatic_operation_window(splitting:float,gap:float,hbar:float=1.0):
    """Return (T_min,T_max,exists) for hbar/gap < T < hbar/splitting."""
    if splitting<0 or gap<=0 or hbar<=0: raise ValueError('invalid energy/time scales')
    tmin=hbar/gap
    tmax=math.inf if splitting==0 else hbar/splitting
    return float(tmin),float(tmax),bool(splitting<gap)
