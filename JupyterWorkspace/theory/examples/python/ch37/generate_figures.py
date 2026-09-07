from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from integer_qhe_companion import *
OUT=Path(__file__).resolve().parents[3]/'generated/ch37/computational'; OUT.mkdir(parents=True,exist_ok=True)
def save(name):
    plt.tight_layout(); plt.savefig(OUT/name,format='pdf'); plt.close()
# 1 plateau trace
x=np.linspace(.2,5.8,700); N=np.maximum(1,np.floor(x).astype(int)); rxy=np.array([hall_resistance(n) for n in N]); rxx=.12*np.sin(np.pi*x)**8
plt.figure(); plt.plot(x,rxy,label='Rxy'); plt.plot(x,rxx,label='Rxx'); plt.xlabel('control parameter'); plt.ylabel('dimensionless resistance'); plt.legend(); save('01_plateau_trace.pdf')
# 2 tensor inversion
sxx=np.linspace(0,.8,300); plt.figure(); plt.plot(sxx,[abs(resistivity_tensor(a,2)[0,1]) for a in sxx],label='|rho_xy|'); plt.plot(sxx,[resistivity_tensor(a,2)[0,0] for a in sxx],label='rho_xx'); plt.xlabel('sigma_xx'); plt.ylabel('resistivity'); plt.legend(); save('02_tensor_inversion.pdf')
# 3 filling map
B=np.linspace(.5,5,300); plt.figure(); plt.plot(B,[filling_factor(2,b) for b in B]); plt.xlabel('B'); plt.ylabel('nu'); save('03_filling_factor.pdf')
# 4 broadened DOS
E=np.linspace(0,7,1000); centers=np.arange(.5,7,.9); plt.figure(); plt.plot(E,gaussian_broadened_dos(E,centers,.13)); plt.xlabel('E'); plt.ylabel('DOS'); save('04_broadened_dos.pdf')
# 5 quantized Kubo staircase
nu=np.linspace(.2,6,400); plt.figure(); plt.step(nu,[plateau_integer(v) for v in nu],where='post'); plt.xlabel('nu'); plt.ylabel('sigma_xy / (e^2/h)'); save('05_kubo_integer.pdf')
# 6 spectral flow
phi=np.linspace(0,1,200); plt.figure();
for j in range(5): plt.plot(phi,j+phi)
plt.xlabel('Phi/Phi0'); plt.ylabel('orbital label'); save('06_spectral_flow.pdf')
# 7 pumped charge
N=np.arange(1,7); plt.figure(); plt.plot(N,[pumped_charge(n) for n in N],marker='o'); plt.xlabel('filled levels'); plt.ylabel('pumped charge / e'); save('07_pumped_charge.pdf')
# 8 Hall-bar potentials
x=np.linspace(0,1,300); plt.figure(); plt.plot(x,np.ones_like(x),label='top edge'); plt.plot(x,np.zeros_like(x),label='bottom edge'); plt.xlabel('x/L'); plt.ylabel('electrochemical potential'); plt.legend(); save('08_hall_bar_potentials.pdf')
# 9 edge dispersion
k=np.linspace(-3,3,400); plt.figure(); plt.plot(k,.5*k*k+1,label='bulk-like branch'); plt.plot(k,.15*k+2,label='edge crossing'); plt.axhline(2.0,linestyle='--'); plt.xlabel('k'); plt.ylabel('E'); plt.legend(); save('09_edge_dispersion.pdf')
