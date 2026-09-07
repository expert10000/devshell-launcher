from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D  # noqa
from crystalline_higher_order import *

def save(fig,p): p.parent.mkdir(parents=True,exist_ok=True); fig.tight_layout(); fig.savefig(p); plt.close(fig)

def draw_cube(ax,scale=1.0,offset=(0,0,0),lw=1.0,alpha=1.0):
    pts=np.array([[0,0,0],[1,0,0],[1,1,0],[0,1,0],[0,0,1],[1,0,1],[1,1,1],[0,1,1]],float)*scale+np.array(offset)
    edges=[(0,1),(1,2),(2,3),(3,0),(4,5),(5,6),(6,7),(7,4),(0,4),(1,5),(2,6),(3,7)]
    for a,b in edges: ax.plot(*zip(pts[a],pts[b]),linewidth=lw,alpha=alpha)
    return pts

def conceptual_crystal(out):
    fig=plt.figure(figsize=(9,4.5)); ax=fig.add_subplot(121,projection="3d")
    for i in range(3):
      for j in range(3):
       for k in range(2):
        draw_cube(ax,.75,(i*.8,j*.8,k*.8),lw=.7,alpha=.45); th=np.linspace(0,2*np.pi,60); cx=i*.8+.375; cy=j*.8+.375; cz=k*.8+.375
        ax.plot(cx+.16*np.cos(th),cy+.16*np.sin(th),cz+.05*np.sin(2*th),linewidth=1.2)
    ax.set_title("ordered crystal + locked phase texture"); ax.set_axis_off()
    ax2=fig.add_subplot(122,projection="3d")
    for i in range(3):
      for j in range(3):
       for k in range(2):
        sh=.08*np.sin(i+j+k); draw_cube(ax2,.75,(i*.8+sh,j*.8-.05*sh,k*.8),lw=.7,alpha=.45); th=np.linspace(0,2*np.pi,60); cx=i*.8+.375+sh; cy=j*.8+.375-.05*sh; cz=k*.8+.375
        ax2.plot(cx+.16*np.cos(th),cy+.16*np.sin(th),cz+.05*np.sin(2*th),linewidth=1.2)
    ax2.set_title("deformed geometry, same topology"); ax2.set_axis_off(); save(fig,out/'crystalline_topology_lattice_concept.pdf')

def conceptual_polarization(out):
    fig,axs=plt.subplots(1,2,figsize=(9,4))
    for ax,aligned,title in [(axs[0],False,"trivial / cancelling"),(axs[1],True,"quantized polarization")]:
        for i in range(5):
            for j in range(5):
                ax.add_patch(plt.Rectangle((i,j),1,1,fill=False,linewidth=.6)); dx,dy=(.55,.25) if aligned else ((-.45 if (i+j)%2 else .45),.2*((i%2)*2-1)); ax.arrow(i+.25,j+.35,dx,dy,width=.018,length_includes_head=True)
        ax.set(xlim=(0,5),ylim=(0,5),title=title); ax.set_aspect('equal'); ax.axis('off')
    save(fig,out/'inversion_quantized_polarization_field.pdf')

def conceptual_hierarchy(out):
    fig=plt.figure(figsize=(7,6)); ax=fig.add_subplot(111,projection='3d'); pts=draw_cube(ax,2.0,lw=1.0,alpha=.35)
    edges=[(0,1),(1,2),(2,3),(3,0),(4,5),(5,6),(6,7),(7,4),(0,4),(1,5),(2,6),(3,7)]
    for a,b in edges: ax.plot(*zip(pts[a],pts[b]),linewidth=3,alpha=.65)
    ax.scatter(pts[:,0],pts[:,1],pts[:,2],s=110); ax.text(1,1,1,'bulk',ha='center'); ax.set_title('3D bulk → 2D faces → 1D edges → 0D corners'); ax.set_axis_off(); save(fig,out/'higher_order_boundary_hierarchy_cube.pdf')

