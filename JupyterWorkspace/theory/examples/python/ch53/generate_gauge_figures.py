"""Generate Commit 585 computational vector figures and diagnostics."""
from __future__ import annotations
from pathlib import Path
import json
import numpy as np
import matplotlib.pyplot as plt

from gauge_quantitative import (
    ab_interference_probability,
    diagnostics,
    electric_currents_two_gauges,
    flux_quantum,
    magnetic_currents_two_gauges,
    magnetic_translation_commutator_phase,
    ring_energies,
    pulse_vector_potential_and_field,
    anharmonic_length_velocity_error,
    plaquette_wilson_loop,
    ring_link_hamiltonian,
    adiabaticity_parameter,
    twisted_boundary_spectrum,
    local_gauge_transform,
    local_gauge_transform_state,
    bond_current_matrix,
    continuity_finite_difference_residual,
)

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "generated/ch53/computational"
OUT.mkdir(parents=True, exist_ok=True)


def save(fig, name: str):
    fig.tight_layout()
    fig.savefig(OUT / name, bbox_inches="tight")
    plt.close(fig)


def electric_current_figure():
    x=np.linspace(-5,5,1000)
    js,jv=electric_currents_two_gauges(x,t=1.1,E=0.7,k=1.0,sigma=1.2)
    fig,ax=plt.subplots(figsize=(6.2,3.7))
    ax.plot(x,js,label="scalar-potential gauge")
    ax.plot(x,jv,"--",label="time-dependent vector gauge")
    ax.set_xlabel("x (dimensionless)")
    ax.set_ylabel("current density")
    ax.set_title("Uniform electric field: gauge-invariant current")
    ax.legend()
    save(fig,"uniform_electric_gauge_current.pdf")


def magnetic_current_figure():
    grid=np.linspace(-3,3,81)
    (jlx,jly),(jsx,jsy),rho=magnetic_currents_two_gauges(grid,grid,B=0.8,kx=0.8,ky=-0.25)
    mid=len(grid)//2
    # Compare y-current on y=0 cut; the two curves lie on top of one another.
    fig,ax=plt.subplots(figsize=(6.2,3.7))
    ax.plot(grid,jly[mid,:],label="Landau gauge")
    ax.plot(grid,jsy[mid,:],"--",label="symmetric gauge")
    ax.set_xlabel("x at y=0")
    ax.set_ylabel("j_y")
    ax.set_title("Uniform magnetic field: identical mechanical current")
    ax.legend()
    save(fig,"uniform_magnetic_gauge_current.pdf")


def translation_phase_figure():
    f=np.linspace(-1.5,1.5,601)
    # q=-1,hbar=1, choose B=1 and area=f*Phi0.
    phi0=flux_quantum()
    phases=np.array([np.angle(magnetic_translation_commutator_phase((1,0),(0,ff*phi0),B=1.0)) for ff in f])
    fig,ax=plt.subplots(figsize=(6.2,3.7))
    ax.plot(f,phases)
    ax.set_xlabel(r"enclosed cell flux $\Phi/\Phi_0$")
    ax.set_ylabel("commutator phase (rad)")
    ax.set_title("Projective magnetic-translation phase")
    save(fig,"magnetic_translation_phase.pdf")


def ab_interference_figure():
    f=np.linspace(-1.5,1.5,1001)
    phi0=flux_quantum()
    p=ab_interference_probability(f*phi0,visibility=0.9,dynamical_phase=0.18)
    fig,ax=plt.subplots(figsize=(6.2,3.7))
    ax.plot(f,p)
    ax.set_xlabel(r"enclosed flux $\Phi/\Phi_0$")
    ax.set_ylabel("normalized output probability")
    ax.set_title("Aharonov-Bohm interferometer")
    save(fig,"ab_interference_flux.pdf")


def ring_spectral_flow_figure():
    f=np.linspace(-1.5,1.5,701)
    phi0=flux_quantum()
    fig,ax=plt.subplots(figsize=(6.2,3.9))
    for n in range(-3,4):
        ax.plot(f,ring_energies(n,f*phi0),label=f"n={n}")
    ax.set_ylim(0,4.5)
    ax.set_xlabel(r"flux $\Phi/\Phi_0$")
    ax.set_ylabel(r"$E/(\hbar^2/2mR^2)$")
    ax.set_title("Flux-threaded ring spectral flow")
    ax.legend(ncol=2,fontsize=8)
    save(fig,"ab_ring_spectral_flow.pdf")



