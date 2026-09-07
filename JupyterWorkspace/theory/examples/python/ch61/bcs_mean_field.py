from __future__ import annotations
import numpy as np

def cooper_binding(lambda_g, omega_d=1.0):
    lam=np.asarray(lambda_g,float); out=np.zeros_like(lam); m=lam>0; out[m]=2*omega_d*np.exp(-2/lam[m]); return out

def bogoliubov_spectrum(xi,delta):
    xi=np.asarray(xi,float); return np.sqrt(xi*xi+abs(delta)**2)

def coherence_factors(xi,delta):
    xi=np.asarray(xi,float); E=bogoliubov_spectrum(xi,delta); return .5*(1+xi/E),.5*(1-xi/E)

def bcs_gap_temperature(T,Tc=1.0,delta0=1.764):
    T=np.asarray(T,float); out=np.zeros_like(T); out[T==0]=delta0; m=(T>0)&(T<Tc); out[m]=delta0*np.tanh(1.74*np.sqrt(Tc/T[m]-1)); return out

def bcs_dos(E,delta,gamma=.02):
    E=np.asarray(E,float); z=E+1j*gamma; return np.abs(np.real(z/np.sqrt(z*z-delta*delta)))

def condensation_energy(delta,N0=1.0): return -.5*N0*delta*delta

def nambu_matrix(xi,delta): return np.array([[xi,delta],[np.conjugate(delta),-xi]],complex)

def discrete_gap_residual(delta,xi,g,beta=np.inf):
    xi=np.asarray(xi,float); E=np.sqrt(xi*xi+delta*delta); k=1/(2*E) if np.isinf(beta) else np.tanh(.5*beta*E)/(2*E); return 1/g-np.sum(k)

def solve_discrete_gap(xi,g,beta=np.inf,lo=1e-7,hi=5.0):
    flo=discrete_gap_residual(lo,xi,g,beta); fhi=discrete_gap_residual(hi,xi,g,beta)
    if flo*fhi>0: return 0.0
    a,b=lo,hi
    for _ in range(100):
        m=.5*(a+b); fm=discrete_gap_residual(m,xi,g,beta)
        if flo*fm<=0: b=m
        else: a=m; flo=fm
    return .5*(a+b)

def finite_size_gap(nlevels,g=.08,omega=1.0): return solve_discrete_gap(np.linspace(-omega,omega,nlevels),g)

def attractive_pair_binding_dimer(U,t=1.0):
    U=np.asarray(U,float); E2=.5*(U-np.sqrt(U*U+16*t*t)); return E2+2*t