def conceptual_tiers(out):
    fig,axs=plt.subplots(1,4,figsize=(11,3)); titles=['Tier 1: bulk','Tier 2: faces','Tier 3: edges','Tier 4: corners']
    for idx,ax in enumerate(axs):
        ax.add_patch(plt.Rectangle((.1,.1),.8,.8,fill=False,linewidth=1))
        if idx>=1: ax.add_patch(plt.Rectangle((.12,.12),.76,.76,fill=False,linewidth=3,alpha=.35))
        if idx>=2:
            for seg in [([.12,.88],[.12,.12]),([.12,.88],[.88,.88]),([.12,.12],[.12,.88]),([.88,.88],[.12,.88])]: ax.plot(*seg,linewidth=4,alpha=.65)
        if idx>=3: ax.scatter([.12,.88,.12,.88],[.12,.12,.88,.88],s=120)
        ax.set_title(titles[idx],fontsize=9); ax.set_xlim(0,1); ax.set_ylim(0,1); ax.set_aspect('equal'); ax.axis('off')
    save(fig,out/'boundary_hierarchy_topological_corner_states.pdf')

def main(outdir):
    out=Path(outdir); concept=out.parent/'conceptual'; conceptual_crystal(concept); conceptual_polarization(concept); conceptual_hierarchy(concept); conceptual_tiers(concept)
    lam=np.linspace(0,1,300); fig,ax=plt.subplots(); ax.plot(lam,wannier_center_flow(lam)); ax.set(xlabel='control parameter',ylabel='Wannier center',title='Wannier-center flow'); save(fig,out/'wannier_center_flow.pdf')
    m=np.linspace(-1,1,200); fig,ax=plt.subplots(); ax.step(m,parity_indicator(m),where='mid'); ax.set(xlabel='mass parameter',ylabel='parity indicator',title='Symmetry-indicator switch'); save(fig,out/'symmetry_indicator_parity_switch.pdf')
    g=np.linspace(0,2,250); fig,ax=plt.subplots(); ax.plot(g,bbh_bulk_gap(g)); ax.set(xlabel=r'$\gamma/\lambda$',ylabel='bulk gap',title='BBH bulk-gap closing'); save(fig,out/'bbh_bulk_gap.pdf')
    den=bbh_corner_density(16); fig,ax=plt.subplots(); ax.imshow(den,origin='lower'); ax.set(xlabel='x',ylabel='y',title='Corner-state probability density'); save(fig,out/'bbh_corner_state_density.pdf')
    fig,ax=plt.subplots(); ax.step(g,quadrupole_invariant(g),where='mid'); ax.set(xlabel=r'$\gamma/\lambda$',ylabel=r'$q_{xy}$',title='Quadrupole invariant'); save(fig,out/'bbh_quadrupole_invariant.pdf')
    p=np.linspace(0,1,250); fig,ax=plt.subplots(); ax.plot(p,corner_mode_splitting(p,False),label='symmetry preserving'); ax.plot(p,corner_mode_splitting(p,True),label='symmetry breaking'); ax.set(xlabel='perturbation strength',ylabel='corner-mode splitting',title='Corner-state symmetry protection'); ax.legend(); save(fig,out/'corner_mode_symmetry_breaking.pdf')
    x=np.linspace(-.5,.5,250); fig,ax=plt.subplots(); ax.plot(x,inversion_polarization(x)); ax.set(xlabel='dimerization control',ylabel='polarization / e',title='Inversion-quantized polarization'); save(fig,out/'inversion_polarization_transition.pdf')
    ep=.5*(1-np.tanh(6*(g-1))); fig,ax=plt.subplots(); ax.plot(g,ep); ax.set(xlabel=r'$\gamma/\lambda$',ylabel='edge polarization proxy',title='Edge polarization in the higher-order phase'); save(fig,out/'bbh_edge_polarization.pdf')
if __name__=='__main__':
 import sys; main(sys.argv[1] if len(sys.argv)>1 else 'generated/ch62/computational')
