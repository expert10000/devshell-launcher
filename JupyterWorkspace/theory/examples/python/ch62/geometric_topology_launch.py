"""Commit 652 geometric/topological Chapter 62 launch diagnostics."""
from __future__ import annotations
import numpy as np

def berry_phase_solid_angle(omega,band=-1):
    omega=np.asarray(omega,float)
    return -0.5*band*omega

def two_level_curvature_magnitude(x,y,z=1.0):
    x=np.asarray(x,float); y=np.asarray(y,float)
    r2=x*x+y*y+z*z
    return 0.5/(r2**1.5)

def parameter_loop(theta,n=400):
    t=np.linspace(0,2*np.pi,n)
    return np.cos(t), np.sin(t), theta*np.ones_like(t)

def accumulated_chern_flux(n=60):
    # synthetic convergence of a discretized unit-flux surface integral
    m=np.arange(4,n+1)
    return m,1-0.7/m**2

def thouless_cycle(n=400):
    t=np.linspace(0,1,n)
    delta=np.cos(2*np.pi*t)
    stagger=np.sin(2*np.pi*t)
    pumped=t-(np.sin(2*np.pi*t)/(2*np.pi))
    return t,delta,stagger,pumped

def quantum_metric_two_level(theta):
    theta=np.asarray(theta,float)
    # phi-direction metric on Bloch sphere for spin-1/2
    return 0.25*np.sin(theta)**2
