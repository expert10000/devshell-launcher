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

def berry(out):
    fig,ax=panel("Two-level Berry geometry")
    box(ax,.45,3.55,3.15,2.55,"PHYSICAL SYSTEM / PARAMETER SPACE")
    c=(1.95,4.65); rad=.78; th=np.linspace(0,2*np.pi,160)
    ax.plot(c[0]+rad*np.cos(th),c[1]+rad*np.sin(th),linewidth=1)
    ax.arrow(c[0],c[1],.52,.38,width=.015,length_includes_head=True)
    ax.text(c[0]+.34,c[1]+.50,"d(R)",fontsize=9); ax.text(c[0],3.82,"closed adiabatic loop",ha="center",fontsize=9)
    box(ax,3.82,4.72,3.55,1.38,"HILBERT SPACE / HAMILTONIAN",r"$|u_\pm(R)\rangle$"+"\n"+r"$H=d_x\sigma_x+d_y\sigma_y+d_z\sigma_z$",9)
    box(ax,7.62,4.72,3.92,1.38,"GEOMETRIC TERMS",r"$A_n=i\langle u_n|\nabla_Ru_n\rangle$"+"\n"+r"$\Omega_n=\nabla_R\times A_n$",9)
    box(ax,3.82,3.05,3.55,1.38,"INVARIANT / PHASE",r"$\gamma_n=\oint A_n\cdot dR$"+"\n"+"solid-angle geometry",9)
    box(ax,7.62,3.05,3.92,1.38,"OBSERVABLE CONSEQUENCE","interference phase\nadiabatic pumping\ncurvature-driven response",9)
    footer(ax,"parameter-space geometry -> Berry curvature -> geometric phase -> measurable response")
    save(fig,out/'berry_two_level_designed_panel.pdf')

def ssh(out):
    fig,ax=panel("SSH chain")
    box(ax,.45,3.55,3.15,2.55,"REAL-SPACE CRYSTAL"); lattice_chain(ax,.78,4.70,8,True)
    ax.text(1.20,4.25,"thin: t1   thick: t2",ha="center",fontsize=8.5)
    box(ax,3.82,4.72,3.55,1.38,"BASIS / HAMILTONIAN",r"basis $(A,B)$"+"\n"+r"$h=(t_1+t_2\cos k)\sigma_x+t_2\sin k\,\sigma_y$",8.6)
    box(ax,7.62,4.72,3.92,1.38,"SYMMETRY / TOPOLOGY","chiral symmetry\nwinding of (dx,dy)\nZak phase",9)
    box(ax,3.82,3.05,3.55,1.38,"BULK SPECTRUM"); mini_bands(ax,4.15,3.24,2.9,.9,gap=.28)
    box(ax,7.62,3.05,3.92,1.38,"BOUNDARY CONSEQUENCE","|t2| > |t1|\nopen chain -> localized end states",9)
    footer(ax,"bond dimerization -> Bloch winding -> bulk gap topology -> end mode"); save(fig,out/'ssh_designed_panel.pdf')

def rice(out):
    fig,ax=panel("Rice-Mele pump")
    box(ax,.45,3.55,3.15,2.55,"DRIVEN DIMERIZED CHAIN"); lattice_chain(ax,.78,4.75,8,True)
    for i in range(8): ax.text(.78+i*.46,5.05,"+" if i%2==0 else "-",ha="center",fontsize=8)
    box(ax,3.82,4.72,3.55,1.38,"HAMILTONIAN",r"$h=d_x\sigma_x+d_y\sigma_y+\Delta\sigma_z$"+"\n"+"cycle: dimerization + staggered onsite",8.7)
    box(ax,7.62,4.72,3.92,1.38,"CONTROL LOOP"); t=np.linspace(0,2*np.pi,120); ax.plot(9.58+.58*np.cos(t),5.30+.36*np.sin(t),linewidth=1.2); ax.scatter([9.58],[5.30],s=20)
    box(ax,3.82,3.05,3.55,1.38,"GEOMETRIC INVARIANT","Chern number in (k,t)\ncycle avoids gap closing",9)
    box(ax,7.62,3.05,3.92,1.38,"OBSERVABLE CONSEQUENCE","one cycle pumps integer charge\npolarization shifts by lattice quantum",9)
    footer(ax,"adiabatic cycle around the gap-closing point -> quantized Thouless pump"); save(fig,out/'rice_mele_designed_panel.pdf')

