from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from scattering_companion import *
OUT=Path(__file__).resolve().parents[3]/'generated/ch31/computational'; OUT.mkdir(parents=True,exist_ok=True)
def save(name,x,y,xlabel,ylabel):
    plt.figure(figsize=(5.2,3.2)); plt.plot(x,y); plt.xlabel(xlabel); plt.ylabel(ylabel); plt.tight_layout(); plt.savefig(OUT/name); plt.close()
q=np.linspace(0,6,300); save('born_gaussian.pdf',q,abs(gaussian_born(q))**2,'q a','|f|^2')
save('yukawa_cross_section.pdf',q,abs(yukawa_born(q))**2,'q/kappa','|f|^2')
th=np.linspace(0,np.pi,300); save('partial_wave_convergence.pdf',th,abs(partial_wave_amplitude(th,1,[.8,.4,.15]))**2,'theta','d sigma/d Omega')
E=np.linspace(-3,3,400); save('phase_shift_resonance.pdf',E,breit_wigner_phase(E,0,1),'E-E_R','delta')
d=np.linspace(0,1.4,200); save('optical_theorem_check.pdf',d,[abs(optical_residual(1,[x])) for x in d],'delta_0','residual')
k=np.linspace(.01,1,300); save('effective_range_plot.pdf',k,np.real(1/effective_range_amplitude(k,2,.7)),'k','Re(1/f)')
x=np.linspace(.05,4.5,600); a=np.clip([square_well_scattering_length(1,t) for t in x],-8,8); save('square_well_scattering_length.pdf',x,a,'kappa R','a/R')
E=np.linspace(-1,3,400); save('coupled_channel_threshold.pdf',E,np.where(E>0,np.sqrt(E),0),'E-E_th','channel momentum')
save('breit_wigner_cross_section.pdf',E,abs((breit_wigner_s(E,1,.4)-1)/(2j))**2,'E','resonant strength')
