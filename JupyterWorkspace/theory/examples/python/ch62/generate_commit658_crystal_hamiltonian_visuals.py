"""Commit 658 visual remediation: explicit crystal structures and Hamiltonian coupling diagrams."""
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Rectangle, FancyArrowPatch
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401

def save(fig,p):
    p.parent.mkdir(parents=True,exist_ok=True)
    fig.tight_layout()
    fig.savefig(p)
    plt.close(fig)

def crystal_structure(out):
    fig=plt.figure(figsize=(9,6))
    ax=fig.add_subplot(111,projection="3d")
    # 4x4x3 simple-cubic lattice: atoms + nearest-neighbor bonds + highlighted primitive cell.
    nx,ny,nz=4,4,3
    pts=[]
    for i in range(nx):
        for j in range(ny):
            for k in range(nz):
                pts.append((i,j,k))
    pts=np.array(pts,float)
    # bonds
    for i,j,k in pts.astype(int):
        for di,dj,dk in [(1,0,0),(0,1,0),(0,0,1)]:
            q=(i+di,j+dj,k+dk)
            if q[0]<nx and q[1]<ny and q[2]<nz:
                ax.plot([i,q[0]],[j,q[1]],[k,q[2]],linewidth=.7,alpha=.35)
    ax.scatter(pts[:,0],pts[:,1],pts[:,2],s=42,depthshade=True)
    # highlight a primitive cube
    cell=np.array([[0,0,0],[1,0,0],[1,1,0],[0,1,0],[0,0,1],[1,0,1],[1,1,1],[0,1,1]],float)
    edges=[(0,1),(1,2),(2,3),(3,0),(4,5),(5,6),(6,7),(7,4),(0,4),(1,5),(2,6),(3,7)]
    for a,b in edges:
        ax.plot(*zip(cell[a],cell[b]),linewidth=2.8)
    # local phase arrows around a few sites
    for cx,cy,cz in [(1,1,1),(2,1,1),(1,2,1),(2,2,1)]:
        th=np.linspace(0,1.7*np.pi,45)
        ax.plot(cx+.22*np.cos(th),cy+.22*np.sin(th),cz+.05*np.sin(2*th),linewidth=1.6)
    ax.text(.5,.5,1.18,"highlighted unit cell",ha="center")
    ax.set(xlabel="x lattice index",ylabel="y lattice index",zlabel="z lattice index",
           title="Crystalline topology: explicit atomic lattice, bonds, unit cell, and phase texture")
    save(fig,out/"crystalline_atomic_lattice_3d.pdf")

def symmetry_planes(out):
    fig=plt.figure(figsize=(9,5))
    ax=fig.add_subplot(111,projection="3d")
    n=4
    P=np.array([(i,j,k) for i in range(n) for j in range(n) for k in range(n)],float)
    ax.scatter(P[:,0],P[:,1],P[:,2],s=25)
    # mirror plane x=1.5
    yy,zz=np.meshgrid(np.linspace(0,n-1,8),np.linspace(0,n-1,8))
    xx=np.full_like(yy,1.5)
    ax.plot_surface(xx,yy,zz,alpha=.18)
    ax.plot([1.5,1.5],[0,3],[0,3],linewidth=2)
    ax.set_title("Crystal symmetry made explicit: atomic sites plus mirror plane")
    ax.set_axis_off()
    save(fig,out/"crystal_mirror_symmetry_plane.pdf")

def polarization_unit_cell(out):
    fig,axs=plt.subplots(1,2,figsize=(10,4.5))
    for ax,shift,title in [(axs[0],0.0,"centrosymmetric / P = 0"),(axs[1],.22,"shifted Wannier centers / quantized P")]:
        for i in range(4):
            for j in range(3):
                ax.add_patch(Rectangle((i,j),1,1,fill=False,linewidth=.7))
                ax.add_patch(Circle((i+.25,j+.5),.07,fill=False,linewidth=1.2))
                ax.text(i+.25,j+.5,"+",ha="center",va="center",fontsize=7)
                wx=i+.75+shift
                if wx>i+.95: wx=i+.95
                ax.add_patch(Circle((wx,j+.5),.07,fill=False,linewidth=1.2))
                ax.text(wx,j+.5,"−",ha="center",va="center",fontsize=7)
                ax.arrow(i+.32,j+.5,wx-(i+.32)-.05,0,width=.014,length_includes_head=True)
        ax.set(xlim=(0,4),ylim=(0,3),title=title)
        ax.set_aspect("equal"); ax.axis("off")
    save(fig,out/"polarization_ionic_wannier_unit_cells.pdf")

