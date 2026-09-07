from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from hall_experiments_metrology_companion import *
OUT=Path(__file__).resolve().parents[3]/'generated/ch41/computational'; OUT.mkdir(parents=True,exist_ok=True)
def save(name):
    plt.tight_layout(); plt.savefig(OUT/name,format='pdf'); plt.close()
# 1 integer Hall resistance hierarchy
i=np.arange(1,9); plt.figure(); plt.plot(i,[hall_plateau_resistance(x)/1e3 for x in i],marker='o'); plt.xlabel('plateau index i'); plt.ylabel('R_H (kOhm)'); save('01_hall_resistance_hierarchy.pdf')
# 2 tensor inversion near plateau
rxx=np.logspace(-3,2,250); ryx=hall_plateau_resistance(2); sxx,sxy=conductivity_from_resistivity(rxx,ryx); plt.figure(); plt.loglog(rxx,np.abs(sxx)*R_K,label='|sigma_xx| R_K'); plt.loglog(rxx,np.abs(sxy)*R_K,label='|sigma_xy| R_K'); plt.xlabel('rho_xx (Ohm)'); plt.ylabel('dimensionless conductivity'); plt.legend(); save('02_tensor_inversion.pdf')
# 3 metrology relative deviation
delta=np.linspace(-1e-7,1e-7,201); plt.figure(); plt.plot(delta*1e9, hall_plateau_resistance(2)*(1+delta)-hall_plateau_resistance(2)); plt.xlabel('relative deviation (ppb)'); plt.ylabel('absolute deviation (Ohm)'); save('03_metrology_deviation.pdf')
# 4 shot noise charge slopes
I=np.linspace(0,3e-9,150); plt.figure();
for frac in [1,1/3,1/4]: plt.plot(I*1e9,[poisson_shot_noise(E_EXACT*frac,x)*1e28 for x in I],label=f'e*={frac:g}e')
plt.xlabel('I_B (nA)'); plt.ylabel('S_I (1e-28 A^2/Hz)'); plt.legend(); save('04_shot_noise_charge.pdf')
# 5 finite-temperature noise crossover
V=np.linspace(0,80e-6,180); plt.figure();
for T in [.02,.04,.08]: plt.plot(V*1e6,[finite_temperature_excess_noise(E_EXACT/3,x,T,1e-7)*1e28 for x in V],label=f'{T*1e3:.0f} mK')
plt.xlabel('bias (microV)'); plt.ylabel('excess noise (1e-28 A^2/Hz)'); plt.legend(); save('05_finite_temperature_noise.pdf')
# 6 interferometer phase
phi=np.linspace(0,4,250); plt.figure(); plt.plot(phi,[interferometer_phase(1/3,x)%(2*np.pi) for x in phi],label='AB only'); plt.plot(phi,[(interferometer_phase(1/3,x,2*np.pi/3))%(2*np.pi) for x in phi],label='+ one braid phase'); plt.xlabel('flux / Phi0'); plt.ylabel('phase mod 2pi'); plt.legend(); save('06_interferometer_phase.pdf')
# 7 visibility/dephasing
x=np.linspace(0,5,200); plt.figure(); plt.plot(x,[visibility_ratio(v,1) for v in x]); plt.xlabel('L / L_phi'); plt.ylabel('visibility / V0'); save('07_visibility_dephasing.pdf')
# 8 thermal Hall benchmark candidates
names=['anti-Pf','PH-Pf','Pf']; vals=[five_halves_thermal_ratio('anti-Pfaffian'),five_halves_thermal_ratio('PH-Pfaffian'),five_halves_thermal_ratio('Pfaffian')]; plt.figure(); plt.bar(np.arange(3),vals); plt.xticks(np.arange(3),names); plt.ylabel('kappa_xy / (kappa0 T)'); save('08_thermal_hall_candidates.pdf')
# 9 equilibration approach
x=np.linspace(0,5,200); plt.figure(); plt.plot(x,[equilibration_fraction(v,1) for v in x]); plt.xlabel('L / ell_eq'); plt.ylabel('equilibrated fraction'); save('09_equilibration_fraction.pdf')
