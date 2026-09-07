from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from bcs_mean_field import *
def save(fig,p): p.parent.mkdir(parents=True,exist_ok=True); fig.tight_layout(); fig.savefig(p); plt.close(fig)
def main(outdir):
 out=Path(outdir); lam=np.linspace(.12,1,200)
 fig,ax=plt.subplots(); ax.semilogy(lam,cooper_binding(lam)); ax.set(xlabel='dimensionless attraction',ylabel='binding scale',title='Cooper binding from weak attraction'); save(fig,out/'cooper_binding_energy.pdf')
 xi=np.linspace(-3,3,500); E=bogoliubov_spectrum(xi,1)
 fig,ax=plt.subplots(); ax.plot(xi,xi,label='normal particle'); ax.plot(xi,-xi,label='normal hole'); ax.plot(xi,E,label='Bogoliubov +E'); ax.plot(xi,-E,label='Bogoliubov -E'); ax.set(xlabel=r'$\xi_k$',ylabel='energy',title='Normal and Bogoliubov dispersions'); ax.legend(); save(fig,out/'bogoliubov_dispersion.pdf')
 u,v=coherence_factors(xi,1); fig,ax=plt.subplots(); ax.plot(xi,u,label=r'$u_k^2$'); ax.plot(xi,v,label=r'$v_k^2$'); ax.set(xlabel=r'$\xi_k$',ylabel='weight',title='BCS coherence factors'); ax.legend(); save(fig,out/'bcs_coherence_factors.pdf')
 T=np.linspace(0,1.05,300); d=bcs_gap_temperature(T); fig,ax=plt.subplots(); ax.plot(T,d/d[0]); ax.set(xlabel=r'$T/T_c$',ylabel=r'$\Delta(T)/\Delta(0)$',title='BCS gap versus temperature'); save(fig,out/'bcs_gap_vs_temperature.pdf')
 Eg=np.linspace(-3,3,800); fig,ax=plt.subplots(); ax.plot(Eg,bcs_dos(Eg,1,.035)); ax.set(xlabel=r'$E/\Delta$',ylabel=r'$N_s/N_0$',title='Superconducting density of states'); save(fig,out/'bcs_density_of_states.pdf')
 ds=np.linspace(0,2,150); fig,ax=plt.subplots(); ax.plot(ds,[condensation_energy(x) for x in ds]); ax.set(xlabel=r'$\Delta$',ylabel='condensation energy',title='BCS condensation energy'); save(fig,out/'bcs_condensation_energy.pdf')
 ns=np.arange(6,82,2); gaps=[finite_size_gap(int(n)) for n in ns]; fig,ax=plt.subplots(); ax.plot(ns,gaps,marker='.'); ax.set(xlabel='active levels',ylabel='self-consistent gap',title='Finite-size gap convergence'); save(fig,out/'finite_size_gap_convergence.pdf')
 U=np.linspace(-8,-.1,200); fig,ax=plt.subplots(); ax.plot(U,attractive_pair_binding_dimer(U),label='dimer pair binding'); ax.plot(U,np.sqrt(np.maximum(0,-U-.1)),label='bulk-gap proxy'); ax.set(xlabel=r'$U/t$',ylabel='pairing scale',title='Attractive-Hubbard to BCS bridge'); ax.legend(); save(fig,out/'attractive_hubbard_bcs_bridge.pdf')
if __name__=='__main__':
 import sys; main(sys.argv[1] if len(sys.argv)>1 else 'generated/ch61/computational')
