from __future__ import annotations
import numpy as np

def many_body_berry_phase(theta,U=1.0):
 theta=np.asarray(theta,float); return np.mod((1+0.15*np.tanh(U-1))*theta,2*np.pi)

def many_body_chern_convergence(n):
 n=np.asarray(n,float); return 1-0.9/n**2

def resta_polarization(control,U=1.0):
 x=np.asarray(control,float); return 0.25*(1-np.tanh(6*(x+0.12*(U-1))))

def entanglement_levels(control):
 x=np.asarray(control,float); base=np.sqrt(x*x+0.04); return np.vstack([-base,-.35*base,.35*base,base]).T

def flux_spectral_branches(theta):
 t=np.asarray(theta,float); return np.vstack([-.8+0.25*np.cos(t),-.2+0.35*np.cos(t+2*np.pi/3),.2+0.35*np.cos(t-2*np.pi/3),.8+0.25*np.cos(t)]).T

def multiplet_splitting(L,xi=5.0):
 L=np.asarray(L,float); return np.exp(-L/xi)

def fractional_charge_profile(x,center=0.0,charge=1/3,width=1.0):
 x=np.asarray(x,float); raw=np.exp(-0.5*((x-center)/width)**2); return charge*raw/np.trapezoid(raw,x)

def interaction_gap(U,Uc=2.0):
 U=np.asarray(U,float); return np.sqrt((U-Uc)**2+0.05**2)

def single_particle_invariant(U):
 U=np.asarray(U,float); return np.where(U<1.7,1.0,0.0)

def many_body_invariant(U):
 U=np.asarray(U,float); return .5*(1-np.tanh(8*(U-2.3)))
