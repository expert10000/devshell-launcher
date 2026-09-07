from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D  # noqa
from interacting_topology import *
def save(fig,p): p.parent.mkdir(parents=True,exist_ok=True); fig.tight_layout(); fig.savefig(p); plt.close(fig)
def conceptual_collective(out):
 fig,ax=plt.subplots(figsize=(8,5)); pts=[]
 for j in range(5):
  for i in range(7): pts.append((i,j))
 pts=np.array(pts,float); ax.scatter(pts[:,0],pts[:,1],s=45)
 for j in range(5):
  for i in range(7):
   if i<6: ax.plot([i,i+1],[j,j],linewidth=.7,alpha=.5)
   if j<4: ax.plot([i,i],[j,j+1],linewidth=.7,alpha=.5)
 x=np.linspace(0,6,300)
 for j in [1,2,3]: ax.plot(x,j+.16*np.sin(2*np.pi*(x/2-j*.2)),linewidth=2,alpha=.75)
 ax.set_title('collective interacting topology: correlated motion across the lattice'); ax.set_aspect('equal'); ax.axis('off'); save(fig,out/'interacting_topology_collective_motion_concept.pdf')
def conceptual_knot(out):
 fig=plt.figure(figsize=(7,6)); ax=fig.add_subplot(111,projection='3d'); t=np.linspace(0,2*np.pi,900)
 for phase in np.linspace(0,2*np.pi,7,endpoint=False):
  x=(2+.35*np.cos(3*t+phase))*np.cos(2*t); y=(2+.35*np.cos(3*t+phase))*np.sin(2*t); z=.35*np.sin(3*t+phase); ax.plot(x,y,z,linewidth=1.2)
 ax.set_title('global many-body invariant as a linked collective object'); ax.set_axis_off(); save(fig,out/'many_body_invariant_global_knot.pdf')
def conceptual_fractionalization(out):
 fig,ax=plt.subplots(figsize=(10,4)); ax.scatter([.7,1.1,1.5],[2.6,2.0,2.6],s=160); ax.text(1.1,1.25,'microscopic electrons',ha='center')
 # fluid region
 xx=np.linspace(3,6,240); yy=2+0.55*np.sin(4*xx)+0.2*np.sin(9*xx); ax.fill_between(xx,yy-.65,yy+.65,alpha=.22); ax.plot(xx,yy,linewidth=2); ax.text(4.5,.8,'correlated quantum fluid',ha='center')
 xs=np.linspace(7.0,9.2,5); ys=2+.55*np.sin(np.arange(5)); ax.scatter(xs,ys,s=110); 
 for x,y in zip(xs,ys): ax.text(x,y-.45,r'$q=e/3$',ha='center',fontsize=8)
 ax.annotate('',xy=(2.7,2.2),xytext=(1.8,2.2),arrowprops={'arrowstyle':'->'}); ax.annotate('',xy=(6.7,2.2),xytext=(6.1,2.2),arrowprops={'arrowstyle':'->'}); ax.set(xlim=(0,10),ylim=(0,4),title='fractionalized quasiparticles emerge from collective order'); ax.axis('off'); save(fig,out/'fractionalization_quasiparticle_emergence.pdf')
def conceptual_boundary(out):
 fig=plt.figure(figsize=(7,6)); ax=fig.add_subplot(111,projection='3d'); L=2.0
 pts=np.array([[0,0,0],[L,0,0],[L,L,0],[0,L,0],[0,0,L],[L,0,L],[L,L,L],[0,L,L]])
 edges=[(0,1),(1,2),(2,3),(3,0),(4,5),(5,6),(6,7),(7,4),(0,4),(1,5),(2,6),(3,7)]
 for a,b in edges: ax.plot(*zip(pts[a],pts[b]),linewidth=2.5,alpha=.6)
 rng=np.random.default_rng(2); cloud=rng.uniform(.25,1.75,(45,3)); ax.scatter(cloud[:,0],cloud[:,1],cloud[:,2],s=10,alpha=.35)
 for a,b in zip(cloud[:-1:3],cloud[1::3]): ax.plot(*zip(a,b),linewidth=.45,alpha=.3)
 ax.scatter(pts[:,0],pts[:,1],pts[:,2],s=100); ax.set_title('correlated bulk with lower-dimensional emergent boundary response'); ax.set_axis_off(); save(fig,out/'interacting_boundary_hierarchy_fractional_corner_states.pdf')
