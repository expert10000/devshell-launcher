"""Commit 660 taxonomy, decision, and final visual-coverage figures."""
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

MODELS=[
("SSH","1D","chiral","winding / Zak","end states"),
("Rice–Mele","1D+cycle","adiabatic gap","Chern pump","pumped charge"),
("QWZ","2D","class A","Chern","chiral edge"),
("BHZ","2D","time reversal","Z2","helical edge"),
("BBH","2D","crystal","quadrupole","corner states"),
("Kitaev","1D BdG","particle-hole","Z2 / winding","Majorana ends"),
("Weyl","3D","node stability","chirality","Fermi arc"),
("Nodal line","3D","crystal/PT-like","Berry phase","drumhead-like boundary"),
]

def save(fig,p):
    p.parent.mkdir(parents=True,exist_ok=True); fig.tight_layout(); fig.savefig(p); plt.close(fig)

def taxonomy(out):
    fig,ax=plt.subplots(figsize=(12,6.4)); ax.axis("off")
    cols=["model","dimension","protecting structure","bulk diagnostic","boundary/response"]
    xs=np.linspace(.06,.94,len(cols))
    for j,c in enumerate(cols): ax.text(xs[j],.95,c,ha="center",va="center",weight="bold")
    ys=np.linspace(.84,.08,len(MODELS))
    for i,row in enumerate(MODELS):
        for j,val in enumerate(row):
            ax.add_patch(FancyBboxPatch((xs[j]-.085,ys[i]-.035),.17,.07,boxstyle="round,pad=0.006",fill=False,linewidth=.8))
            ax.text(xs[j],ys[i],val,ha="center",va="center",fontsize=8)
    ax.set_title("Topological Hamiltonian taxonomy")
    save(fig,out/"topological_hamiltonian_taxonomy.pdf")

def decision(out):
    fig,ax=plt.subplots(figsize=(11,7)); ax.axis("off")
    nodes=[
        (.50,.91,"Write H in an explicit basis"),
        (.50,.78,"Identify exact / approximate symmetries"),
        (.25,.62,"translation available?"),
        (.75,.62,"disorder / finite sample?"),
        (.25,.45,"Bloch / Wilson / Chern / Z2 / winding"),
        (.75,.45,"Bott / local Chern / twisted boundary"),
        (.50,.28,"open-boundary / pump / flux / response check"),
        (.50,.11,"perturb symmetry + finite-size robustness"),
    ]
    for x,y,t in nodes:
        ax.add_patch(FancyBboxPatch((x-.15,y-.045),.30,.09,boxstyle="round,pad=0.012",fill=False,linewidth=1.2))
        ax.text(x,y,t,ha="center",va="center",fontsize=9)
    arrows=[((.5,.865),(.5,.825)),((.5,.735),(.25,.665)),((.5,.735),(.75,.665)),((.25,.575),(.25,.495)),((.75,.575),(.75,.495)),((.25,.405),(.47,.325)),((.75,.405),(.53,.325)),((.5,.235),(.5,.155))]
    for a,b in arrows: ax.add_patch(FancyArrowPatch(a,b,arrowstyle="->",mutation_scale=12))
    ax.set_title("Topology diagnostic decision workflow")
    save(fig,out/"topology_diagnostic_decision_tree.pdf")

