from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from tensor_network_diagnostics import *
def save(fig,p): p.parent.mkdir(parents=True,exist_ok=True); fig.tight_layout(); fig.savefig(p); plt.close(fig)
def main(outdir):
 out=Path(outdir)
 p=schmidt_probabilities(); x=np.arange(1,31)
 fig,ax=plt.subplots(); ax.semilogy(x,p[:30],marker="."); ax.set(xlabel="Schmidt index",ylabel="probability",title="Decaying Schmidt spectrum"); save(fig,out/"schmidt_spectrum_truncation.pdf")
 chi=np.arange(2,129)
 fig,ax=plt.subplots(); ax.semilogy(chi,[discarded_weight(c) for c in chi]); ax.set(xlabel=r"$\chi$",ylabel="discarded weight",title="Truncation error versus bond dimension"); save(fig,out/"truncation_error_bond_dimension.pdf")
 fig,ax=plt.subplots(); ax.loglog(chi,variational_energy_error(chi)); ax.set(xlabel=r"$\chi$",ylabel="variational energy error",title="Energy convergence with bond dimension"); save(fig,out/"variational_energy_convergence.pdf")
 sw=np.arange(0,14)
 fig,ax=plt.subplots(); ax.semilogy(sw,dmrg_sweep_energy_error(sw)); ax.set(xlabel="sweep",ylabel="energy error",title="DMRG sweep convergence"); save(fig,out/"dmrg_sweep_energy.pdf")
 fig,ax=plt.subplots(); ax.plot(chi,[entropy_bound(c) for c in chi]); ax.set(xlabel=r"$\chi$",ylabel=r"$S_{\max}$ (bits)",title="Entanglement capacity of an MPS bond"); save(fig,out/"entropy_bond_dimension.pdf")
 r=np.arange(0,70)
 fig,ax=plt.subplots()
 for c in [8,16,32,64]: ax.semilogy(r,correlation_profile(r,c),label=rf"$\chi={c}$")
 ax.set(xlabel="distance",ylabel="correlation magnitude",title="Finite-entanglement correlation convergence"); ax.legend(); save(fig,out/"mps_correlation_convergence.pdf")
 L=np.arange(4,31)
 fig,ax=plt.subplots(); ax.semilogy(L,[full_state_dimension(int(l)) for l in L],label="full state"); ax.semilogy(L,[mps_parameter_count(int(l),chi=64) for l in L],label=r"MPS $\chi=64$")
 ax.set(xlabel="sites",ylabel="stored amplitudes / parameters",title="ED versus fixed-bond MPS scaling"); ax.legend(); save(fig,out/"ed_mps_scaling_comparison.pdf")
 cv=np.arange(4,129,4)
 fig,ax=plt.subplots(); ax.loglog(cv,[contraction_cost_proxy(40,chi=int(c)) for c in cv]); ax.set(xlabel=r"$\chi$",ylabel="cost proxy",title="Representative MPS contraction cost"); save(fig,out/"mps_cost_scaling.pdf")
if __name__=="__main__":
 import sys; main(sys.argv[1] if len(sys.argv)>1 else "generated/ch61/computational")
