from __future__ import annotations
import numpy as np
from math import pi

def nondegenerate_energy_corrections(energies, perturbation, state=0):
    e=np.asarray(energies,dtype=float); v=np.asarray(perturbation,dtype=complex); n=int(state)
    if v.shape!=(len(e),len(e)) or not np.allclose(v,v.conj().T): raise ValueError
    first=float(np.real(v[n,n])); second=0.0
    for m in range(len(e)):
        if m!=n:
            if np.isclose(e[n],e[m]): raise ValueError('degeneracy')
            second += abs(v[m,n])**2/(e[n]-e[m])
    return first,float(np.real(second))

def exact_eigenvalues(energies, perturbation, coupling=1.0):
    h=np.diag(np.asarray(energies,dtype=float))+coupling*np.asarray(perturbation,dtype=complex)
    return np.linalg.eigvalsh(h)

def degenerate_first_order(block): return np.linalg.eigvalsh(np.asarray(block,dtype=complex))

def rayleigh_quotient(h, vector):
    h=np.asarray(h,dtype=complex); v=np.asarray(vector,dtype=complex).reshape(-1)
    n=np.vdot(v,v).real
    if n<=0: raise ValueError
    return float(np.real(np.vdot(v,h@v)/n))

def residual_norm(h, vector):
    h=np.asarray(h,dtype=complex); v=np.asarray(vector,dtype=complex).reshape(-1); v=v/np.linalg.norm(v)
    e=rayleigh_quotient(h,v); return float(np.linalg.norm(h@v-e*v))

def gaussian_quartic_energy(alpha, lam=0.1, omega=1.0):
    a=np.asarray(alpha,dtype=float)
    if np.any(a<=0) or lam<0 or omega<=0: raise ValueError
    return a/4+omega**2/(4*a)+3*lam/(4*a**2)

def rectangular_pulse_probability(detuning, coupling, duration):
    d=np.asarray(detuning,dtype=float); g=float(coupling); t=float(duration)
    if t<0: raise ValueError
    return (g*t)**2*np.sinc(d*t/(2*pi))**2

def rabi_probability(detuning, rabi_frequency, time):
    d=np.asarray(detuning,dtype=float); o=float(rabi_frequency); t=np.asarray(time,dtype=float)
    om=np.sqrt(o**2+d**2)
    return np.where(om==0,0.0,(o**2/om**2)*np.sin(om*t/2)**2)

def golden_rule_rate(matrix_element, density, hbar=1.0):
    if density<0 or hbar<=0: raise ValueError
    return 2*pi*abs(matrix_element)**2*density/hbar

def adiabatic_parameter(gap, hdot_matrix_element, hbar=1.0):
    if gap<=0 or hbar<=0: raise ValueError
    return hbar*abs(hdot_matrix_element)/gap**2

def landau_zener_diabatic_probability(coupling, sweep_rate, hbar=1.0):
    if sweep_rate<=0 or hbar<=0: raise ValueError
    return float(np.exp(-2*pi*abs(coupling)**2/(hbar*sweep_rate)))

def sudden_probabilities(initial_state, new_basis):
    psi=np.asarray(initial_state,dtype=complex).reshape(-1); b=np.asarray(new_basis,dtype=complex)
    psi=psi/np.linalg.norm(psi)
    if b.shape[0]!=len(psi) or not np.allclose(b.conj().T@b,np.eye(b.shape[1]),atol=1e-10): raise ValueError
    return np.abs(b.conj().T@psi)**2

def wkb_transmission(barrier_height, energy, width, mass=0.5, hbar=1.0):
    if barrier_height<=energy or width<0 or mass<=0 or hbar<=0: raise ValueError
    kappa=np.sqrt(2*mass*(barrier_height-energy))/hbar
    return float(np.exp(-2*kappa*width))

def bohr_sommerfeld_harmonic(n, omega=1.0, hbar=1.0):
    if n<0 or omega<=0 or hbar<=0: raise ValueError
    return hbar*omega*(n+0.5)