def reference_matrix(out):
    fig,ax=plt.subplots(figsize=(12,6.5)); ax.axis("off")
    cols=["setup","basis / couplings","Hamiltonian","bulk diagnostic","boundary signature"]
    xs=np.linspace(.12,.90,5)
    for j,c in enumerate(cols): ax.text(xs[j],.95,c,ha="center",weight="bold",fontsize=9)
    ys=np.linspace(.84,.10,8)
    descriptors={
      "SSH":["dimer chain","A/B; t1,t2",r"$d_x\sigma_x+d_y\sigma_y$","winding","end mode"],
      "Rice–Mele":["pump chain","A/B; t1,t2,Î”",r"$d_x\sigma_x+d_y\sigma_y+\Delta\sigma_z$","Chern(k,t)","charge pump"],
      "QWZ":["square lattice","2 orbitals",r"$d_x\sigma_x+d_y\sigma_y+d_z\sigma_z$","Chern","chiral edge"],
      "BHZ":["2D QW","orbitalĂ—spin","TR Dirac blocks","Z2","helical edge"],
      "BBH":["4-site cell","Îł/Î» bonds",r"$\sum d_a\Gamma_a$","quadrupole","corner"],
      "Kitaev":["paired chain","Nambu",r"$d_y\tau_y+d_z\tau_z$","Z2","Majorana"],
      "Weyl":["3D node","2-band",r"$v_iq_i\sigma_i$","chirality","Fermi arc"],
      "Nodal line":["3D ring","2-band",r"$d_x\sigma_x+d_z\sigma_z$","Berry Ď€","surface state"],
    }
    for i,(name,*_) in enumerate(MODELS):
        ax.text(.02,ys[i],name,ha="left",va="center",weight="bold",fontsize=8)
        vals=descriptors[name]
        for j,val in enumerate(vals):
            ax.add_patch(FancyBboxPatch((xs[j]-.085,ys[i]-.034),.17,.068,boxstyle="round,pad=.004",fill=False,linewidth=.7))
            ax.text(xs[j],ys[i],val,ha="center",va="center",fontsize=7)
    ax.set_title("Hamiltonian visual reference matrix")
    save(fig,out/"hamiltonian_visual_reference_matrix.pdf")

def symmetry_map(out):
    fig,ax=plt.subplots(figsize=(11,6)); ax.axis("off")
    rows=[
        ("chiral","winding / Zak","SSH end mode"),
        ("time reversal ÎÂ˛=-1","Z2 / Wilson flow","helical edge"),
        ("crystalline","polarization / quadrupole","corner / hinge"),
        ("particle-hole BdG","Z2 / Pfaffian","Majorana end"),
        ("translation absent","Bott / local Chern","robust edge / Hall"),
        ("interacting many-body","twist Chern / Resta / ES","fractional / spectral flow"),
    ]
    for i,(s,inv,bnd) in enumerate(rows):
        y=.86-i*.14
        for x,t in [(.18,s),(.50,inv),(.82,bnd)]:
            ax.add_patch(FancyBboxPatch((x-.13,y-.045),.26,.09,boxstyle="round,pad=.008",fill=False))
            ax.text(x,y,t,ha="center",va="center",fontsize=8)
        ax.add_patch(FancyArrowPatch((.31,y),(.37,y),arrowstyle="->"))
        ax.add_patch(FancyArrowPatch((.63,y),(.69,y),arrowstyle="->"))
    ax.text(.18,.96,"symmetry / setting",ha="center",weight="bold")
    ax.text(.50,.96,"bulk / real-space invariant",ha="center",weight="bold")
    ax.text(.82,.96,"boundary / response",ha="center",weight="bold")
    ax.set_title("Symmetry â†’ invariant â†’ boundary map")
    save(fig,out/"symmetry_invariant_boundary_map.pdf")

def coverage(out):
    fig,ax=plt.subplots(figsize=(11,6))
    data=np.ones((8,5))
    ax.imshow(data,aspect="auto",vmin=0,vmax=1)
    ax.set_yticks(range(8),[m[0] for m in MODELS])
    ax.set_xticks(range(5),["physical setup","basis/couplings","Hamiltonian","spectrum/invariant","boundary/response"],rotation=18)
    for i in range(8):
        for j in range(5): ax.text(j,i,"âś“",ha="center",va="center",fontsize=14)
    ax.set_title("Chapter 62 visual coverage matrix")
    save(fig,out/"chapter62_visual_coverage_matrix.pdf")

def main(outdir):
    out=Path(outdir); taxonomy(out); decision(out); reference_matrix(out); symmetry_map(out); coverage(out)

if __name__=="__main__":
    import sys; main(sys.argv[1] if len(sys.argv)>1 else "generated/ch62/reference")