def bbh_realspace(out):
    fig,ax=plt.subplots(figsize=(8,7))
    # four-site unit cells; thin = gamma, thick = lambda.
    for i in range(4):
        for j in range(4):
            x,y=2*i,2*j
            sites=[(x,y),(x+1,y),(x+1,y+1),(x,y+1)]
            for sx,sy in sites:
                ax.add_patch(Circle((sx,sy),.11,fill=False,linewidth=1.5))
            # intracell gamma
            for a,b in [((x,y),(x+1,y)),((x+1,y),(x+1,y+1)),((x+1,y+1),(x,y+1)),((x,y+1),(x,y))]:
                ax.plot([a[0],b[0]],[a[1],b[1]],linewidth=1)
            # intercell lambda
            if i<3:
                ax.plot([x+1,x+2],[y,y],linewidth=3)
                ax.plot([x+1,x+2],[y+1,y+1],linewidth=3)
            if j<3:
                ax.plot([x,x],[y+1,y+2],linewidth=3)
                ax.plot([x+1,x+1],[y+1,y+2],linewidth=3)
            if i==0 and j==0:
                ax.add_patch(Rectangle((-.28,-.28),1.56,1.56,fill=False,linewidth=2))
                ax.text(.5,1.45,"4-site unit cell",ha="center")
    ax.text(6.5,6.4,r"thin: $\gamma$  |  thick: $\lambda$",ha="right")
    ax.set_aspect("equal"); ax.axis("off")
    ax.set_title("BBH real-space Hamiltonian: sites, unit cells, intracell and intercell couplings")
    save(fig,out/"bbh_real_space_hamiltonian_couplings.pdf")

def bbh_terms(out):
    fig,ax=plt.subplots(figsize=(10,6))
    ax.axis("off")
    ax.text(.5,.93,r"$H_{\rm BBH}(\mathbf{k})=$",ha="center",fontsize=18)
    terms=[
        (r"$(\gamma_x+\lambda_x\cos k_x)\Gamma_4$","intracell + x-direction hopping"),
        (r"$+\lambda_x\sin k_x\,\Gamma_3$","x-directed phase / orientation"),
        (r"$+(\gamma_y+\lambda_y\cos k_y)\Gamma_2$","intracell + y-direction hopping"),
        (r"$+\lambda_y\sin k_y\,\Gamma_1$","y-directed phase / orientation"),
    ]
    ys=[.76,.60,.44,.28]
    for (formula,label),y in zip(terms,ys):
        ax.add_patch(Rectangle((.08,y-.07),.84,.12,fill=False,linewidth=1.2))
        ax.text(.30,y,formula,ha="center",va="center",fontsize=14)
        ax.annotate(label,xy=(.54,y),xytext=(.88,y),ha="right",va="center",
                    arrowprops=dict(arrowstyle="->",linewidth=1))
    ax.text(.5,.10,r"Topology comes from how the four coupling terms wind and invert as $\mathbf{k}$ spans the Brillouin zone.",ha="center")
    save(fig,out/"bbh_hamiltonian_term_decomposition.pdf")

def bbh_matrix(out):
    fig,ax=plt.subplots(figsize=(8.5,6))
    ax.axis("off")
    ax.text(.5,.92,"BBH Hamiltonian — visual matrix/basis map",ha="center",fontsize=16)
    ax.text(.5,.78,r"basis: $(|A\rangle,|B\rangle,|C\rangle,|D\rangle)$",ha="center",fontsize=13)
    M=[
        ["0",r"$q_x$",r"$q_y$", "0"],
        [r"$q_x^*$","0","0",r"$-q_y$"],
        [r"$q_y^*$","0","0",r"$q_x$"],
        ["0",r"$-q_y^*$",r"$q_x^*$","0"],
    ]
    x0,y0=.19,.58; dx=.155; dy=.10
    for i in range(4):
        for j in range(4):
            ax.add_patch(Rectangle((x0+j*dx,y0-i*dy),dx,dy,fill=False,linewidth=.8))
            ax.text(x0+(j+.5)*dx,y0-(i-.5)*dy,M[i][j],ha="center",va="center",fontsize=12)
    ax.text(.5,.15,r"$q_x=\gamma_x+\lambda_xe^{ik_x}$,  $q_y=\gamma_y+\lambda_ye^{ik_y}$",ha="center",fontsize=13)
    save(fig,out/"bbh_hamiltonian_matrix_basis_map.pdf")

def boundary_cube_atomic(out):
    fig=plt.figure(figsize=(8,6)); ax=fig.add_subplot(111,projection="3d")
    n=5
    # lattice points in cube, muted interior
    pts=np.array([(i,j,k) for i in range(n) for j in range(n) for k in range(n)],float)
    boundary=((pts==0)|(pts==n-1)).any(axis=1)
    ax.scatter(pts[~boundary,0],pts[~boundary,1],pts[~boundary,2],s=8,alpha=.12)
    ax.scatter(pts[boundary,0],pts[boundary,1],pts[boundary,2],s=18,alpha=.35)
    # edges
    corners=np.array([(0,0,0),(4,0,0),(4,4,0),(0,4,0),(0,0,4),(4,0,4),(4,4,4),(0,4,4)],float)
    edges=[(0,1),(1,2),(2,3),(3,0),(4,5),(5,6),(6,7),(7,4),(0,4),(1,5),(2,6),(3,7)]
    for a,b in edges: ax.plot(*zip(corners[a],corners[b]),linewidth=3)
    ax.scatter(corners[:,0],corners[:,1],corners[:,2],s=100)
    ax.set_title("Higher-order boundary hierarchy on an explicit atomic crystal")
    ax.set_axis_off()
    save(fig,out/"higher_order_atomic_boundary_hierarchy.pdf")

def main(outdir):
    comp=Path(outdir); concept=comp.parent/"conceptual"
    crystal_structure(concept)
    symmetry_planes(concept)
    polarization_unit_cell(concept)
    bbh_realspace(concept)
    bbh_terms(concept)
    bbh_matrix(concept)
    boundary_cube_atomic(concept)

if __name__=="__main__":
    import sys
    main(sys.argv[1] if len(sys.argv)>1 else "generated/ch62/computational")
