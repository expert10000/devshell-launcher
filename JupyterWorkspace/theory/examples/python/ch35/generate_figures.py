from pathlib import Path
import sys, math
import numpy as np
import matplotlib.pyplot as plt
sys.path.insert(0,str(Path(__file__).parent))
from magnetic_fields_companion import *
OUT=Path(__file__).resolve().parents[3]/'generated/ch35/computational'; OUT.mkdir(parents=True,exist_ok=True)

def save(name):
    plt.tight_layout(); plt.savefig(OUT/name,bbox_inches='tight'); plt.close()
# 1 orbit
T=np.linspace(0,2*math.pi,400); x,y=cyclotron_trajectory(T,0,0,1,0,1,1,1); plt.figure(figsize=(4.2,3.4)); plt.plot(x,y); plt.scatter([0],[0]); plt.axis('equal'); plt.xlabel('x'); plt.ylabel('y'); plt.title('Cyclotron orbit'); save('01_cyclotron_orbit.pdf')
# 2 omega scaling
B=np.linspace(.2,4,120); plt.figure(figsize=(4.2,3.4)); plt.plot(B,[cyclotron_frequency(1,b,1) for b in B]); plt.xlabel('B'); plt.ylabel(r'$\omega_c$'); plt.title('Cyclotron frequency'); save('02_cyclotron_scaling.pdf')
# 3 crossed drift
E=np.linspace(0,4,80); plt.figure(figsize=(4.2,3.4)); plt.plot(E,[exb_drift([e,0,0],[0,0,2])[1] for e in E]); plt.xlabel('E_x'); plt.ylabel('v_d,y'); plt.title(r'$\mathbf{E}\times\mathbf{B}$ drift'); save('03_exb_drift.pdf')
# 4 guiding center
T=np.linspace(0,9,600); x,y=cyclotron_trajectory(T,0,0,1,0,1,1,1); drift=np.array([0,-.18]); plt.figure(figsize=(4.2,3.4)); plt.plot(x+drift[0]*T,y+drift[1]*T); plt.xlabel('x'); plt.ylabel('y'); plt.title('Orbit plus guiding-center drift'); save('04_guiding_center_drift.pdf')
# 5 magnetic length
B=np.linspace(.2,5,120); plt.figure(figsize=(4.2,3.4)); plt.plot(B,[magnetic_length(1,b) for b in B]); plt.xlabel('B'); plt.ylabel(r'$\ell_B$'); plt.title('Magnetic length'); save('05_magnetic_length.pdf')
# 6 flux count
B=np.linspace(.1,5,120); plt.figure(figsize=(4.2,3.4)); plt.plot(B,[landau_state_count(10,1,b) for b in B]); plt.xlabel('B'); plt.ylabel('states in fixed area'); plt.title('Flux-cell state counting'); save('06_flux_state_count.pdf')
# 7 gauges
s=np.linspace(-2,2,17); X,Y=np.meshgrid(s,s); A1=landau_gauge_A(X,Y,1); A2=symmetric_gauge_A(X,Y,1); plt.figure(figsize=(4.2,3.4)); plt.quiver(X,Y,A1[...,0],A1[...,1],alpha=.55); plt.quiver(X,Y,A2[...,0],A2[...,1],alpha=.55); plt.xlabel('x'); plt.ylabel('y'); plt.title('Two gauges, one uniform B'); save('07_gauge_vector_fields.pdf')
# 8 commutator scales
B=np.linspace(.2,4,120); plt.figure(figsize=(4.2,3.4)); plt.plot(B,[abs(kinetic_momentum_commutator_scale(-1,b)) for b in B],label='|[pi_x,pi_y]| scale'); plt.plot(B,[abs(guiding_center_commutator_scale(-1,b)) for b in B],label='|[X,Y]| scale'); plt.yscale('log'); plt.xlabel('B'); plt.legend(fontsize=7); plt.title('Dual magnetic noncommutativity'); save('08_operator_scales.pdf')
# 9 hall current
B=np.linspace(.2,5,120); jy=[hall_drift_current_density(1,-1,[1,0,0],[0,0,b])[1] for b in B]; plt.figure(figsize=(4.2,3.4)); plt.plot(B,jy); plt.xlabel('B'); plt.ylabel('j_y'); plt.title('Classical Hall drift current'); save('09_hall_current.pdf')
