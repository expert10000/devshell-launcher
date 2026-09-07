from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle, FancyArrowPatch

def save(fig,p):
    p=Path(p); p.parent.mkdir(parents=True,exist_ok=True)
    fig.savefig(p,bbox_inches="tight")
    plt.close(fig)

def panel(title, subtitle="Hamiltonian Visual Laboratory"):
    fig,ax=plt.subplots(figsize=(12,7.2))
    ax.set_xlim(0,12); ax.set_ylim(0,7.2); ax.axis("off")
    ax.add_patch(Rectangle((.18,.18),11.64,6.84,fill=False,linewidth=1.6))
    ax.text(.45,6.78,subtitle+" - "+title,fontsize=13,weight="bold",va="center")
    ax.plot([.35,11.65],[6.48,6.48],linewidth=1.0)
    return fig,ax

def box(ax,x,y,w,h,title,body=None,fontsize=10):
    ax.add_patch(Rectangle((x,y),w,h,fill=False,linewidth=1.1))
    ax.text(x+.18,y+h-.24,title,fontsize=10.5,weight="bold",va="top")
    if body:
        ax.text(x+w/2,y+h/2-.05,body,fontsize=fontsize,ha="center",va="center")

def arrow(ax,a,b):
    ax.add_patch(FancyArrowPatch(a,b,arrowstyle="->",mutation_scale=12,linewidth=1))

def footer(ax,text):
    ax.add_patch(Rectangle((.45,.38),11.1,.52,fill=False,linewidth=1.0))
    ax.text(6,.64,text,fontsize=9.3,ha="center",va="center")

def lattice_chain(ax,x0,y0,n=8,alt=True):
    for i in range(n):
        ax.add_patch(Circle((x0+i*.46,y0),.075,fill=False,linewidth=1.1))
        if i<n-1:
            lw=2.5 if (alt and i%2==1) else 1.0
            ax.plot([x0+i*.46+.08,x0+(i+1)*.46-.08],[y0,y0],linewidth=lw)

def square_lattice(ax,x0,y0,nx=4,ny=4,spacing=.42):
    for i in range(nx):
        for j in range(ny):
            x=x0+i*spacing; y=y0+j*spacing
            ax.add_patch(Circle((x,y),.055,fill=False,linewidth=1))
            if i<nx-1: ax.plot([x+.06,x+spacing-.06],[y,y],linewidth=.8)
            if j<ny-1: ax.plot([x,x],[y+.06,y+spacing-.06],linewidth=.8)

def mini_bands(ax,x0,y0,w,h,gap=.35,edge=False):
    k=np.linspace(-1,1,120); e=np.sqrt(k*k+gap*gap)
    ax.plot(x0+(k+1)*w/2,y0+h/2+e*h/3,linewidth=1)
    ax.plot(x0+(k+1)*w/2,y0+h/2-e*h/3,linewidth=1)
    if edge: ax.plot([x0+.1*w,x0+.9*w],[y0+.25*h,y0+.75*h],linewidth=1.5)

def crystal(out):
    fig,ax=panel("Crystalline topology","Conceptual + Hamiltonian Visual Laboratory")
    box(ax,.45,3.55,3.15,2.55,"ATOMIC CRYSTAL / UNIT CELL")
    for i in range(5):
      for j in range(4):
        x=.82+i*.48; y=4.12+j*.42; ax.add_patch(Circle((x,y),.055,fill=False,linewidth=1));
        if i<4: ax.plot([x+.06,x+.42],[y,y],linewidth=.8)
        if j<3: ax.plot([x,x],[y+.06,y+.36],linewidth=.8)
    ax.add_patch(Rectangle((.72,4.02),.60,.54,fill=False,linewidth=2))
    box(ax,3.82,4.72,3.55,1.38,"SPATIAL SYMMETRY","translation T_a\ninversion I\nmirror M\nrotation C_n",9)
    box(ax,7.62,4.72,3.92,1.38,"HAMILTONIAN CONSTRAINT","U_g H(k) U_g^-1 = H(gk)\nsymmetry eigenvalues organize bands",8.7)
    box(ax,3.82,3.05,3.55,1.38,"TOPOLOGICAL DATA","symmetry indicators\nWannier obstruction\nmirror / rotation invariants",9)
    box(ax,7.62,3.05,3.92,1.38,"PHYSICAL CONSEQUENCE","surface, hinge, or corner states\non symmetry-compatible boundaries",9)
    footer(ax,"atomic lattice + spatial symmetry -> constrained Hamiltonian -> crystalline invariant -> boundary signature"); save(fig,out/'crystalline_topology_designed_panel.pdf')

