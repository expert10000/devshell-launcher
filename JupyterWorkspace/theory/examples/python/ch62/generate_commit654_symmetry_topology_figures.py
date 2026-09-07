from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from symmetry_topology_semimetals import *
def save(fig,p): p.parent.mkdir(parents=True,exist_ok=True); fig.tight_layout(); fig.savefig(p); plt.close(fig)
def main(outdir):
 out=Path(outdir)
 M=np.linspace(-2,6,350)
 fig,ax=plt.subplots(); ax.plot(M,bhz_gap_parameter(M)); ax.axvline(0,linestyle="--"); ax.set(xlabel="Dirac mass M",ylabel="bulk gap",title="Band inversion through a Dirac gap closing"); save(fig,out/"bhz_bulk_gap_mass_inversion.pdf")
 k=np.linspace(-1.5,1.5,320); up,dn,bp,bm=qsh_edge_spectrum(k)
 fig,ax=plt.subplots(); ax.plot(k,bp); ax.plot(k,bm); ax.plot(k,up,label="edge Kramers partner"); ax.plot(k,dn,label="edge Kramers partner"); ax.set(xlabel="edge momentum",ylabel="energy",title="Helical edge crossing"); ax.legend(); save(fig,out/"bhz_helical_edge_spectrum.pdf")
 x=np.linspace(0,1,280); a,b=wilson_helical_flow(x)
 fig,ax=plt.subplots(); ax.plot(x,a,label="Wilson phase 1"); ax.plot(x,b,label="Wilson phase 2"); ax.set(xlabel="half-BZ path",ylabel="eigenphase",title="Partner-switching Wilson-loop flow"); ax.legend(); save(fig,out/"wilson_loop_helical_flow.pdf")
 kk=np.linspace(-2,2,350)
 fig,ax=plt.subplots()
 for m in [0,.5,-.5]: ax.plot(kk,dirac_energy(kk,m),label=f"m={m}"); ax.plot(kk,-dirac_energy(kk,m))
 ax.set(xlabel="momentum",ylabel="energy",title="Dirac mass opening"); ax.legend(); save(fig,out/"dirac_mass_gap.pdf")
 fig,ax=plt.subplots(); ax.plot(kk,weyl_energy(kk,0,0)); ax.plot(kk,-weyl_energy(kk,0,0)); ax.set(xlabel=r"$q_x$",ylabel="energy",title="Linear Weyl cone"); save(fig,out/"weyl_cone_chirality.pdf")
 q=np.linspace(-1.6,1.6,300); X,Y=np.meshgrid(q,q); E=nodal_ring_energy(X,Y,0)
 fig,ax=plt.subplots(); ax.imshow(E,origin="lower",extent=[q.min(),q.max(),q.min(),q.max()],aspect="equal"); ax.set(xlabel=r"$k_x$",ylabel=r"$k_y$",title="Nodal-ring gap map at kz=0"); save(fig,out/"nodal_ring_gap_map.pdf")
 labels=["gapped","Weyl point","nodal line","nodal surface"]; cod=[4,3,2,1]
 fig,ax=plt.subplots(); ax.bar(np.arange(4),cod); ax.set_xticks(np.arange(4),labels,rotation=20); ax.set(ylabel="codimension proxy",title="Topological-defect organization"); save(fig,out/"topological_defect_dimension_map.pdf")
if __name__=="__main__":
 import sys; main(sys.argv[1] if len(sys.argv)>1 else "generated/ch62/computational")
