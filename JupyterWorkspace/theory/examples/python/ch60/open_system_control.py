"""Commit 643 quantitative open-system-control diagnostics.

The routines use dimensionless units (hbar=1) unless stated otherwise.
They are intentionally small reference models: the purpose is to make
control/noise tradeoffs inspectable and regression-testable.
"""
from __future__ import annotations
import numpy as np

def switching_function(t, pulse_times, pulse_width=0.0):
    t=np.asarray(t,float)
    y=np.ones_like(t)
    for tp in sorted(pulse_times):
        if pulse_width<=0:
            y[t>=tp]*=-1.0
        else:
            a=tp-pulse_width/2
            b=tp+pulse_width/2
            before=t<a
            during=(t>=a)&(t<=b)
            after=t>b
            sign=np.where(np.sum(np.asarray(pulse_times)<tp)%2==0,1.0,-1.0)
            y[during]=sign*np.cos(np.pi*(t[during]-a)/pulse_width)
            y[after]*=-1.0
    return y

def pulse_times(sequence, total_time):
    s=sequence.upper()
    if s=="FID": return []
    if s=="HAHN": return [0.5*total_time]
    n={"CPMG":4,"XY4":4,"XY8":8}.get(s)
    if n is None: raise ValueError(sequence)
    return [(j+0.5)*total_time/n for j in range(n)]

def gaussian_ou_coherence(total_time, sequence="FID", sigma=1.0, tau_c=0.25, ngrid=700, pulse_width=0.0):
    if total_time<=0: return 1.0
    t=np.linspace(0,total_time,ngrid)
    y=switching_function(t,pulse_times(sequence,total_time),pulse_width)
    dt=t[1]-t[0]
    # Stationary Ornstein-Uhlenbeck covariance C(dt)=sigma^2 exp(-|dt|/tau_c).
    d=np.abs(t[:,None]-t[None,:])
    C=sigma**2*np.exp(-d/tau_c)
    chi=0.5*dt*dt*np.sum((y[:,None]*y[None,:])*C)
    return float(np.exp(-chi))

def filter_function(omega, total_time, sequence="XY4", pulse_width=0.0, ngrid=2000):
    omega=np.atleast_1d(np.asarray(omega,float))
    t=np.linspace(0,total_time,ngrid)
    y=switching_function(t,pulse_times(sequence,total_time),pulse_width)
    phase=np.exp(1j*omega[:,None]*t[None,:])
    Y=np.trapezoid(y[None,:]*phase,t,axis=1)
    return np.abs(Y)**2

def finite_width_scan(widths, total_time=4.0, sequence="XY8"):
    widths=np.asarray(widths,float)
    return np.array([gaussian_ou_coherence(total_time,sequence,pulse_width=w) for w in widths])

def feedback_rabi_trajectory(t, omega=2*np.pi, gamma=0.16, feedback_gain=0.9, seed=643):
    """Synthetic but explicit phase-diffusion Rabi trajectory with proportional feedback."""
    t=np.asarray(t,float)
    rng=np.random.default_rng(seed)
    dt=float(np.mean(np.diff(t)))
    target=np.sin(omega*t)
    free=np.zeros_like(t); fb=np.zeros_like(t)
    phase_free=phase_fb=0.0
    for k in range(1,len(t)):
        phase_free += omega*dt + np.sqrt(2*gamma*dt)*rng.normal()
        phase_fb += omega*dt + np.sqrt(2*gamma*dt)*rng.normal()
        free[k]=np.sin(phase_free)
        err=target[k-1]-np.sin(phase_fb)
        phase_fb += feedback_gain*err*dt
        fb[k]=np.sin(phase_fb)
    return target, free, fb

def dark_state_fidelity(t, kappa=1.0, f0=0.05):
    t=np.asarray(t,float)
    return 1-(1-f0)*np.exp(-kappa*t)

def dissipative_prep_fidelity(kappa, mismatch=0.0, coherent_drive=0.0):
    kappa=np.asarray(kappa,float)
    leak=mismatch**2 + (coherent_drive/(kappa+1e-12))**2
    return 1/(1+leak)

def engineered_jump_liouvillian(kappa=1.0):
    """Liouvillian for L=sqrt(kappa)|0><1| in column-vectorized convention."""
    sm=np.array([[0,1],[0,0]],complex)
    L=np.sqrt(kappa)*sm
    I=np.eye(2)
    A=L.conj().T@L
    return np.kron(L.conj(),L)-0.5*np.kron(I,A)-0.5*np.kron(A.T,I)

def pareto_curve(strength):
    strength=np.asarray(strength,float)
    residual_noise=1/(1+strength**2)
    control_cost=strength**2/(1+strength**2)
    robustness=np.exp(-0.12*strength)
    return residual_noise, control_cost, robustness

