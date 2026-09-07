from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from fractional_hall_companion import *
OUT=Path(__file__).resolve().parents[3]/'generated/ch39/computational'; OUT.mkdir(parents=True,exist_ok=True)
def save(name):
    plt.tight_layout(); plt.savefig(OUT/name,format='pdf'); plt.close()
# 1 energy hierarchy / mixing
B=np.linspace(.5,12,300); ec=np.sqrt(B); cyc=2.2*B
plt.figure(); plt.plot(B,ec,label='interaction scale'); plt.plot(B,cyc,label='cyclotron scale'); plt.xlabel('B'); plt.ylabel('dimensionless energy'); plt.legend(); save('01_energy_hierarchy.pdf')
# 2 many-body Hilbert growth at approximate 1/3
N=np.arange(3,11); dims=[]
for n in N:
    nphi=laughlin_sphere_flux(int(n),3); dims.append(hilbert_dimension(int(n),sphere_orbitals(nphi)))
plt.figure(); plt.semilogy(N,dims,marker='o'); plt.xlabel('electron number N'); plt.ylabel('raw LLL basis dimension'); save('02_hilbert_growth.pdf')
# 3 short-distance correlation holes
r=np.linspace(0,1,250); plt.figure()
for m in (1,3,5): plt.plot(r,pair_correlation_short_distance(r,m),label=f'm={m}')
plt.xlabel('r / l_B'); plt.ylabel('short-distance g(r) scale'); plt.legend(); save('03_correlation_hole.pdf')
# 4 fractional charge sequence
m=np.array([1,3,5,7,9]); plt.figure(); plt.plot(m,[quasihole_charge(int(x)) for x in m],marker='o'); plt.xlabel('Laughlin denominator m'); plt.ylabel('|e*| / e'); save('04_fractional_charge.pdf')
# 5 statistics sequence
plt.figure(); plt.plot(m,[exchange_angle(int(x))/np.pi for x in m],marker='o'); plt.xlabel('Laughlin denominator m'); plt.ylabel('exchange angle / pi'); save('05_exchange_angle.pdf')
# 6 pseudopotential ladder
R=np.array([1,3,5,7,9]); V=np.exp(-.32*(R-1)); plt.figure(); plt.bar(R,V,width=1.2); plt.xlabel('relative angular momentum R'); plt.ylabel('model V_R'); save('06_pseudopotentials.pdf')
# 7 finite-size gap extrapolation
N=np.array([6,8,10,12,14,16.]); gaps=.075+.28/N; intercept,slope=linear_gap_extrapolation(N,gaps); x=1/N
plt.figure(); plt.plot(x,gaps,marker='o'); xx=np.linspace(0,x.max(),100); plt.plot(xx,intercept+slope*xx); plt.xlabel('1/N'); plt.ylabel('neutral gap / E_C'); save('07_gap_extrapolation.pdf')
# 8 torus spectral flow
phi=np.linspace(0,1,300); levels=spectral_flow_levels(phi,3); plt.figure()
for row in levels: plt.plot(phi,row)
plt.xlabel('twist / 2pi'); plt.ylabel('ground-state flow label'); save('08_torus_spectral_flow.pdf')
# 9 fractional Hall sequence
nu=np.array([1,1/3,1/5,1/7]); labels=['1','1/3','1/5','1/7']; plt.figure(); plt.bar(np.arange(len(nu)),nu); plt.xticks(np.arange(len(nu)),labels); plt.xlabel('filling'); plt.ylabel('|sigma_xy| / (e^2/h)'); save('09_fractional_hall_response.pdf')