def qwz(out):
    fig,ax=panel("QWZ Chern insulator")
    box(ax,.45,3.55,3.15,2.55,"2D CRYSTAL / ORBITALS"); square_lattice(ax,.90,4.20,5,4,.40)
    box(ax,3.82,4.72,3.55,1.38,"BLOCH HAMILTONIAN",r"$h=\sin k_x\sigma_x+\sin k_y\sigma_y$"+"\n"+r"$+(m+\cos k_x+\cos k_y)\sigma_z$",8.6)
    box(ax,7.62,4.72,3.92,1.38,"TERM MEANING","sigma_x, sigma_y: momentum mixing\nsigma_z: mass / band inversion",9)
    box(ax,3.82,3.05,3.55,1.38,"BULK TOPOLOGY","Berry curvature in Brillouin zone\nChern number C",9)
    box(ax,7.62,3.05,3.92,1.38,"BOUNDARY CONSEQUENCE"); mini_bands(ax,8.05,3.20,3.0,.95,gap=.30,edge=True)
    footer(ax,"mass inversion -> nonzero Chern number -> one-way chiral edge transport"); save(fig,out/'qwz_designed_panel.pdf')

def bhz(out):
    fig,ax=panel("BHZ quantum spin Hall Hamiltonian")
    box(ax,.45,3.55,3.15,2.55,"QUANTUM WELL / BASIS","electron-like E1 orbital\nhole-like H1 orbital\nKramers partners",9)
    box(ax,3.82,4.72,3.55,1.38,"BLOCK HAMILTONIAN",r"$H=\mathrm{diag}[h(k),h^*(-k)]$"+"\n"+r"$h=A k_x\sigma_x+A k_y\sigma_y+(M-Bk^2)\sigma_z$",8.0)
    box(ax,7.62,4.72,3.92,1.38,"SYMMETRY","time reversal, Theta^2 = -1\nKramers degeneracy at TRIM",9)
    box(ax,3.82,3.05,3.55,1.38,"BAND INVERSION","normal vs inverted orbital order\nM/B selects regime",9)
    box(ax,7.62,3.05,3.92,1.38,"EDGE CONSEQUENCE"); x=np.linspace(8.0,11.15,100); ax.plot(x,3.30+(x-9.57)*.28,linewidth=1.2); ax.plot(x,3.30-(x-9.57)*.28,linewidth=1.2)
    footer(ax,"time-reversal-related Dirac blocks -> Z2 topology -> helical edge pair"); save(fig,out/'bhz_designed_panel.pdf')

def bbh(out):
    fig,ax=panel("BBH quadrupole Hamiltonian")
    box(ax,.45,3.55,3.15,2.55,"4-SITE UNIT CELL")
    for ci in range(2):
      for cj in range(2):
        x=.92+ci*1.15; y=4.18+cj*.82; pts=[(x,y),(x+.48,y),(x+.48,y+.40),(x,y+.40)]
        for px,py in pts: ax.add_patch(Circle((px,py),.06,fill=False,linewidth=1))
        for a,b in [(0,1),(1,2),(2,3),(3,0)]: ax.plot([pts[a][0],pts[b][0]],[pts[a][1],pts[b][1]],linewidth=1)
    ax.text(2.0,5.75,"gamma: intracell   lambda: intercell",ha="center",fontsize=8.3)
    box(ax,3.82,4.72,3.55,1.38,"MATRIX / GAMMA TERMS",r"$H(k)=\sum_{a=1}^{4}d_a(k)\Gamma_a$"+"\n"+"x/y bond alternation",8.7)
    box(ax,7.62,4.72,3.92,1.38,"BULK MULTIPOLE","vanishing net dipole\nquantized quadrupole q_xy",9)
    box(ax,3.82,3.05,3.55,1.38,"BOUNDARY HIERARCHY","gapped bulk -> polarized edges\nedge termination -> corner charge",9)
    box(ax,7.62,3.05,3.92,1.38,"CORNER STATES"); [ax.scatter([px],[py],s=65) for px,py in [(8.15,3.32),(10.95,3.32),(8.15,4.04),(10.95,4.04)]]
    footer(ax,"four-site crystal + alternating couplings -> quadrupole topology -> corner modes"); save(fig,out/'bbh_designed_panel.pdf')

