from __future__ import annotations
import numpy as np
ZETA32=2.612375348685488
KB=1.380649e-23
HBAR=1.054571817e-34
H=2*np.pi*HBAR

def bose_occupation(eps,mu=0.0,kT=1.0):
    x=(np.asarray(eps)-mu)/kT
    return 1/np.expm1(x)

def fermi_occupation(eps,mu=0.0,kT=1.0):
    x=(np.asarray(eps)-mu)/kT
    return 1/(np.exp(x)+1)

def maxwell_boltzmann(eps,mu=0.0,kT=1.0): return np.exp(-(np.asarray(eps)-mu)/kT)
def thermal_wavelength(m,T): return H/np.sqrt(2*np.pi*m*KB*T)
def bose_critical_temperature(n,m,g=1.0): return 2*np.pi*HBAR**2/(m*KB)*(n/(g*ZETA32))**(2/3)
def condensate_fraction(T,Tc):
    x=np.asarray(T)/Tc
    return np.where(x<Tc*0+1, np.maximum(0.0,1-x**1.5),0.0)
def fermi_wave_number(n,g=2.0): return (6*np.pi**2*n/g)**(1/3)
def fermi_energy(n,m,g=2.0): return HBAR**2*fermi_wave_number(n,g)**2/(2*m)
def fermi_pressure_zero(n,m,g=2.0): return 2*n*fermi_energy(n,m,g)/5
def sommerfeld_mu(EF,T_over_TF): return EF*(1-(np.pi**2/12)*np.asarray(T_over_TF)**2)
def fermion_cv_per_particle(T_over_TF): return (np.pi**2/2)*KB*np.asarray(T_over_TF)
def planck_scaled(x): return np.asarray(x)**3/np.expm1(np.asarray(x))
def debye_lowT_ratio(T_over_theta): return (12*np.pi**4/5)*np.asarray(T_over_theta)**3
def phase_space_density(n,m,T,g=1.0): return n*thermal_wavelength(m,T)**3/g
