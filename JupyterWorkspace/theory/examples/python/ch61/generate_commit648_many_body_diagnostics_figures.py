from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from many_body_diagnostics import *
def save(fig,p): p.parent.mkdir(parents=True,exist_ok=True); fig.tight_layout(); fig.savefig(p); plt.close(fig)
def main(outdir):
 out=Path(outdir); U=np.linspace(-8,8,140)
 fig,ax=plt.subplots(); ax.plot(U,[double_occupancy(u) for u in U]); ax.set(xlabel=r'$U/t$',ylabel='double occupancy',title='Hubbard-dimer double occupancy'); save(fig,out/'hubbard_double_occupancy.pdf')
 fig,ax=plt.subplots(); ax.plot(U,[bose_number_variance(u,N=4) for u in U]); ax.set(xlabel=r'$U/J$',ylabel='site-number variance',title='Bose-Hubbard number fluctuations'); save(fig,out/'bose_hubbard_number_fluctuations.pdf')
 c,s,p=finite_gap_schematic(U); fig,ax=plt.subplots(); ax.plot(U,c,label='charge'); ax.plot(U,s,label='spin'); ax.plot(U,p,label='pair'); ax.set(xlabel='interaction',ylabel='finite-system gap',title='Charge, spin, and pair gaps'); ax.legend(); save(fig,out/'many_body_gap_comparison.pdf')
 fig,ax=plt.subplots(); ax.plot(U,structure_factor_proxy(U)); ax.set(xlabel='interaction',ylabel=r'$S(\pi)$',title='Structure-factor diagnostic'); save(fig,out/'structure_factor_parameter_sweep.pdf')
 fig,ax=plt.subplots(); ax.plot(U,entanglement_entropy_proxy(U)); ax.set(xlabel='interaction',ylabel='bipartite entropy',title='Entanglement entropy'); save(fig,out/'entanglement_entropy_interaction.pdf')
 fig,ax=plt.subplots(); ax.plot(U,fidelity_susceptibility_proxy(U)); ax.set(xlabel='interaction',ylabel='fidelity susceptibility',title='Fidelity-susceptibility peak'); save(fig,out/'fidelity_susceptibility.pdf')
 L=np.arange(4,80); fig,ax=plt.subplots(); ax.plot(L,finite_size_gap(L,True),label='critical-like'); ax.plot(L,finite_size_gap(L,False),label='gapped'); ax.set(xlabel='system size',ylabel='finite-size gap',title='Finite-size gap scaling'); ax.legend(); save(fig,out/'finite_size_gap_scaling.pdf')
 sites=np.arange(2,10); vals=[symmetry_block_dimensions(int(n)) for n in sites]; fig,ax=plt.subplots(); [ax.semilogy(sites,[v[j] for v in vals],label=l) for j,l in enumerate(['full','fixed N','momentum','parity'])]; ax.set(xlabel='sites',ylabel='block dimension',title='Symmetry-sector reduction'); ax.legend(); save(fig,out/'symmetry_block_reduction.pdf')
 r=np.arange(20); fig,ax=plt.subplots(); ax.plot(r,pair_correlation_distance(r),label='short-range'); ax.plot(r,pair_correlation_distance(r,ordered=True),label='ordered proxy'); ax.set(xlabel='distance',ylabel='pair correlation',title='Pair correlations versus distance'); ax.legend(); save(fig,out/'pair_correlation_distance.pdf')
 modes=np.arange(4,25); fig,ax=plt.subplots(); ax.semilogy(modes,[ed_dimension(int(m)) for m in modes],label='full Fock'); ax.semilogy(modes,[ed_dimension(int(m),int(m//2)) for m in modes],label='fixed N'); ax.set(xlabel='fermionic modes',ylabel='Hilbert dimension',title='Exact-diagonalization cost scaling'); ax.legend(); save(fig,out/'exact_diagonalization_cost_scaling.pdf')
if __name__=='__main__':
 import sys; main(sys.argv[1] if len(sys.argv)>1 else 'generated/ch61/computational')
