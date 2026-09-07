from __future__ import annotations

import json
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt

from bound_engineered_systems import (
    finite_well_energy_ratios,
    rectangular_barrier_transmission,
    wkb_rectangular_transmission,
    multilayer_transmission,
    finite_difference_spectrum,
    symmetric_square_well_potential,
    density_of_states_shape,
    variable_mass_eigensystem,
    exterior_probability,
    symmetric_double_well_potential,
    double_well_splitting,
    tilted_potential,
    two_level_energies,
    two_level_polarization,
    lorentzian_transmission,
    landauer_conductance_dimensionless,
    poisson_dirichlet_1d,
)

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "generated/ch51/computational"
OUT.mkdir(parents=True, exist_ok=True)


def finite_well_spectrum():
    z0s = np.linspace(0.25, 6.0, 180)
    branches = [[] for _ in range(4)]
    xs = [[] for _ in range(4)]
    for z0 in z0s:
        vals = finite_well_energy_ratios(float(z0))
        for j, val in enumerate(vals[:4]):
            xs[j].append(z0); branches[j].append(val)
    fig, ax = plt.subplots(figsize=(6.8, 4.1))
    for j in range(4):
        if xs[j]: ax.plot(xs[j], branches[j], label=f"state {j+1}")
    ax.axhline(0.0, linewidth=0.8)
    ax.set(xlabel=r"dimensionless depth $z_0$", ylabel=r"$E/V_0$", ylim=(-1.02,0.05))
    ax.legend(frameon=False, ncol=2)
    fig.tight_layout(); fig.savefig(OUT/'finite_well_spectrum.pdf'); plt.close(fig)


def barrier_comparison():
    E = np.linspace(0.04, 0.92, 220)
    exact = rectangular_barrier_transmission(E, 1.0, 2.2)
    wkb = wkb_rectangular_transmission(E, 1.0, 2.2)
    fig, ax = plt.subplots(figsize=(6.8, 4.1))
    ax.semilogy(E, exact, label='exact')
    ax.semilogy(E, wkb, '--', label='leading WKB')
    ax.set(xlabel=r"$E/V_0$ (with $V_0=1$)", ylabel='transmission', ylim=(1e-4,1.2))
    ax.legend(frameon=False)
    fig.tight_layout(); fig.savefig(OUT/'barrier_exact_vs_wkb.pdf'); plt.close(fig)


def double_barrier():
    E = np.linspace(0.04, 0.99, 1200)
    seg=[(1.0,0.55),(0.0,2.0),(1.0,0.55)]
    T=np.array([multilayer_transmission(float(e),seg) for e in E])
    fig, ax = plt.subplots(figsize=(6.8, 4.1))
    ax.plot(E,T)
    ax.set(xlabel='energy', ylabel='transmission', ylim=(-0.02,1.05))
    fig.tight_layout(); fig.savefig(OUT/'double_barrier_resonances.pdf'); plt.close(fig)
    return float(E[np.argmax(T)]), float(T.max())


def fd_convergence():
    depth, a, L = 1.0, 1.4, 8.0
    xref=np.linspace(-L,L,641); vref=symmetric_square_well_potential(xref,depth,a)
    ref=float(finite_difference_spectrum(xref,vref,levels=1)[0])
    ns=np.array([81,101,141,181,241,321])
    errs=[]; dxs=[]
    for n in ns:
        x=np.linspace(-L,L,int(n)); v=symmetric_square_well_potential(x,depth,a)
        e=float(finite_difference_spectrum(x,v,levels=1)[0])
        dxs.append(x[1]-x[0]); errs.append(abs(e-ref))
    fig,ax=plt.subplots(figsize=(6.8,4.1))
    ax.loglog(dxs,errs,'o-')
    ax.set(xlabel=r"grid spacing $\Delta x$",ylabel='ground-state absolute error')
    fig.tight_layout(); fig.savefig(OUT/'fd_convergence.pdf'); plt.close(fig)
    return ref, float(errs[-1])


