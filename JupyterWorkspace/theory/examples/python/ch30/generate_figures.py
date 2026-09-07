from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from approximation_companion import *
OUT=Path(__file__).resolve().parents[3]/'generated/ch30/computational'; OUT.mkdir(parents=True,exist_ok=True)
def save(name): plt.tight_layout(); plt.savefig(OUT/name); plt.close()
# 1 perturbative comparison
l=np.linspace(-.7,.7,200); exact=np.array([exact_eigenvalues([0,2],[[0,1],[1,0]],x)[0] for x in l]); pert=-l*l/2
plt.figure(); plt.plot(l,exact,label='exact'); plt.plot(l,pert,'--',label='second order'); plt.xlabel('coupling'); plt.ylabel('ground energy'); plt.legend(); save('perturbation_energy_comparison.pdf')
# 2 avoided crossing
x=np.linspace(-3,3,240); vals=np.array([np.linalg.eigvalsh([[q/2,.4],[.4,-q/2]]) for q in x]); plt.figure(); plt.plot(x,vals[:,0]); plt.plot(x,vals[:,1]); plt.xlabel('detuning'); plt.ylabel('energy'); save('avoided_crossing_spectrum.pdf')
# 3 variational quartic
a=np.linspace(.25,2.5,250); plt.figure(); plt.plot(a,gaussian_quartic_energy(a,.2)); plt.xlabel('Gaussian width parameter'); plt.ylabel('variational energy'); save('variational_quartic_landscape.pdf')
# 4 pulse line
D=np.linspace(-12,12,400); plt.figure(); plt.plot(D,rectangular_pulse_probability(D,.1,4)); plt.xlabel('detuning'); plt.ylabel('first-order probability'); save('finite_pulse_spectrum.pdf')
# 5 Rabi
t=np.linspace(0,12,300); plt.figure(); plt.plot(t,rabi_probability(0,1,t),label='resonant'); plt.plot(t,rabi_probability(1,1,t),label='detuned'); plt.xlabel('time'); plt.ylabel('excited probability'); plt.legend(); save('rabi_dynamics.pdf')
# 6 golden rule
rho=np.linspace(0,3,100); plt.figure(); plt.plot(rho,[golden_rule_rate(.2,r) for r in rho]); plt.xlabel('density of states'); plt.ylabel('transition rate'); save('golden_rule_density.pdf')
# 7 LZ
v=np.logspace(-2,1,200); plt.figure(); plt.semilogx(v,[landau_zener_diabatic_probability(.3,q) for q in v]); plt.xlabel('sweep rate'); plt.ylabel('diabatic probability'); save('landau_zener_probability.pdf')
# 8 WKB
width=np.linspace(0,5,160); plt.figure(); plt.semilogy(width,[wkb_transmission(2,1,q) for q in width]); plt.xlabel('barrier width'); plt.ylabel('transmission'); save('wkb_transmission.pdf')
# 9 BS
n=np.arange(8); plt.figure(); plt.plot(n,[bohr_sommerfeld_harmonic(int(q)) for q in n],'o-'); plt.xlabel('n'); plt.ylabel('semiclassical energy'); save('bohr_sommerfeld_levels.pdf')
