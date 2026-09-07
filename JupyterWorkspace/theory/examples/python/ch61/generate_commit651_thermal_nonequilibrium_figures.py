from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from thermal_nonequilibrium import *
def save(fig,p): p.parent.mkdir(parents=True,exist_ok=True); fig.tight_layout(); fig.savefig(p); plt.close(fig)
def main(outdir):
 out=Path(outdir)
 E=np.array([0.,.7,1.6,2.8])
 T=np.linspace(.08,4,220)
 P=np.array([thermal_probabilities(E,1/t) for t in T])
 fig,ax=plt.subplots()
 for i in range(len(E)): ax.plot(T,P[:,i],label=f"level {i}")
 ax.set(xlabel="temperature",ylabel="probability",title="Finite-spectrum thermal populations"); ax.legend(); save(fig,out/"thermal_probabilities.pdf")
 beta=np.linspace(.2,12,300); C=np.array([heat_capacity([0.,1.],b) for b in beta]); temp=1/beta
 fig,ax=plt.subplots(); ax.plot(temp[::-1],C[::-1]); ax.set(xlabel="temperature",ylabel="heat capacity",title="Two-level Schottky anomaly"); save(fig,out/"specific_heat_schottky.pdf")
 T2=np.linspace(.05,5,250); fig,ax=plt.subplots(); ax.plot(T2,thermal_correlation_length(T2)); ax.set(xlabel="temperature",ylabel="correlation length",title="Thermal correlation-length crossover"); save(fig,out/"thermal_correlation_length.pdf")
 tt=np.linspace(0,40,600); surv=survival_probability(np.array([0.,.8,1.77,2.63]),np.array([.4,.3,.2,.1]),tt)
 fig,ax=plt.subplots(); ax.plot(tt,surv); ax.set(xlabel="time",ylabel="return probability",title="Quench survival and finite-size revivals"); save(fig,out/"quench_survival_loschmidt.pdf")
 fig,ax=plt.subplots(); ax.plot(tt,entanglement_growth(tt,v=.18,Smax=4)); ax.set(xlabel="time",ylabel="entanglement entropy",title="Post-quench entanglement growth"); save(fig,out/"entanglement_growth_quench.pdf")
 r=np.arange(0,31); t=np.linspace(0,18,240); R,Tm=np.meshgrid(r,t); Cc=light_cone(R,Tm)
 fig,ax=plt.subplots(); ax.imshow(Cc,origin="lower",aspect="auto",extent=[r.min(),r.max(),t.min(),t.max()]); ax.set(xlabel="distance",ylabel="time",title="Ballistic correlation front"); save(fig,out/"light_cone_spreading.pdf")
 om=np.linspace(-1,5,800); A=lorentzian_spectrum(om,[.3,1.1,2.0,3.6],[1,.7,.45,.2],.07)
 fig,ax=plt.subplots(); ax.plot(om,A); ax.set(xlabel=r"$\omega$",ylabel=r"$A(\omega)$",title="Broadened finite-size spectral function"); save(fig,out/"spectral_function_broadening.pdf")
 ee=np.linspace(-5,5,220); oo=eth_diagonal(ee)
 fig,ax=plt.subplots(); ax.scatter(ee,oo,s=8); ax.plot(ee,np.tanh(ee/3)); ax.set(xlabel="energy",ylabel="diagonal observable",title="ETH-like eigenstate matrix elements"); save(fig,out/"eth_diagonal_matrix_elements.pdf")
 s=np.linspace(0,3.5,350); fig,ax=plt.subplots(); ax.plot(s,poisson_spacing_pdf(s),label="Poisson"); ax.plot(s,wigner_spacing_pdf(s),label="Wigner surmise"); ax.set(xlabel="normalized spacing",ylabel="probability density",title="Level-spacing diagnostics"); ax.legend(); save(fig,out/"level_spacing_poisson_wigner.pdf")
 FF=np.array([free_energy(E,1/t) for t in T]); fig,ax=plt.subplots(); ax.plot(T,FF); ax.set(xlabel="temperature",ylabel="free energy",title="Finite-spectrum Helmholtz free energy"); save(fig,out/"free_energy_temperature.pdf")
if __name__=="__main__":
 import sys; main(sys.argv[1] if len(sys.argv)>1 else "generated/ch61/computational")