def time_dependent_pulse_figure():
    t=np.linspace(-6,6,1600)
    A,E=pulse_vector_potential_and_field(t,A0=1.0,tau=2.0,omega=1.35)
    fig,ax=plt.subplots(figsize=(6.2,3.7))
    ax.plot(t,A,label=r"$A(t)$")
    ax.plot(t,E,label=r"$E(t)=-\dot A(t)$")
    ax.set_xlabel("time (dimensionless)")
    ax.set_ylabel("field amplitude")
    ax.set_title("Time-dependent electromagnetic pulse")
    ax.legend()
    save(fig,"time_dependent_pulse_fields.pdf")


def length_velocity_convergence_figure():
    Ns=np.arange(6,42,2)
    err=np.array([anharmonic_length_velocity_error(int(N)) for N in Ns])
    fig,ax=plt.subplots(figsize=(6.2,3.7))
    ax.semilogy(Ns,err,marker="o")
    ax.set_xlabel("truncated oscillator basis size N")
    ax.set_ylabel("length-velocity matrix-element mismatch")
    ax.set_title("Gauge-form convergence in an anharmonic model")
    save(fig,"length_velocity_truncation_convergence.pdf")


def wilson_loop_figure():
    f=np.linspace(-1.5,1.5,1000)
    phi0=flux_quantum()
    W=plaquette_wilson_loop(f*phi0)
    fig,ax=plt.subplots(figsize=(6.2,3.7))
    ax.plot(f,np.angle(W))
    ax.set_xlabel(r"plaquette flux $\Phi/\Phi_0$")
    ax.set_ylabel("Wilson-loop phase (rad)")
    ax.set_title("Gauge-invariant plaquette holonomy")
    save(fig,"wilson_loop_flux_phase.pdf")


def lattice_ring_gauge_spectra_figure():
    f=np.linspace(-1.0,1.0,260)
    N=8
    phi0=flux_quantum()
    eu=[]; ec=[]
    for ff in f:
        theta=-2*np.pi*ff  # q=-1, so q Phi/hbar = -2pi Phi/Phi0
        eu.append(np.linalg.eigvalsh(ring_link_hamiltonian(N,theta,gauge="uniform")))
        ec.append(np.linalg.eigvalsh(ring_link_hamiltonian(N,theta,gauge="concentrated")))
    eu=np.asarray(eu); ec=np.asarray(ec)
    fig,ax=plt.subplots(figsize=(6.2,3.9))
    for k in range(N):
        ax.plot(f,eu[:,k])
        ax.plot(f,ec[:,k],"--",alpha=0.65)
    ax.set_xlabel(r"flux $\Phi/\Phi_0$")
    ax.set_ylabel("tight-binding energy / t")
    ax.set_title("Lattice-ring spectra in two link gauges")
    save(fig,"lattice_ring_gauge_spectra.pdf")



def adiabaticity_figure():
    lam=np.linspace(-2.2,2.2,900)
    fig,ax=plt.subplots(figsize=(6.2,3.7))
    for rate in (0.015,0.06):
        ax.plot(lam,adiabaticity_parameter(lam,gap=0.6,slope=1.0,sweep_rate=rate),label=fr"$|\dot\lambda|={rate}$")
    ax.set_xlabel(r"control parameter $\lambda$")
    ax.set_ylabel(r"adiabaticity $\eta$")
    ax.set_title("Slow electromagnetic control near an avoided crossing")
    ax.legend()
    save(fig,"adiabaticity_parameter.pdf")


def twisted_boundary_spectrum_figure():
    f=np.linspace(-1.0,1.0,300)
    N=9
    vals=np.asarray([twisted_boundary_spectrum(N,-2*np.pi*ff) for ff in f])
    fig,ax=plt.subplots(figsize=(6.2,3.9))
    for k in range(N):
        ax.plot(f,vals[:,k])
    ax.set_xlabel(r"boundary twist / $2\pi$ (equiv. $\Phi/\Phi_0$)")
    ax.set_ylabel("tight-binding energy / t")
    ax.set_title("Flux spectral flow encoded by a boundary twist")
    save(fig,"twisted_boundary_spectrum.pdf")


