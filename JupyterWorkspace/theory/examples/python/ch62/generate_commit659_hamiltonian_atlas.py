"""Commit 659 Hamiltonian visual atlas."""
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Rectangle

def save(fig,p):
    p.parent.mkdir(parents=True,exist_ok=True); fig.tight_layout(); fig.savefig(p); plt.close(fig)

def setup_axes(title):
    fig,axs=plt.subplots(2,3,figsize=(12,7.4))
    fig.suptitle(title,fontsize=16)
    return fig,axs.ravel()

def chain(ax,t1=0.55,t2=1.0,onsite=None,pair=False):
    n=10
    for i in range(n):
        ax.add_patch(Circle((i,0),.10,fill=False,linewidth=1.3))
        if onsite is not None:
            ax.text(i,.25,f"{onsite[i%2]:+.1f}",ha="center",fontsize=8)
    for i in range(n-1):
        lw=1.3 if i%2==0 else 3.0
        ax.plot([i+.1,i+.9],[0,0],linewidth=lw)
        if pair:
            ax.plot([i+.15,i+.85],[-.18,-.18],linewidth=1.2,linestyle="--")
    ax.set(xlim=(-.5,n-.5),ylim=(-.5,.55)); ax.axis("off")

def ssh(out):
    fig,a=setup_axes("SSH Hamiltonian visual laboratory")
    chain(a[0]); a[0].set_title("real space: alternating bonds")
    a[1].axis("off"); a[1].text(.5,.7,r"basis: $(A,B)$",ha="center"); a[1].text(.5,.45,r"$h(k)=d_x\sigma_x+d_y\sigma_y$",ha="center",fontsize=13); a[1].text(.5,.25,r"$d_x=t_1+t_2\cos k,\ d_y=t_2\sin k$",ha="center")
    k=np.linspace(-np.pi,np.pi,400); E=np.sqrt((.55+np.cos(k))**2+np.sin(k)**2)
    a[2].plot(k,E); a[2].plot(k,-E); a[2].set_title("bulk bands"); a[2].set_xlabel("k")
    a[3].plot(.55+np.cos(k),np.sin(k)); a[3].scatter([0],[0]); a[3].set_aspect("equal"); a[3].set_title("winding encloses origin")
    t=np.linspace(.2,1.8,250); gap=2*np.abs(t-1); a[4].plot(t,gap); a[4].set_title("gap closes at $t_1=t_2$"); a[4].set_xlabel(r"$t_1/t_2$")
    x=np.arange(30); p=np.exp(-x/2.5)+np.exp(-(29-x)/2.5); p/=p.sum(); a[5].plot(x,p); a[5].set_title("open-chain edge modes")
    save(fig,out/"ssh_hamiltonian_visual_panel.pdf")

def rice(out):
    fig,a=setup_axes("Rice–Mele Hamiltonian visual laboratory")
    chain(a[0],onsite=(.5,-.5)); a[0].set_title("dimerization + staggered onsite")
    a[1].axis("off"); a[1].text(.5,.70,r"$h(k)=d_x\sigma_x+d_y\sigma_y+\Delta\sigma_z$",ha="center",fontsize=12); a[1].text(.5,.42,r"$d_x=t_1+t_2\cos k,\ d_y=t_2\sin k$",ha="center"); a[1].text(.5,.25,r"$d_z=\Delta$",ha="center")
    s=np.linspace(0,2*np.pi,300); a[2].plot(.7*np.cos(s),.7*np.sin(s)); a[2].scatter([0],[0]); a[2].set_aspect("equal"); a[2].set_title("pump loop around gap closing")
    k=np.linspace(-np.pi,np.pi,300); d=.5; E=np.sqrt((.7+np.cos(k))**2+np.sin(k)**2+d*d); a[3].plot(k,E); a[3].plot(k,-E); a[3].set_title("instantaneous gapped bands")
    q=(s-np.sin(s))/(2*np.pi); a[4].plot(s/(2*np.pi),q); a[4].set_title("pumped polarization")
    a[5].axis("off"); a[5].text(.5,.62,"Invariant",ha="center",fontsize=13); a[5].text(.5,.42,r"$C_{(k,t)}\in\mathbb{Z}$",ha="center",fontsize=17); a[5].text(.5,.22,"one cycle → quantized transported charge",ha="center")
    save(fig,out/"rice_mele_hamiltonian_visual_panel.pdf")

