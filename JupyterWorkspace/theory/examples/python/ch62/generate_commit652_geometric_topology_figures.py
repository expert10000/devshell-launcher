from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from geometric_topology_launch import *

def save(fig,p):
    p.parent.mkdir(parents=True,exist_ok=True); fig.tight_layout(); fig.savefig(p); plt.close(fig)

def main(outdir):
    out=Path(outdir)

    x,y,z=parameter_loop(.4)
    fig,ax=plt.subplots(); ax.plot(x,y); ax.scatter([0],[0]); ax.set_aspect("equal")
    ax.set(xlabel=r"$\lambda_1$",ylabel=r"$\lambda_2$",title="Closed adiabatic parameter loop")
    save(fig,out/"adiabatic_parameter_loop.pdf")

    xx=np.linspace(-2,2,220); yy=np.linspace(-2,2,220); X,Y=np.meshgrid(xx,yy)
    F=two_level_curvature_magnitude(X,Y,.4)
    fig,ax=plt.subplots(); ax.imshow(F,origin="lower",extent=[xx.min(),xx.max(),yy.min(),yy.max()],aspect="auto")
    ax.set(xlabel=r"$d_x$",ylabel=r"$d_y$",title="Two-level Berry-curvature magnitude")
    save(fig,out/"two_level_berry_curvature.pdf")

    om=np.linspace(0,4*np.pi,300)
    fig,ax=plt.subplots(); ax.plot(om,berry_phase_solid_angle(om,-1))
    ax.set(xlabel="enclosed solid angle",ylabel="Berry phase",title="Spin-half geometric phase")
    save(fig,out/"berry_phase_solid_angle.pdf")

    n,c=accumulated_chern_flux()
    fig,ax=plt.subplots(); ax.plot(n,c,marker="."); ax.axhline(1,linestyle="--")
    ax.set(xlabel="mesh resolution",ylabel="integrated Berry flux / 2pi",title="Chern-number convergence")
    save(fig,out/"chern_flux_quantization.pdf")

    t,d,m,q=thouless_cycle()
    fig,ax=plt.subplots(); ax.plot(t,d,label="dimerization"); ax.plot(t,m,label="staggering"); ax.plot(t,q,label="pumped charge")
    ax.set(xlabel="cycle fraction",ylabel="normalized value",title="Adiabatic pump cycle"); ax.legend()
    save(fig,out/"thouless_pump_cycle.pdf")

if __name__=="__main__":
    import sys; main(sys.argv[1] if len(sys.argv)>1 else "generated/ch62/computational")