def density_of_states_figure():
    e=np.linspace(-0.05,1.2,500)
    fig,ax=plt.subplots(figsize=(6.8,4.1))
    ax.plot(e,density_of_states_shape(e,0.0,3),label='3D')
    ax.plot(e,density_of_states_shape(e,0.0,2),label='2D')
    one=density_of_states_shape(e,0.0,1); one=np.minimum(one,6.0)
    ax.plot(e,one,label='1D')
    zero=density_of_states_shape(e,0.35,0,broadening=0.035); zero=zero/zero.max()*1.8
    ax.plot(e,zero,label='0D (broadened line)')
    ax.set(xlabel='energy above reference edge',ylabel='relative density of states',ylim=(0,6.2))
    ax.legend(frameon=False); fig.tight_layout(); fig.savefig(OUT/'density_of_states_dimensionality.pdf'); plt.close(fig)


def effective_mass_levels():
    x=np.linspace(-7,7,241); depth=1.0; a=1.2
    v=symmetric_square_well_potential(x,depth,a)
    masses=np.linspace(0.7,3.0,28); levels=[]; leaks=[]
    for mb in masses:
        m=np.where(np.abs(x)<a,1.0,mb)
        vals,vecs=variable_mass_eigensystem(x,v,m,levels=2)
        levels.append(vals); leaks.append(exterior_probability(x,vecs[:,0],a))
    levels=np.asarray(levels)
    fig,ax=plt.subplots(figsize=(6.8,4.1))
    ax.plot(masses,levels[:,0],label='ground')
    ax.plot(masses,levels[:,1],label='first excited')
    ax.axhline(0.0,linewidth=0.8)
    ax.set(xlabel='barrier effective mass / well mass',ylabel='energy')
    ax.legend(frameon=False); fig.tight_layout(); fig.savefig(OUT/'effective_mass_well_levels.pdf'); plt.close(fig)
    fig,ax=plt.subplots(figsize=(6.8,4.1)); ax.plot(masses,leaks)
    ax.set(xlabel='barrier effective mass / well mass',ylabel='ground-state exterior probability')
    fig.tight_layout(); fig.savefig(OUT/'leakage_vs_barrier_mass.pdf'); plt.close(fig)
    return float(leaks[0]),float(leaks[-1])


def double_well_splitting_figure():
    x=np.linspace(-6,6,241); barriers=np.linspace(0.0,2.5,35); spl=[]
    for b in barriers:
        v=symmetric_double_well_potential(x,central_barrier=float(b))
        spl.append(double_well_splitting(x,v))
    fig,ax=plt.subplots(figsize=(6.8,4.1)); ax.semilogy(barriers,spl)
    ax.set(xlabel='central barrier height',ylabel='lowest-doublet splitting')
    fig.tight_layout(); fig.savefig(OUT/'double_well_splitting.pdf'); plt.close(fig)
    return float(spl[0]),float(spl[-1])



def tilted_well_stark_figure():
    x=np.linspace(-2.0,2.0,241)
    slopes=np.linspace(-0.35,0.35,61)
    levels=[]
    for slope in slopes:
        v=tilted_potential(x,np.zeros_like(x),float(slope))
        levels.append(finite_difference_spectrum(x,v,levels=3))
    levels=np.asarray(levels)
    fig,ax=plt.subplots(figsize=(6.8,4.1))
    for j in range(3):
        ax.plot(slopes,levels[:,j],label=f'level {j+1}')
    ax.set(xlabel=r'energy slope $F$',ylabel='hard-wall eigenenergy')
    ax.legend(frameon=False)
    fig.tight_layout(); fig.savefig(OUT/'tilted_well_stark_levels.pdf'); plt.close(fig)
    center=len(slopes)//2
    curvature=(levels[center+1,0]-2*levels[center,0]+levels[center-1,0])/(slopes[center+1]-slopes[center])**2
    return float(curvature)


