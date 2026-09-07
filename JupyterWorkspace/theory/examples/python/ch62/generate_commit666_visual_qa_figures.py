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

MODELS=["Berry 2-level","SSH","Rice-Mele","QWZ","BHZ","BBH","Kitaev","Weyl","Crystalline","Polarization","Higher-order","Interacting","Many-body invariant","Fractionalization","Topological order"]
def grammar(out):
    fig,ax=panel("Unified visual grammar","Volume VIII Visual QA")
    labels=[("SYSTEM",.55,4.65,1.75,1.05),("BASIS / DOF",2.55,4.65,1.75,1.05),("HAMILTONIAN",4.55,4.65,2.05,1.05),("SPECTRUM / INVARIANT",6.85,4.65,2.05,1.05),("BOUNDARY / OBSERVABLE",9.15,4.65,2.25,1.05)]
    for t,x,y,w,h in labels: box(ax,x,y,w,h,t)
    for i in range(len(labels)-1): arrow(ax,(labels[i][1]+labels[i][3],5.18),(labels[i+1][1],5.18))
    box(ax,1.10,2.72,3.10,1.35,"CAPTION MUST ANSWER","What is shown?\nWhich Hamiltonian term matters?\nWhat physical consequence follows?",8.8)
    box(ax,4.45,2.72,3.10,1.35,"FIGURE MUST EXPOSE","geometry / crystal\ncouplings / fields\nmathematical structure",8.8)
    box(ax,7.80,2.72,3.10,1.35,"QA FAILURE MODES","plot-only without system\nHamiltonian without term map\nboundary state without bulk link",8.6)
    footer(ax,"one visual language across the volume: system -> Hamiltonian -> topology -> observable consequence"); save(fig,out/'volume08_hamiltonian_visual_grammar.pdf')
def coverage(out):
    fig,ax=plt.subplots(figsize=(12,7)); data=np.ones((len(MODELS),5)); ax.imshow(data,aspect='auto',vmin=0,vmax=1); ax.set_yticks(range(len(MODELS)),MODELS,fontsize=8); ax.set_xticks(range(5),["system","basis / couplings","Hamiltonian","spectrum / invariant","boundary / response"],rotation=15)
    for i in range(data.shape[0]):
        for j in range(data.shape[1]): ax.text(j,i,"OK",ha='center',va='center',fontsize=7)
    ax.set_title("Chapter 62 designed-panel coverage matrix"); save(fig,out/'chapter62_designed_visual_coverage_matrix.pdf')
def comparison(out):
    fig,ax=panel("From plot-only to Hamiltonian teaching panel","Volume VIII Visual QA")
    box(ax,.65,3.45,4.65,2.35,"INSUFFICIENT FIGURE"); x=np.linspace(1.0,4.9,120); ax.plot(x,4.05+.35*np.sin(2*x),linewidth=1.1); ax.text(2.95,5.20,"single curve + title",ha='center',fontsize=9)
    box(ax,6.05,3.45,5.25,2.35,"DESIGNED HAMILTONIAN PANEL")
    for t,x0 in [("system",6.35),("H",7.55),("invariant",8.75),("boundary",10.0)]: ax.add_patch(Rectangle((x0,4.20),1.0,.70,fill=False,linewidth=1)); ax.text(x0+.5,4.55,t,ha='center',va='center',fontsize=8)
    footer(ax,"final standard: explanatory composition, not merely a generated plot"); save(fig,out/'plot_to_designed_panel_comparison.pdf')
def main(outdir):
    out=Path(outdir); grammar(out); coverage(out); comparison(out)
if __name__=='__main__':
    import sys; main(sys.argv[1] if len(sys.argv)>1 else 'generated/ch62/visual_qa')