def kitaev(out):
    fig,ax=panel("Kitaev topological superconductor")
    box(ax,.45,3.55,3.15,2.55,"SPINLESS FERMION CHAIN"); lattice_chain(ax,.78,4.78,8,False); ax.plot([.85,3.05],[4.48,4.48],linestyle="--",linewidth=1.1)
    box(ax,3.82,4.72,3.55,1.38,"NAMBU / BdG HAMILTONIAN",r"basis $(c_k,c^\dagger_{-k})$"+"\n"+r"$H=(-\mu-2t\cos k)\tau_z+2\Delta\sin k\,\tau_y$",8.0)
    box(ax,7.62,4.72,3.92,1.38,"TOPOLOGICAL WINDOW","|mu| < 2|t|\nparticle-hole symmetry\nfermion parity protected",9)
    box(ax,3.82,3.05,3.55,1.38,"BULK GAP CLOSING","mu = +/- 2t\nBdG phase boundary",9)
    box(ax,7.62,3.05,3.92,1.38,"BOUNDARY CONSEQUENCE"); ax.scatter([8.20,10.95],[3.67,3.67],s=90); ax.plot([8.35,10.80],[3.67,3.67],linewidth=1)
    footer(ax,"pairing + hopping + chemical potential -> BdG topology -> Majorana zero modes"); save(fig,out/'kitaev_designed_panel.pdf')

def weyl(out):
    fig,ax=panel("Weyl Hamiltonian")
    box(ax,.45,3.55,3.15,2.55,"3D MOMENTUM-SPACE NODE"); xx=np.linspace(.9,3.1,60); ax.plot(xx,4.75+np.abs(xx-2.0)*.55,linewidth=1.2); ax.plot(xx,4.75-np.abs(xx-2.0)*.55,linewidth=1.2); ax.scatter([2.0],[4.75],s=35)
    box(ax,3.82,4.72,3.55,1.38,"LOW-ENERGY HAMILTONIAN",r"$H=v_xq_x\sigma_x+v_yq_y\sigma_y+v_zq_z\sigma_z$",8.6)
    box(ax,7.62,4.72,3.92,1.38,"TOPOLOGICAL CHARGE",r"$\chi=\mathrm{sgn}(v_xv_yv_z)$"+"\n"+"Berry flux through enclosing sphere",8.8)
    box(ax,3.82,3.05,3.55,1.38,"BULK GEOMETRY","node = momentum-space monopole\nopposite chiralities appear in pairs",9)
    box(ax,7.62,3.05,3.92,1.38,"SURFACE CONSEQUENCE"); ax.scatter([8.35,10.78],[3.65,3.65],s=50); ax.plot([8.42,10.71],[3.65,3.65],linewidth=2.2)
    footer(ax,"linear Weyl node -> quantized Berry flux -> surface Fermi arc"); save(fig,out/'weyl_designed_panel.pdf')

def main(outdir):
    out=Path(outdir); berry(out); ssh(out); rice(out); qwz(out); bhz(out); bbh(out); kitaev(out); weyl(out)
if __name__=='__main__':
    import sys; main(sys.argv[1] if len(sys.argv)>1 else 'generated/ch62/designed_hamiltonian_panels')