def qwz(out):
    fig,a=setup_axes("QWZ Chern-insulator Hamiltonian visual laboratory")
    # lattice
    for i in range(5):
        for j in range(5):
            a[0].add_patch(Circle((i,j),.07,fill=False))
            if i<4:a[0].plot([i+.07,i+.93],[j,j],linewidth=1)
            if j<4:a[0].plot([i,i],[j+.07,j+.93],linewidth=1)
    a[0].set_aspect("equal"); a[0].axis("off"); a[0].set_title("square lattice / two-orbital basis")
    a[1].axis("off"); a[1].text(.5,.72,r"$h=\sin k_x\sigma_x+\sin k_y\sigma_y$",ha="center",fontsize=12); a[1].text(.5,.48,r"$+(m+\cos k_x+\cos k_y)\sigma_z$",ha="center",fontsize=12); a[1].text(.5,.22,"mass term controls band inversion",ha="center")
    m=np.linspace(-3,3,300); c=np.where((m>-2)&(m<0),-1,np.where((m>0)&(m<2),1,0)); a[2].step(m,c); a[2].set_title("Chern phases"); a[2].set_xlabel("m")
    k=np.linspace(-np.pi,np.pi,250); KX,KY=np.meshgrid(k,k); dz=-1+np.cos(KX)+np.cos(KY); cur=1/(1+dz*dz+np.sin(KX)**2+np.sin(KY)**2); a[3].imshow(cur,origin="lower",extent=[-np.pi,np.pi,-np.pi,np.pi]); a[3].set_title("Berry-curvature texture")
    E=np.sqrt(np.sin(k)**2+( -1+np.cos(k)+1 )**2); a[4].plot(k,E); a[4].plot(k,-E); a[4].set_title("bulk cut")
    a[5].plot(k,.6*k,label="edge"); a[5].plot(k,-np.sqrt(k*k+1.2),alpha=.6); a[5].plot(k,np.sqrt(k*k+1.2),alpha=.6); a[5].set_title("chiral boundary branch")
    save(fig,out/"qwz_hamiltonian_visual_panel.pdf")

def bhz(out):
    fig,a=setup_axes("BHZ / quantum-spin-Hall Hamiltonian visual laboratory")
    a[0].axis("off"); a[0].text(.5,.72,r"basis: $(E1+,H1+,E1-,H1-)$",ha="center"); a[0].text(.5,.45,"orbital × Kramers structure",ha="center",fontsize=13)
    a[1].axis("off"); a[1].text(.5,.72,r"$H_{\rm BHZ}=\mathrm{diag}[h(\mathbf{k}),h^*(-\mathbf{k})]$",ha="center",fontsize=12); a[1].text(.5,.45,r"$h=A k_x\sigma_x+A k_y\sigma_y+(M-Bk^2)\sigma_z$",ha="center",fontsize=11)
    M=np.linspace(-2,2,300); a[2].plot(M,2*np.abs(M)); a[2].set_title("Dirac mass inversion"); a[2].set_xlabel("M")
    k=np.linspace(-1.5,1.5,300); bulk=np.sqrt(k*k+1.2**2); a[3].plot(k,bulk); a[3].plot(k,-bulk); a[3].set_title("gapped bulk")
    a[4].plot(k,k,label="Kramers 1"); a[4].plot(k,-k,label="Kramers 2"); a[4].set_title("helical edge pair"); a[4].legend()
    a[5].axis("off"); a[5].text(.5,.65,r"$\Theta^2=-1$",ha="center",fontsize=17); a[5].text(.5,.42,r"$\mathbb{Z}_2=1$",ha="center",fontsize=18); a[5].text(.5,.22,"opposite Chern-like blocks, zero net Chern number",ha="center")
    save(fig,out/"bhz_hamiltonian_visual_panel.pdf")

def bbh(out):
    fig,a=setup_axes("BBH quadrupole Hamiltonian visual laboratory")
    # simple 4-site cell array
    for i in range(3):
      for j in range(3):
        x,y=2*i,2*j
        for sx,sy in [(x,y),(x+1,y),(x+1,y+1),(x,y+1)]: a[0].add_patch(Circle((sx,sy),.08,fill=False))
        for A,B in [((x,y),(x+1,y)),((x+1,y),(x+1,y+1)),((x+1,y+1),(x,y+1)),((x,y+1),(x,y))]: a[0].plot([A[0],B[0]],[A[1],B[1]],linewidth=1)
        if i<2: a[0].plot([x+1,x+2],[y,y],linewidth=3)
        if j<2: a[0].plot([x,x],[y+1,y+2],linewidth=3)
    a[0].set_aspect("equal"); a[0].axis("off"); a[0].set_title("4-site cells: γ vs λ")
    a[1].axis("off"); a[1].text(.5,.68,r"$H=\sum_{a=1}^{4}d_a(\mathbf{k})\Gamma_a$",ha="center",fontsize=13); a[1].text(.5,.42,r"$d\sim(\lambda_y\sin k_y,\gamma_y+\lambda_y\cos k_y,$",ha="center"); a[1].text(.5,.25,r"$\lambda_x\sin k_x,\gamma_x+\lambda_x\cos k_x)$",ha="center")
    g=np.linspace(0,2,250); a[2].plot(g,2*np.abs(1-g)); a[2].set_title("bulk gap"); a[2].set_xlabel(r"$\gamma/\lambda$")
    a[3].step(g,np.where(g<1,.5,0)); a[3].set_title("quadrupole invariant")
    a[4].plot(g,.5*(1-np.tanh(5*(g-1)))); a[4].set_title("edge polarization")
    X,Y=np.meshgrid(np.arange(14),np.arange(14)); d=np.exp(-(X+Y)/1.5)+np.exp(-((13-X)+Y)/1.5)+np.exp(-(X+(13-Y))/1.5)+np.exp(-((13-X)+(13-Y))/1.5); a[5].imshow(d); a[5].set_title("corner-state density")
    save(fig,out/"bbh_hamiltonian_visual_panel.pdf")

