from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from topological_superconductivity import *

def save(fig,p):
    p.parent.mkdir(parents=True,exist_ok=True); fig.tight_layout(); fig.savefig(p); plt.close(fig)

def main(outdir):
    out=Path(outdir)
    k=np.linspace(-np.pi,np.pi,700)
    fig,ax=plt.subplots()
    for mu,label in [(3.0,"trivial"),(2.0,"critical"),(0.5,"topological")]:
        ax.plot(k,bulk_energy(k,mu),label=label)
    ax.set(xlabel=r"$k$",ylabel=r"$E(k)$",title="Kitaev-chain bulk spectrum"); ax.legend()
    save(fig,out/"kitaev_bulk_spectrum.pdf")

    mu=np.linspace(-3.2,3.2,320); de=np.linspace(.05,1.2,180)
    M,D=np.meshgrid(mu,de); Z=np.where(np.abs(M)<2,1.0,0.0)
    fig,ax=plt.subplots(); im=ax.imshow(Z,origin="lower",aspect="auto",extent=[mu.min(),mu.max(),de.min(),de.max()])
    ax.set(xlabel=r"$\mu/t$",ylabel=r"$\Delta/t$",title="Clean Kitaev topological phase region")
    save(fig,out/"kitaev_phase_diagram.pdf")

    p=lowest_mode_profile(60,.5)
    fig,ax=plt.subplots(); ax.plot(np.arange(60),p,marker=".")
    ax.set(xlabel="site",ylabel="lowest-mode weight",title="Majorana edge localization")
    save(fig,out/"majorana_edge_profile.pdf")

    L=np.arange(8,82,2); spl=np.array([min_abs_energy(int(x),.5) for x in L])
    fig,ax=plt.subplots(); ax.semilogy(L,np.maximum(spl,1e-14),marker=".")
    ax.set(xlabel="chain length",ylabel="near-zero splitting",title="Finite-size Majorana splitting")
    save(fig,out/"majorana_finite_size_splitting.pdf")

    W=np.linspace(0,7,55); g=np.array([disorder_gap_stat(28,.3,float(w),samples=12) for w in W])
    fig,ax=plt.subplots(); ax.plot(W,g)
    ax.set(xlabel=r"disorder strength $W/t$",ylabel="median bulk-gap statistic",title="Disorder robustness diagnostic")
    save(fig,out/"kitaev_disorder_robustness.pdf")

    fig,ax=plt.subplots()
    for m,label in [(3.0,"trivial"),(.5,"topological")]:
        dz,dy=winding_points(m); ax.plot(dz,dy,label=label)
    ax.scatter([0],[0]); ax.set(xlabel=r"$d_z$",ylabel=r"$d_y$",title="BdG winding trajectory"); ax.legend(); ax.axis("equal")
    save(fig,out/"bdg_winding_trajectory.pdf")

    mus=np.linspace(-3,3,160); eo=[]; ep=[]
    for m in mus:
        eo.append(min_abs_energy(36,m,periodic=False))
        ep.append(min_abs_energy(36,m,periodic=True))
    fig,ax=plt.subplots(); ax.plot(mus,eo,label="open"); ax.plot(mus,ep,label="periodic")
    ax.set(xlabel=r"$\mu/t$",ylabel="minimum absolute energy",title="Boundary-sensitive low-energy spectrum"); ax.legend()
    save(fig,out/"open_periodic_spectrum_comparison.pdf")

    muv=np.linspace(-1.5,1.5,250); B=np.linspace(0,2.0,220); MM,BB=np.meshgrid(muv,B)
    crit=np.sqrt(MM**2+.35**2); topo=(BB>crit).astype(float)
    fig,ax=plt.subplots(); ax.imshow(topo,origin="lower",aspect="auto",extent=[muv.min(),muv.max(),B.min(),B.max()])
    ax.set(xlabel=r"$\mu$",ylabel=r"$B$",title=r"Idealized criterion $B>\sqrt{\mu^2+\Delta^2}$")
    save(fig,out/"nanowire_topological_criterion.pdf")

    gaps=np.array([bulk_gap(m) for m in mus]); tg=np.where(np.abs(mus)<2,gaps,0)
    fig,ax=plt.subplots(); ax.plot(mus,tg)
    ax.set(xlabel=r"$\mu/t$",ylabel="topological bulk gap",title="Topological-gap map along a chemical-potential cut")
    save(fig,out/"topological_gap_map.pdf")

if __name__=="__main__":
    import sys; main(sys.argv[1] if len(sys.argv)>1 else "generated/ch61/computational")
