from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from disorder_real_space_topology import *
def save(fig,p): p.parent.mkdir(parents=True,exist_ok=True); fig.tight_layout(); fig.savefig(p); plt.close(fig)
def main(outdir):
 out=Path(outdir); Ws=np.linspace(0,6,36)
 vals=[]
 for W in Ws:
  e=np.linalg.eigvalsh(qwz_realspace(5,-1,W,seed=2)); vals.append(e)
 vals=np.array(vals); fig,ax=plt.subplots(); ax.plot(Ws,vals); ax.set(xlabel='disorder W',ylabel='energy',title='Disordered finite Chern spectrum'); save(fig,out/'disordered_chern_spectrum.pdf')
 ip=[]
 for W in Ws: ip.append(median_ipr_near_zero(qwz_realspace(5,-1,W,seed=3)))
 fig,ax=plt.subplots(); ax.plot(Ws,ip); ax.set(xlabel='disorder W',ylabel='median IPR',title='Localization near the Fermi level'); save(fig,out/'ipr_vs_disorder.pdf')
 th=np.linspace(0,2*np.pi,80); flow=[]
 for x in th: flow.append(np.linalg.eigvalsh(qwz_realspace(4,-1,1.0,seed=4,theta_x=x)))
 flow=np.array(flow); fig,ax=plt.subplots(); ax.plot(th,flow); ax.set(xlabel=r'$\theta_x$',ylabel='energy',title='Twisted-boundary spectral flow'); save(fig,out/'twisted_boundary_spectral_flow.pdf')
 b=[]
 for W in np.linspace(0,5,20): b.append(bott_index(qwz_realspace(4,-1,W,seed=1),4))
 fig,ax=plt.subplots(); ax.plot(np.linspace(0,5,20),b,marker='.'); ax.set(xlabel='disorder W',ylabel='Bott index',title='Real-space topological invariant'); save(fig,out/'bott_index_vs_disorder.pdf')
 mk=local_chern_marker_proxy(20); fig,ax=plt.subplots(); ax.imshow(mk,origin='lower'); ax.set(xlabel='x',ylabel='y',title='Local Chern marker proxy'); save(fig,out/'local_chern_marker_map.pdf')
 m=np.linspace(-3,1,180); W=np.linspace(0,6,160); M,WW=np.meshgrid(m,W); Z=topological_anderson_indicator(M,WW); fig,ax=plt.subplots(); ax.imshow(Z,origin='lower',aspect='auto',extent=[m.min(),m.max(),W.min(),W.max()]); ax.set(xlabel='bare mass',ylabel='disorder W',title='Topological-Anderson window'); save(fig,out/'topological_anderson_phase_map.pdf')
 ef=np.linspace(-2,2,400); fig,ax=plt.subplots(); ax.plot(ef,hall_plateau(ef)); ax.set(xlabel='Fermi energy',ylabel=r'$\sigma_{xy}$ proxy',title='Mobility-gap Hall plateau'); save(fig,out/'hall_conductivity_plateau.pdf')
 edge=np.exp(-(Ws/5.0)**4); fig,ax=plt.subplots(); ax.plot(Ws,edge); ax.set(xlabel='disorder W',ylabel='boundary-weight proxy',title='Edge-state robustness'); save(fig,out/'edge_state_robustness_disorder.pdf')
 fig,ax=plt.subplots();
 for L in [12,24,48]: ax.plot(Ws,localization_length_proxy(Ws,L)/L,label=f'L={L}')
 ax.set(xlabel='disorder W',ylabel=r'$\xi/L$',title='Localization-length scaling'); ax.legend(); save(fig,out/'localization_length_scaling.pdf')
 control=np.linspace(-3,1,250); clean=((control>-2)&(control<0)).astype(float); real=.5*(np.tanh((control+2.05)/.08)-np.tanh((control+.05)/.08)); fig,ax=plt.subplots(); ax.plot(control,clean,label='clean Chern'); ax.plot(control,real,label='real-space invariant'); ax.set(xlabel='mass control',ylabel='topological index',title='Clean and real-space invariants'); ax.legend(); save(fig,out/'clean_vs_realspace_invariant.pdf')
 pump=1-.08*(Ws/6)**4; fig,ax=plt.subplots(); ax.plot(Ws,pump); ax.set(xlabel='disorder W',ylabel='pumped charge',title='Disordered charge-pump robustness'); save(fig,out/'charge_pump_with_disorder.pdf')
if __name__=='__main__':
 import sys; main(sys.argv[1] if len(sys.argv)>1 else 'generated/ch62/computational')
