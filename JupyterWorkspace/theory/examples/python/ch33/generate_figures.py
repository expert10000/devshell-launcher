from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from relativistic_quantum_companion import *
OUT=Path(__file__).resolve().parents[3]/'generated/ch33/computational'; OUT.mkdir(parents=True,exist_ok=True)
def save(name,x,y,xlab,ylab):
    fig,ax=plt.subplots(figsize=(5.2,3.2)); ax.plot(x,y); ax.set_xlabel(xlab); ax.set_ylabel(ylab); ax.grid(True,alpha=.25); fig.tight_layout(); fig.savefig(OUT/f'{name}.pdf'); plt.close(fig)
p=np.linspace(0,5,300); save('relativistic_energy',p,relativistic_energy(p),'p/(mc)','E/(mc^2)')
save('group_velocity',p,velocity_from_p(p),'p/(mc)','v/c')
save('small_component',p,lower_upper_ratio(p),'p/(mc)','lower/upper')
b=np.linspace(0,.95,300); save('lorentz_gamma',b,gamma_factor(b),'beta','gamma')
e=np.linspace(1.01,20,300); save('chirality_mixing',e,chirality_mix_scale(1,e),'E/m','m/E')
Z=np.arange(1,81); save('dirac_1s_binding',Z,1-np.array([dirac_coulomb_energy(1,.5,z) for z in Z]),'Z','1-E/mc^2')
n=np.arange(1,8); save('fine_structure_scale',n,np.abs([fine_structure_shift(int(i),.5) for i in n]),'n','|Delta E|')
k=np.linspace(0,5,300); save('kg_dispersion',k,kg_frequency(k),'k','omega')
B=np.linspace(0,5,100); save('pauli_zeeman',B,pauli_zeeman(B),'B','Zeeman splitting')