def main(outdir):
 out=Path(outdir); concept=out.parent/'conceptual'; conceptual_collective(concept); conceptual_knot(concept); conceptual_fractionalization(concept); conceptual_boundary(concept)
 th=np.linspace(0,2*np.pi,300); fig,ax=plt.subplots(); ax.plot(th,many_body_berry_phase(th)); ax.set(xlabel='boundary twist',ylabel='Berry phase',title='Many-body geometric phase'); save(fig,out/'many_body_berry_phase_twist.pdf')
 n=np.arange(4,65); fig,ax=plt.subplots(); ax.plot(n,many_body_chern_convergence(n)); ax.axhline(1,linestyle='--'); ax.set(xlabel='twist-grid resolution',ylabel='many-body Chern estimate',title='Many-body Chern convergence'); save(fig,out/'many_body_chern_convergence.pdf')
 x=np.linspace(-1,1,300); fig,ax=plt.subplots(); ax.plot(x,resta_polarization(x,1),label='U=1'); ax.plot(x,resta_polarization(x,2.5),label='U=2.5'); ax.set(xlabel='control',ylabel='polarization / e',title='Resta polarization'); ax.legend(); save(fig,out/'resta_polarization.pdf')
 lv=entanglement_levels(x); fig,ax=plt.subplots(); ax.plot(x,lv); ax.set(xlabel='control',ylabel='entanglement level',title='Entanglement-spectrum rearrangement'); save(fig,out/'entanglement_spectrum_transition.pdf')
 b=flux_spectral_branches(th); fig,ax=plt.subplots(); ax.plot(th,b); ax.set(xlabel='inserted flux angle',ylabel='many-body energy',title='Flux-insertion spectral flow'); save(fig,out/'flux_insertion_spectral_flow.pdf')
 L=np.arange(4,60); fig,ax=plt.subplots(); ax.semilogy(L,multiplet_splitting(L)); ax.set(xlabel='system size',ylabel='multiplet splitting',title='Topological ground-state multiplet splitting'); save(fig,out/'ground_state_multiplet_splitting.pdf')
 xx=np.linspace(-8,8,500); rho=fractional_charge_profile(xx); cum=np.array([np.trapezoid(rho[:i+1],xx[:i+1]) if i>0 else 0 for i in range(len(xx))]); fig,ax=plt.subplots(); ax.plot(xx,cum); ax.axhline(1/3,linestyle='--'); ax.set(xlabel='integration boundary',ylabel='accumulated excess charge / e',title='Fractional charge accumulation'); save(fig,out/'fractional_charge_accumulation.pdf')
 U=np.linspace(0,4,300); fig,ax=plt.subplots(); ax.plot(U,interaction_gap(U)); ax.set(xlabel='interaction U',ylabel='many-body diagnostic gap',title='Interaction-driven topological transition'); save(fig,out/'interaction_topological_transition.pdf')
 fig,ax=plt.subplots(); ax.plot(U,single_particle_invariant(U),label='single-particle diagnostic'); ax.plot(U,many_body_invariant(U),label='many-body invariant'); ax.set(xlabel='interaction U',ylabel='normalized topological diagnostic',title='Single-particle versus many-body topology'); ax.legend(); save(fig,out/'single_particle_vs_many_body_invariant.pdf')
 fig,ax=plt.subplots(figsize=(8,4)); labels=['needs symmetry','fractional quasiparticles','topological degeneracy','long-range entanglement']; spt=[1,0,0,0]; intrinsic=[0,1,1,1]; x0=np.arange(len(labels)); ax.bar(x0-.18,spt,.36,label='SPT'); ax.bar(x0+.18,intrinsic,.36,label='intrinsic topological order'); ax.set_xticks(x0,labels,rotation=18); ax.set_ylim(0,1.25); ax.set_title('SPT versus intrinsic topological order'); ax.legend(); save(fig,out/'spt_vs_topological_order_comparison.pdf')
if __name__=='__main__':
 import sys; main(sys.argv[1] if len(sys.argv)>1 else 'generated/ch62/computational')