def polarization(out):
    fig,ax=panel("Polarization and Wannier centers","Conceptual + Hamiltonian Visual Laboratory")
    box(ax,.45,3.55,3.15,2.55,"UNIT-CELL CHARGE GEOMETRY")
    for i in range(4):
        x=.72+i*.68; ax.add_patch(Rectangle((x,4.15),.58,.80,fill=False,linewidth=.8)); ax.text(x+.13,4.55,"+",fontsize=10); ax.text(x+.43,4.55,"-",fontsize=10); ax.arrow(x+.19,4.40,.22,0,width=.012,length_includes_head=True)
    box(ax,3.82,4.72,3.55,1.38,"BULK GEOMETRIC QUANTITY","P from Zak phase (mod e)\ninversion can quantize P",9)
    box(ax,7.62,4.72,3.92,1.38,"TRIVIAL VS TOPOLOGICAL","centers coincide -> P = 0\nhalf-cell shift -> P = e/2",9)
    box(ax,3.82,3.05,3.55,1.38,"BOUNDARY CHARGE","bulk polarization terminates at edge\nsurface charge follows Delta P",9)
    box(ax,7.62,3.05,3.92,1.38,"WANNIER VIEW","obstruction to moving centers\nwithout closing gap or breaking symmetry",8.7)
    footer(ax,"microscopic charge centers -> Berry/Zak phase -> quantized polarization -> boundary charge"); save(fig,out/'polarization_wannier_designed_panel.pdf')

def higher_order(out):
    fig,ax=panel("Higher-order boundary hierarchy","Conceptual + Hamiltonian Visual Laboratory")
    box(ax,.45,3.55,3.15,2.55,"3D CRYSTAL / CODIMENSION")
    p=np.array([[.9,4.15],[2.6,4.15],[2.6,5.45],[.9,5.45],[1.35,4.55],[3.05,4.55],[3.05,5.85],[1.35,5.85]])
    for a,b in [(0,1),(1,2),(2,3),(3,0),(4,5),(5,6),(6,7),(7,4),(0,4),(1,5),(2,6),(3,7)]: ax.plot([p[a,0],p[b,0]],[p[a,1],p[b,1]],linewidth=1.4)
    ax.scatter(p[:,0],p[:,1],s=45)
    box(ax,3.82,4.72,3.55,1.38,"BOUNDARY LADDER","3D bulk -> 2D faces\n-> 1D hinges -> 0D corners",9.4)
    box(ax,7.62,4.72,3.92,1.38,"HIGHER-ORDER RULE","nth-order phase localizes states\non codimension-n boundaries",9)
    box(ax,3.82,3.05,3.55,1.38,"HAMILTONIAN MECHANISM","bulk masses gap surfaces\nmass sign changes trap lower-dimensional modes",8.8)
    box(ax,7.62,3.05,3.92,1.38,"OBSERVABLE CONSEQUENCE","hinge conduction\ncorner resonances\nfractional boundary charge",9)
    footer(ax,"bulk topology can descend through faces and hinges to isolated protected corner states"); save(fig,out/'higher_order_hierarchy_designed_panel.pdf')

def bbh_boundary(out):
    fig,ax=panel("BBH boundary hierarchy","Conceptual + Hamiltonian Visual Laboratory")
    box(ax,.45,3.55,3.15,2.55,"2D FOUR-SITE CRYSTAL")
    for i in range(3):
      for j in range(3):
        x=.72+i*.82; y=4.00+j*.60; pts=[(x,y),(x+.30,y),(x+.30,y+.26),(x,y+.26)]
        for px,py in pts: ax.add_patch(Circle((px,py),.045,fill=False,linewidth=.9))
        for a,b in [(0,1),(1,2),(2,3),(3,0)]: ax.plot([pts[a][0],pts[b][0]],[pts[a][1],pts[b][1]],linewidth=.8)
    box(ax,3.82,4.72,3.55,1.38,"COUPLING HIERARCHY","intracell gamma_x, gamma_y\nintercell lambda_x, lambda_y",9)
    box(ax,7.62,4.72,3.92,1.38,"MULTIPOLE INVARIANT","q_xy = 1/2 in quadrupole phase\nedge polarizations nontrivial",9)
    box(ax,3.82,3.05,3.55,1.38,"EDGE PHYSICS","gapped bulk\nedges behave as polarized 1D systems",9)
    box(ax,7.62,3.05,3.92,1.38,"CORNER PHYSICS"); [ax.scatter([qx],[qy],s=75) for qx,qy in [(8.18,3.35),(11.0,3.35),(8.18,4.02),(11.0,4.02)]]
    footer(ax,"quadrupole bulk invariant -> edge polarization -> quantized corner response"); save(fig,out/'bbh_boundary_hierarchy_designed_panel.pdf')

def interacting(out):
    fig,ax=panel("Interacting topology","Many-body Visual Laboratory")
    box(ax,.45,3.55,3.15,2.55,"CORRELATED ELECTRON LATTICE"); square_lattice(ax,.82,4.18,5,4,.42)
    box(ax,3.82,4.72,3.55,1.38,"MANY-BODY HAMILTONIAN",r"$H=H_0+U\sum_i n_{i\uparrow}n_{i\downarrow}$"+"\n"+r"$+V\sum_{<ij>}n_i n_j$",8.2)
    box(ax,7.62,4.72,3.92,1.38,"WHAT INTERACTIONS DO","U: onsite repulsion\nV: neighbor correlation\ncollective state != independent bands",9)
    box(ax,3.82,3.05,3.55,1.38,"TOPOLOGICAL OBJECT","ground-state bundle under twists\nmany-body Berry phase / Chern number",9)
    box(ax,7.62,3.05,3.92,1.38,"CONSEQUENCE","collective pumping\nfractionalized excitations\ninteraction-driven transitions",9)
    footer(ax,"single-particle topology + correlations -> topology of the full many-body wavefunction"); save(fig,out/'interacting_topology_designed_panel.pdf')

