from __future__ import annotations
import numpy as np
def bdg_spectrum(xi,delta): xi=np.asarray(xi,float); E=np.sqrt(xi*xi+abs(delta)**2); return -E,E
def gap_profile(x,delta0=1.,xi0=1.): x=np.asarray(x,float); return delta0*np.tanh(np.maximum(x,0)/xi0)
def meissner_field(x,B0=1.,lambda_L=1.): x=np.asarray(x,float); return B0*np.exp(-np.maximum(x,0)/lambda_L)
def ring_energy(phi_ext,n,EL=1.): phi_ext=np.asarray(phi_ext,float); return EL*(n-phi_ext)**2
def josephson_energy(phi,EJ=1.): return -EJ*np.cos(phi)
def josephson_current(phi,Ic=1.): return Ic*np.sin(phi)
def squid_critical_current(flux,I0=1.): flux=np.asarray(flux,float); return 2*I0*np.abs(np.cos(np.pi*flux))
def andreev_energy(phi,delta=1.,tau=1.): phi=np.asarray(phi,float); return delta*np.sqrt(np.maximum(0,1-tau*np.sin(phi/2)**2))
def andreev_current(phi,delta=1.,tau=.8):
 phi=np.asarray(phi,float); E=andreev_energy(phi,delta,tau); return delta*tau*np.sin(phi)/(4*np.maximum(E,1e-12))
def ac_josephson_frequency(voltage,e_over_hbar=1.): return 2*e_over_hbar*voltage
