from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from quantum_statistics_companion import *
out=Path(__file__).resolve().parents[3]/'generated/ch32/computational'; out.mkdir(parents=True,exist_ok=True)
def save(name,x,y,xlabel,ylabel):
    fig,ax=plt.subplots(figsize=(5.2,3.4)); ax.plot(x,y); ax.set_xlabel(xlabel); ax.set_ylabel(ylabel); ax.grid(True,alpha=.25); fig.tight_layout(); fig.savefig(out/name); plt.close(fig)
x=np.linspace(.08,6,400); save('be_fd_occupations.pdf',x,bose_occupation(x),r'$(\epsilon-\mu)/k_BT$',r'$\bar n_B$');
z=np.linspace(.01,.999,300); approx=ZETA32*(1-np.sqrt(1-z)); save('bose_function_saturation.pdf',z,approx,'fugacity $z$',r'$g_{3/2}(z)$ (scaled model)')
t=np.linspace(0,1.2,300); save('condensate_fraction_curve.pdf',t,condensate_fraction(t,1),'$T/T_c$','$N_0/N$')
n=np.logspace(18,22,200); save('critical_temperature_scaling.pdf',n,n**(2/3)/n[0]**(2/3),'density $n$ (arb.)','$T_c/T_{c0}$')
e=np.linspace(-4,4,400); fig,ax=plt.subplots(figsize=(5.2,3.4)); [ax.plot(e,fermi_occupation(e,kT=t),label=f'kT={t}') for t in (.2,.5,1)]; ax.legend(); ax.set_xlabel(r'$(\epsilon-\mu)$'); ax.set_ylabel(r'$\bar n_F$'); ax.grid(True,alpha=.25); fig.tight_layout(); fig.savefig(out/'fermi_step_temperature.pdf'); plt.close(fig)
n=np.logspace(26,30,200); save('fermi_pressure_density.pdf',n,n**(5/3)/n[0]**(5/3),'density $n$ (arb.)','$P/P_0$')
x=np.linspace(.05,12,400); save('planck_spectrum_scaled.pdf',x,planck_scaled(x),r'$\hbar\omega/k_BT$',r'$x^3/(e^x-1)$')
t=np.linspace(.005,.15,250); save('debye_heat_capacity_scaled.pdf',t,debye_lowT_ratio(t),'$T/\Theta_D$','$C_V/(Nk_B)$ low-$T$')
t=np.logspace(-2,1,250); save('quantum_degeneracy_map.pdf',t,t**(-1.5),'scaled temperature','scaled $n\lambda_T^3$')