def manybody(out):
    fig,ax=panel("Many-body invariants","Many-body Visual Laboratory")
    box(ax,.45,3.55,3.15,2.55,"TWISTED-BOUNDARY TORUS"); th=np.linspace(0,2*np.pi,160); ax.plot(1.95+.95*np.cos(th),4.80+.45*np.sin(th),linewidth=1); ax.plot(1.95+.55*np.cos(th),4.80+.75*np.sin(th),linewidth=1)
    box(ax,3.82,4.72,3.55,1.38,"GLOBAL PARAMETER SPACE",r"$|\Psi(\theta_x,\theta_y)\rangle$"+"\n"+"correlated ground state transported around twist torus",8.5)
    box(ax,7.62,4.72,3.92,1.38,"MANY-BODY CHERN NUMBER","integral of Berry curvature over twist torus",9)
    box(ax,3.82,3.05,3.55,1.38,"WHY IT IS GLOBAL","local particle labels insufficient\ninvariant belongs to full wavefunction",9)
    box(ax,7.62,3.05,3.92,1.38,"ROBUSTNESS","smooth local perturbations deform state\ninteger unchanged while gap survives",8.6)
    footer(ax,"twist the whole many-body state -> integrate global Berry curvature -> interaction-stable invariant"); save(fig,out/'many_body_invariant_designed_panel.pdf')

def fractional(out):
    fig,ax=panel("Fractionalization","Many-body Visual Laboratory")
    box(ax,.45,3.55,3.15,2.55,"CORRELATED QUANTUM FLUID")
    for y in [4.25,4.70,5.15]: ax.scatter([.82],[y],s=45); arrow(ax,(1.0,y),(1.45,4.70))
    ax.add_patch(Circle((2.05,4.70),.62,fill=False,linewidth=1.2))
    for dy in np.linspace(-.65,.65,5): arrow(ax,(2.55,4.70),(2.85,4.70+dy)); ax.scatter([2.85],[4.70+dy],s=30)
    box(ax,3.82,4.72,3.55,1.38,"EMERGENT QUASIPARTICLES","collective defects\nnot bare electrons",9)
    box(ax,7.62,4.72,3.92,1.38,"FRACTIONAL QUANTUM NUMBERS","charge e/3, e/5, ...\nanyon exchange phases",9)
    box(ax,3.82,3.05,3.55,1.38,"TOPOLOGICAL ORIGIN","strong correlations + global topology\nreorganize elementary excitations",9)
    box(ax,7.62,3.05,3.92,1.38,"MEASURABLE CONSEQUENCE","fractional Hall response\nflux spectral flow\nshot-noise charge",8.8)
    footer(ax,"strongly correlated fluid -> emergent fractional quasiparticles -> fractional topological response"); save(fig,out/'fractionalization_designed_panel.pdf')

def topological_order(out):
    fig,ax=panel("Topological order","Many-body Visual Laboratory")
    box(ax,.45,3.55,3.15,2.55,"GLOBAL TOPOLOGY / NONLOCAL DATA"); th=np.linspace(0,2*np.pi,160); ax.plot(1.95+.92*np.cos(th),4.78+.42*np.sin(th),linewidth=1); ax.plot(1.95+.48*np.cos(th),4.78+.76*np.sin(th),linewidth=1)
    box(ax,3.82,4.72,3.55,1.38,"GROUND-STATE MANIFOLD","topology-dependent degeneracy\nlocally indistinguishable states",9)
    box(ax,7.62,4.72,3.92,1.38,"ANYONIC DATA","braiding phases\nfusion channels\nnonlocal logical information",9)
    box(ax,3.82,3.05,3.55,1.38,"SPT VS INTRINSIC ORDER","SPT: short-range entangled + symmetry\nintrinsic: long-range entangled",8.7)
    box(ax,7.62,3.05,3.92,1.38,"ROBUSTNESS","local perturbations cannot read or erase\nglobal sector without closing gap",8.6)
    footer(ax,"long-range entanglement -> topological ground-state sectors -> anyons and nonlocal protection"); save(fig,out/'topological_order_designed_panel.pdf')

def main(outdir):
    out=Path(outdir); crystal(out); polarization(out); higher_order(out); bbh_boundary(out); interacting(out); manybody(out); fractional(out); topological_order(out)
if __name__=='__main__':
    import sys; main(sys.argv[1] if len(sys.argv)>1 else 'generated/ch62/designed_conceptual_panels')
