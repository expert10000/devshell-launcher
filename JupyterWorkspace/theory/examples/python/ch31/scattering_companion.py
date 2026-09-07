from __future__ import annotations
import numpy as np

def reduced_mass(m1,m2): return m1*m2/(m1+m2)
def momentum_transfer(k,theta): return 2*k*np.sin(np.asarray(theta)/2)
def gaussian_born(q,mu=1.0,V0=1.0,a=1.0,hbar=1.0): return -(mu*V0*np.sqrt(np.pi)*a**3/(2*hbar**2))*np.exp(-(np.asarray(q)*a)**2/4)
def yukawa_born(q,mu=1.0,g=1.0,kappa=1.0,hbar=1.0): return -(2*mu*g/hbar**2)/(np.asarray(q)**2+kappa**2)
def partial_wave_amplitude(theta,k,delta):
    x=np.cos(np.asarray(theta)); out=np.zeros_like(x,dtype=complex)
    from numpy.polynomial.legendre import legval
    for l,d in enumerate(delta):
        c=np.zeros(l+1); c[-1]=1
        out += (2*l+1)*np.exp(1j*d)*np.sin(d)*legval(x,c)/k
    return out
def total_cross_section(k,delta): return 4*np.pi/k**2*sum((2*l+1)*np.sin(d)**2 for l,d in enumerate(delta))
def forward_amplitude(k,delta): return sum((2*l+1)*np.exp(1j*d)*np.sin(d) for l,d in enumerate(delta))/k
def optical_residual(k,delta): return 4*np.pi*np.imag(forward_amplitude(k,delta))/k-total_cross_section(k,delta)
def effective_range_amplitude(k,a,re=0.0): return 1/(-1/a+0.5*re*np.asarray(k)**2-1j*np.asarray(k))
def square_well_scattering_length(R,kappa): return R*(1-np.tan(kappa*R)/(kappa*R))
def breit_wigner_s(E,ER,Gamma,background=0.0): return np.exp(2j*background)*(E-ER-0.5j*Gamma)/(E-ER+0.5j*Gamma)
def breit_wigner_phase(E,ER,Gamma): return np.unwrap(np.angle(breit_wigner_s(np.asarray(E),ER,Gamma)))/2
def reaction_partial(k,l,eta): return np.pi/k**2*(2*l+1)*(1-eta**2)
def elastic_partial(k,l,eta,delta): return np.pi/k**2*(2*l+1)*abs(1-eta*np.exp(2j*delta))**2
