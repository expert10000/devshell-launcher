from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from edge_states_companion import *
OUT=Path(__file__).resolve().parents[3]/'generated/ch38/computational'; OUT.mkdir(parents=True,exist_ok=True)
def save(name):
    plt.tight_layout(); plt.savefig(OUT/name,format='pdf'); plt.close()
# 1 confinement-bent edge dispersion
k=np.linspace(-5,5,500); Y=-k; wall=np.log1p(np.exp((Y-1.2)/.45))*.45
plt.figure()
for n in range(4): plt.plot(k,n+.5+wall)
plt.axhline(3.2,linestyle='--'); plt.xlabel('edge wave number k'); plt.ylabel('E'); save('01_edge_dispersion.pdf')
# 2 group velocity from dispersion slope
E=.5+np.log1p(np.exp((-k-1.2)/.5))*.5; v=np.gradient(E,k)
plt.figure(); plt.plot(k,v); plt.xlabel('k'); plt.ylabel('v = (1/hbar) dE/dk'); save('02_group_velocity.pdf')
# 3 channel conductance quantization
N=np.arange(1,7); plt.figure(); plt.step(N,[multichannel_conductance(np.ones(n)) for n in N],where='mid'); plt.xlabel('open channels'); plt.ylabel('G / (e^2/h)'); save('03_landauer_quantum.pdf')
# 4 ideal six-terminal Hall potentials
contacts=np.arange(1,7); V=ideal_hall_probe_voltages(1,0); plt.figure(); plt.step(contacts,V,where='mid'); plt.xticks(contacts); plt.xlabel('contact'); plt.ylabel('electrochemical voltage'); save('04_six_terminal_potentials.pdf')
# 5 QPC conductance steps
g=np.linspace(-3,4,500); thresholds=np.array([-1.2,.2,1.6,3.0]); Ts=1/(1+np.exp(-(g[:,None]-thresholds[None,:])*7)); G=Ts.sum(axis=1)
plt.figure(); plt.plot(g,G); plt.xlabel('QPC gate control'); plt.ylabel('G / (e^2/h)'); save('05_qpc_steps.pdf')
# 6 co-propagating equilibration
x=np.linspace(0,5,300); a,b=equilibration_profile(x,3,1,1.2); plt.figure(); plt.plot(x,a,label='channel 1'); plt.plot(x,b,label='channel 2'); plt.xlabel('distance / ell_eq'); plt.ylabel('electrochemical potential'); plt.legend(); save('06_equilibration.pdf')
# 7 bulk-boundary interface index
CR=np.arange(0,6); CL=5*np.ones_like(CR); idx=[bulk_boundary_index(a,b) for a,b in zip(CL,CR)]; plt.figure(); plt.step(CR,idx,where='mid'); plt.xlabel('right-hand Chern integer'); plt.ylabel('N+ - N-'); save('07_bulk_boundary_index.pdf')
# 8 flux spectral flow
phi=np.linspace(0,1,250); levels=spectral_flow_levels(phi,range(6)); plt.figure();
for row in levels: plt.plot(phi,row)
plt.xlabel('inserted flux / Phi0'); plt.ylabel('edge spectral label'); save('08_spectral_flow.pdf')
# 9 local filling and incompressible strips
y=np.linspace(-4,4,600); nu=3.2/(1+np.exp((np.abs(y)-2.7)/.35)); mask=incompressible_mask(nu,.06); plt.figure(); plt.plot(y,nu,label='local filling'); plt.plot(y,np.where(mask,nu,np.nan),linewidth=3,label='near integer'); plt.xlabel('transverse coordinate'); plt.ylabel('local filling'); plt.legend(); save('09_edge_strips.pdf')
