from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from landau_quantization_companion import *
OUT=Path(__file__).resolve().parents[3]/'generated/ch36/computational'; OUT.mkdir(parents=True,exist_ok=True)

def save(name):
    plt.tight_layout(); plt.savefig(OUT/name,format='pdf'); plt.close()
B=np.linspace(.2,5,200)
plt.figure();
for n in range(4): plt.plot(B,[landau_energy(n,b) for b in B],label=f'n={n}')
plt.xlabel('B'); plt.ylabel('E'); plt.legend(); save('01_landau_spectrum.pdf')
plt.figure(); plt.plot(B,[magnetic_length(b) for b in B]); plt.xlabel('B'); plt.ylabel('l_B'); save('02_magnetic_length.pdf')
plt.figure(); X=guiding_centers(10,20,2); plt.vlines(X,0,1); plt.xlim(0,10); plt.yticks([]); plt.xlabel('guiding-center X'); save('03_guiding_centers.pdf')
x=np.linspace(-6,6,600); plt.figure();
for n in range(3): plt.plot(x,landau_gauge_orbital(n,x),label=f'n={n}')
plt.xlabel('x/l_B'); plt.ylabel('phi_n'); plt.legend(); save('04_landau_gauge_orbitals.pdf')
r=np.linspace(0,8,600); plt.figure();
for k in [0,1,3,6]: plt.plot(r,lll_radial_probability(k,r),label=f'k={k}')
plt.xlabel('r/l_B'); plt.ylabel('radial probability'); plt.legend(); save('05_lll_radial_orbitals.pdf')
plt.figure(); A=np.linspace(0,20,100); plt.plot(A,[flux_degeneracy(a,2) for a in A]); plt.xlabel('area'); plt.ylabel('N_Phi'); save('06_flux_degeneracy.pdf')
plt.figure(); plt.plot(B,[filling_factor(1,b) for b in B]); plt.xlabel('B'); plt.ylabel('nu'); save('07_filling_factor.pdf')
plt.figure();
for s in [-1,1]: plt.plot(B,[spin_resolved_energy(0,s,b,g=.4,muB=.5) for b in B],label=f'sigma={s}')
plt.xlabel('B'); plt.ylabel('E_0,sigma'); plt.legend(); save('08_spin_splitting.pdf')
E=np.linspace(0,8,1000); levels=[landau_energy(n,1) for n in range(7)]; plt.figure(); plt.plot(E,gaussian_broadened_dos(E,levels,.12)); plt.xlabel('E'); plt.ylabel('DOS'); save('09_broadened_dos.pdf')
