from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from bdg_josephson import *
def save(fig,p): p.parent.mkdir(parents=True,exist_ok=True); fig.tight_layout(); fig.savefig(p); plt.close(fig)
def main(outdir):
 out=Path(outdir); xi=np.linspace(-3,3,400); em,ep=bdg_spectrum(xi,1)
 fig,ax=plt.subplots(); ax.plot(xi,em); ax.plot(xi,ep); ax.set(xlabel=r'$\xi$',ylabel='BdG energy',title='Particle-hole symmetric BdG spectrum'); save(fig,out/'bdg_particle_hole_spectrum.pdf')
 x=np.linspace(0,6,300); fig,ax=plt.subplots(); ax.plot(x,gap_profile(x)); ax.set(xlabel=r'$x/\xi_0$',ylabel=r'$\Delta(x)/\Delta_0$',title='Gap recovery near a boundary'); save(fig,out/'bdg_gap_profile_boundary.pdf')
 fig,ax=plt.subplots(); ax.plot(x,meissner_field(x)); ax.set(xlabel=r'$x/\lambda_L$',ylabel=r'$B/B_0$',title='Meissner-field penetration'); save(fig,out/'meissner_field_decay.pdf')
 flux=np.linspace(-1.5,1.5,500); fig,ax=plt.subplots(); [ax.plot(flux,ring_energy(flux,n),label=f'n={n}') for n in range(-2,3)]; ax.set(xlabel=r'$\Phi/\Phi_0$',ylabel='ring energy',title='Fluxoid winding sectors'); ax.legend(); save(fig,out/'superconducting_ring_flux_sectors.pdf')
 phi=np.linspace(-2*np.pi,2*np.pi,500); fig,ax=plt.subplots(); ax.plot(phi,josephson_energy(phi)); ax.set(xlabel=r'$\phi$',ylabel=r'$-E_J\cos\phi$',title='Josephson coupling energy'); save(fig,out/'josephson_energy_phase.pdf')
 fig,ax=plt.subplots(); ax.plot(flux,squid_critical_current(flux)); ax.set(xlabel=r'$\Phi/\Phi_0$',ylabel=r'$I_c/I_0$',title='Symmetric SQUID interference'); save(fig,out/'squid_critical_current.pdf')
 phi=np.linspace(-np.pi,np.pi,500); fig,ax=plt.subplots(); [ax.plot(phi,andreev_energy(phi,tau=t),label=rf'$\tau={t}$') for t in [.2,.6,.95]]; ax.set(xlabel=r'$\phi$',ylabel=r'$E_A/\Delta$',title='Andreev bound states'); ax.legend(); save(fig,out/'andreev_bound_states.pdf')
 fig,ax=plt.subplots(); [ax.plot(phi,andreev_current(phi,tau=t),label=rf'$\tau={t}$') for t in [.2,.6,.95]]; ax.set(xlabel=r'$\phi$',ylabel='normalized supercurrent',title='Andreev current-phase relation'); ax.legend(); save(fig,out/'josephson_current_phase_relation.pdf')
if __name__=='__main__':
 import sys; main(sys.argv[1] if len(sys.argv)>1 else 'generated/ch61/computational')