def kitaev(out):
    fig,a=setup_axes("Kitaev topological-superconductor Hamiltonian visual laboratory")
    chain(a[0],pair=True); a[0].set_title("fermion hopping + pairing bonds")
    a[1].axis("off"); a[1].text(.5,.72,r"Nambu basis: $(c_k,c^\dagger_{-k})$",ha="center"); a[1].text(.5,.48,r"$H_{\rm BdG}=(-\mu-2t\cos k)\tau_z+2\Delta\sin k\,\tau_y$",ha="center",fontsize=11)
    mu=np.linspace(-3,3,300); gap=np.abs(np.abs(mu)-2); a[2].plot(mu,gap); a[2].set_title("bulk gap closings at μ=±2t")
    top=(np.abs(mu)<2).astype(float); a[3].fill_between(mu,0,top); a[3].set_title("topological interval")
    x=np.arange(40); p=np.exp(-x/3)+np.exp(-(39-x)/3); a[4].plot(x,p); a[4].set_title("Majorana end modes")
    a[5].axis("off"); a[5].text(.5,.68,r"$\mathcal{P}$ = fermion parity",ha="center",fontsize=14); a[5].text(.5,.44,"open chain → near-zero mode",ha="center"); a[5].text(.5,.25,"periodic chain → bulk invariant only",ha="center")
    save(fig,out/"kitaev_hamiltonian_visual_panel.pdf")

def weyl(out):
    fig,a=setup_axes("Weyl Hamiltonian visual laboratory")
    a[0].axis("off"); a[0].text(.5,.65,"isolated momentum-space node",ha="center",fontsize=14); a[0].scatter([.5],[.4],s=100); a[0].annotate("Berry-flux monopole",(.5,.4),(.65,.7),arrowprops=dict(arrowstyle="->"))
    a[1].axis("off"); a[1].text(.5,.68,r"$H=v_xq_x\sigma_x+v_yq_y\sigma_y+v_zq_z\sigma_z$",ha="center",fontsize=12); a[1].text(.5,.42,r"$\chi=\mathrm{sgn}(v_xv_yv_z)$",ha="center",fontsize=16)
    q=np.linspace(-2,2,300); E=np.abs(q); a[2].plot(q,E); a[2].plot(q,-E); a[2].set_title("linear cone")
    th=np.linspace(0,2*np.pi,100); a[3].quiver(np.cos(th)[::10],np.sin(th)[::10],np.cos(th)[::10],np.sin(th)[::10]); a[3].set_aspect("equal"); a[3].set_title("Berry-flux orientation")
    a[4].axis("off"); a[4].text(.5,.64,r"$\frac{1}{2\pi}\oint_{S^2}\mathcal{F}=\chi$",ha="center",fontsize=16); a[4].text(.5,.35,"node = topological defect in k-space",ha="center")
    a[5].plot([-1,1],[0,0],linewidth=3); a[5].scatter([-1,1],[0,0],s=80); a[5].set_title("surface Fermi arc connects projected nodes"); a[5].axis("off")
    save(fig,out/"weyl_hamiltonian_visual_panel.pdf")

def nodal(out):
    fig,a=setup_axes("Nodal-line Hamiltonian visual laboratory")
    a[0].axis("off"); a[0].text(.5,.68,r"$H=(k_x^2+k_y^2-k_0^2)\sigma_x+v_zk_z\sigma_z$",ha="center",fontsize=11); a[0].text(.5,.38,"zero energy requires both coefficients = 0",ha="center")
    th=np.linspace(0,2*np.pi,300); a[1].plot(np.cos(th),np.sin(th)); a[1].set_aspect("equal"); a[1].set_title("nodal ring in kz=0 plane")
    q=np.linspace(-1.6,1.6,220); X,Y=np.meshgrid(q,q); E=np.abs(X*X+Y*Y-1); a[2].imshow(E,origin="lower",extent=[q.min(),q.max(),q.min(),q.max()]); a[2].set_title("gap map")
    # linked loop
    a[3].plot(np.cos(th),np.sin(th)); a[3].plot(1+.35*np.cos(th),.35*np.sin(th)); a[3].set_aspect("equal"); a[3].set_title("linked Berry-phase loop")
    m=np.linspace(0,1,200); a[4].plot(m,m); a[4].set_title("symmetry-breaking mass opens gap")
    a[5].axis("off"); a[5].text(.5,.65,r"linked loop: $\gamma_B=\pi$ (protected case)",ha="center",fontsize=14); a[5].text(.5,.38,"node dimension = 1 in 3D momentum space",ha="center")
    save(fig,out/"nodal_line_hamiltonian_visual_panel.pdf")

def main(outdir):
    out=Path(outdir)
    ssh(out); rice(out); qwz(out); bhz(out); bbh(out); kitaev(out); weyl(out); nodal(out)

if __name__=="__main__":
    import sys; main(sys.argv[1] if len(sys.argv)>1 else "generated/ch62/hamiltonian_atlas")