def lattice_bond_current_gauge_figure():
    N=14; theta=0.91
    H=ring_link_hamiltonian(N,theta,gauge="uniform")
    x=np.arange(N,dtype=float)
    psi=np.exp(-0.08*(x-(N-1)/2)**2+1j*0.43*x); psi/=np.linalg.norm(psi)
    chi=0.5*np.sin(0.8*x)+0.07*x*x/N
    Hp=local_gauge_transform(H,chi)
    psip=local_gauge_transform_state(psi,chi)
    J=bond_current_matrix(H,psi); Jp=bond_current_matrix(Hp,psip)
    bonds=np.arange(N)
    vals=np.array([J[i,(i+1)%N] for i in range(N)])
    valsp=np.array([Jp[i,(i+1)%N] for i in range(N)])
    fig,ax=plt.subplots(figsize=(6.2,3.7))
    ax.plot(bonds,vals,marker="o",label="original link gauge")
    ax.plot(bonds,valsp,"--",marker="x",label="local site-gauge transformed")
    ax.set_xlabel("oriented bond i -> i+1")
    ax.set_ylabel("probability current")
    ax.set_title("Bondwise gauge invariance of lattice current")
    ax.legend()
    save(fig,"lattice_bond_current_gauge_closure.pdf")


def lattice_continuity_convergence_figure():
    N=11; H=ring_link_hamiltonian(N,0.64,gauge="uniform")
    x=np.arange(N,dtype=float)
    psi=np.exp(-0.12*(x-5.0)**2+1j*0.38*x); psi/=np.linalg.norm(psi)
    dts=np.logspace(-3,-0.7,14)
    res=np.array([continuity_finite_difference_residual(H,psi,float(dt)) for dt in dts])
    fig,ax=plt.subplots(figsize=(6.2,3.7))
    ax.loglog(dts,res,marker="o")
    ax.set_xlabel(r"centered difference step $\Delta t$")
    ax.set_ylabel("max local continuity residual")
    ax.set_title("Quadratic convergence of local continuity")
    save(fig,"lattice_continuity_convergence.pdf")

def main():
    electric_current_figure()
    magnetic_current_figure()
    translation_phase_figure()
    ab_interference_figure()
    ring_spectral_flow_figure()
    time_dependent_pulse_figure()
    length_velocity_convergence_figure()
    wilson_loop_figure()
    lattice_ring_gauge_spectra_figure()
    adiabaticity_figure()
    twisted_boundary_spectrum_figure()
    lattice_bond_current_gauge_figure()
    lattice_continuity_convergence_figure()
    d=diagnostics()
    payload={
        "commit":585,
        "units":"dimensionless hbar=m=1, q=-1 unless otherwise stated",
        "electric_current_max_difference":d.electric_current_max_difference,
        "magnetic_current_max_difference":d.magnetic_current_max_difference,
        "flux_quantum":d.flux_quantum,
        "translation_phase_at_one_flux_quantum":{
            "real":d.translation_phase_at_one_flux_quantum.real,
            "imag":d.translation_phase_at_one_flux_quantum.imag,
        },
        "ab_periodicity_max_difference":d.ab_periodicity_max_difference,
        "ring_relabel_max_difference":d.ring_relabel_max_difference,
        "lattice_ring_gauge_spectrum_max_difference":d.lattice_ring_gauge_spectrum_max_difference,
        "wilson_one_flux_max_difference":d.wilson_one_flux_max_difference,
        "length_velocity_error_N8":d.length_velocity_error_N8,
        "length_velocity_error_N32":d.length_velocity_error_N32,
        "adiabatic_eta_slow":d.adiabatic_eta_slow,
        "adiabatic_eta_fast":d.adiabatic_eta_fast,
        "landau_zener_slow":d.landau_zener_slow,
        "landau_zener_fast":d.landau_zener_fast,
        "twisted_boundary_spectrum_max_difference":d.twisted_boundary_spectrum_max_difference,
        "bond_current_gauge_max_difference":d.bond_current_gauge_max_difference,
        "continuity_algebra_max_residual":d.continuity_algebra_max_residual,
        "continuity_fd_dt_1e2":d.continuity_fd_dt_1e2,
        "continuity_fd_dt_5e3":d.continuity_fd_dt_5e3,
        "computational_figures":13,
    }
    (OUT/"gauge_diagnostics.json").write_text(json.dumps(payload,indent=2)+"\n",encoding="utf-8")


if __name__ == "__main__":
    main()
