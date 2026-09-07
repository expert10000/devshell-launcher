from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from topological_band_models import *
def save(fig,p): p.parent.mkdir(parents=True,exist_ok=True); fig.tight_layout(); fig.savefig(p); plt.close(fig)
def main(outdir):
 out=Path(outdir)
 r=np.linspace(.2,1.8,250); gap=np.array([ssh_bulk_gap(x,1) for x in r])
 fig,ax=plt.subplots(); ax.plot(r,gap); ax.set(xlabel=r"$t_1/t_2$",ylabel="bulk gap",title="SSH dimerization transition"); save(fig,out/"ssh_bulk_gap_vs_dimerization.pdf")
 fig,ax=plt.subplots()
 for a,label in [(1.4,"trivial"),(.6,"topological")]:
  x,y=ssh_winding_points(a,1); ax.plot(x,y,label=label)
 ax.scatter([0],[0]); ax.set_aspect("equal"); ax.set(xlabel=r"$d_x$",ylabel=r"$d_y$",title="SSH winding trajectories"); ax.legend(); save(fig,out/"ssh_winding_trajectory.pdf")
 rr=np.linspace(.25,1.75,180); vals=[]
 for a in rr:
  e=np.linalg.eigvalsh(ssh_open_hamiltonian(18,a,1)); vals.append(e)
 vals=np.array(vals)
 fig,ax=plt.subplots(); ax.plot(rr,vals); ax.set(xlabel=r"$t_1/t_2$",ylabel="energy",title="Open SSH spectrum"); save(fig,out/"ssh_open_chain_spectrum.pdf")
 p=ssh_low_mode_profile(30,.5,1)
 fig,ax=plt.subplots(); ax.plot(np.arange(len(p)),p,marker="."); ax.set(xlabel="orbital index",ylabel="mode weight",title="SSH edge-mode localization"); save(fig,out/"ssh_edge_mode_profile.pdf")
 s,d,m,q=rice_mele_loop()
 fig,ax=plt.subplots(); ax.plot(d,m); ax.scatter([0],[0]); ax.set_aspect("equal"); ax.set(xlabel="dimerization",ylabel="staggering",title="Rice-Mele pumping loop"); save(fig,out/"rice_mele_pump_loop.pdf")
 fig,ax=plt.subplots(); ax.plot(s/(2*np.pi),q); ax.set(xlabel="cycle fraction",ylabel="pumped polarization",title="Quantized pump accumulation"); save(fig,out/"rice_mele_pumped_charge.pdf")
 ms=np.linspace(-3,3,301); cc=np.array([qwz_expected_chern(x) for x in ms])
 fig,ax=plt.subplots(); ax.step(ms,cc,where="mid"); ax.set(xlabel="mass m",ylabel="lower-band Chern number",title="QWZ Chern phases"); save(fig,out/"qwz_chern_phase_diagram.pdf")
 c,ks,F=lattice_chern(-1,n=35,return_flux=True)
 fig,ax=plt.subplots(); ax.imshow(F.T,origin="lower",extent=[-np.pi,np.pi,-np.pi,np.pi],aspect="auto"); ax.set(xlabel=r"$k_x$",ylabel=r"$k_y$",title=f"Lattice Berry flux, C={c:.3f}"); save(fig,out/"qwz_berry_curvature.pdf")
 kys=np.linspace(-np.pi,np.pi,180); ev=np.array([np.linalg.eigvalsh(qwz_ribbon(18,k,-1)) for k in kys])
 fig,ax=plt.subplots(); ax.plot(kys,ev); ax.set(xlabel=r"$k_y$",ylabel="energy",title="QWZ ribbon spectrum"); save(fig,out/"qwz_ribbon_edge_spectrum.pdf")
if __name__=="__main__":
 import sys; main(sys.argv[1] if len(sys.argv)>1 else "generated/ch62/computational")