def anticrossing_spectroscopy_figure():
    det=np.linspace(-1.2,1.2,300); t=0.18
    e=two_level_energies(det,t); pol=two_level_polarization(det,t)
    fig,ax=plt.subplots(figsize=(6.8,4.1))
    ax.plot(det,e[:,0],label='lower branch')
    ax.plot(det,e[:,1],label='upper branch')
    ax.set(xlabel=r'detuning $\delta$',ylabel='energy')
    ax.legend(frameon=False)
    fig.tight_layout(); fig.savefig(OUT/'coupled_well_anticrossing.pdf'); plt.close(fig)
    fig,ax=plt.subplots(figsize=(6.8,4.1))
    ax.plot(det,pol)
    ax.set(xlabel=r'detuning $\delta$',ylabel=r'ground-state $\langle\sigma_z\rangle$',ylim=(-1.05,1.05))
    fig.tight_layout(); fig.savefig(OUT/'coupled_well_polarization.pdf'); plt.close(fig)
    return float(e[len(det)//2,1]-e[len(det)//2,0])


def landauer_thermal_figure():
    e=np.linspace(-1.5,1.5,1801); T=lorentzian_transmission(e,0.0,0.22,peak=1.0)
    mus=np.linspace(-0.8,0.8,300)
    fig,ax=plt.subplots(figsize=(6.8,4.1))
    for kT in (0.0,0.04,0.10):
        g=[landauer_conductance_dimensionless(e,T,float(mu),kT,degeneracy=2.0) for mu in mus]
        ax.plot(mus,g,label=rf'$k_BT={kT:.2f}$')
    ax.set(xlabel=r'chemical potential $\mu$',ylabel=r'$G/(e^2/h)$')
    ax.legend(frameon=False)
    fig.tight_layout(); fig.savefig(OUT/'landauer_resonance_thermal_broadening.pdf'); plt.close(fig)
    return float(landauer_conductance_dimensionless(e,T,0.0,0.0,degeneracy=2.0))


def poisson_response_figure():
    x=np.linspace(-1.0,1.0,241)
    rho=np.exp(-0.5*(x/0.24)**2)
    phi=poisson_dirichlet_1d(x,rho,permittivity=1.0)
    fig,ax=plt.subplots(figsize=(6.8,4.1))
    ax.plot(x,rho/rho.max(),label='charge density (scaled)')
    ax.plot(x,phi/phi.max(),label='electrostatic potential (scaled)')
    ax.set(xlabel='position',ylabel='normalized response')
    ax.legend(frameon=False)
    fig.tight_layout(); fig.savefig(OUT/'poisson_charge_response.pdf'); plt.close(fig)
    return float(phi.max())


def main():
    finite_well_spectrum(); barrier_comparison(); resonance_energy,resonance_T=double_barrier(); ref,err=fd_convergence()
    density_of_states_figure(); leak_lo,leak_hi=effective_mass_levels(); split_lo,split_hi=double_well_splitting_figure()
    stark_curvature=tilted_well_stark_figure(); anticrossing_gap=anticrossing_spectroscopy_figure()
    landauer_peak=landauer_thermal_figure(); poisson_peak=poisson_response_figure()
    diagnostics={
        'commit':574,
        'finite_well_figures':4,
        'double_barrier_peak_energy':resonance_energy,
        'double_barrier_peak_transmission':resonance_T,
        'fd_reference_ground_energy':ref,
        'fd_finest_nonreference_error':err,
        'barrier_mass_leakage_low':leak_lo,
        'barrier_mass_leakage_high':leak_hi,
        'double_well_splitting_low_barrier':split_lo,
        'double_well_splitting_high_barrier':split_hi,
        'symmetric_box_ground_stark_curvature':stark_curvature,
        'two_level_anticrossing_gap_near_zero':anticrossing_gap,
        'zero_temperature_landauer_peak_dimensionless':landauer_peak,
        'poisson_gaussian_charge_peak_potential':poisson_peak,
        'computational_figures':13,
    }
    (OUT/'diagnostics.json').write_text(json.dumps(diagnostics,indent=2)+"\n",encoding='utf-8')

if __name__=='__main__': main()
