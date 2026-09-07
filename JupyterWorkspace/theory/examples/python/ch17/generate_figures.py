from pathlib import Path
import json
import numpy as np
import matplotlib.pyplot as plt
from waves_radiation_companion import (
 C0, array_factor, dipole_power_pattern, dipole_solid_angle_integral,
 effective_aperture, friis_received_power, gaussian_pulse,
 half_wave_power_pattern, hertzian_radiation_resistance, zone_terms)
ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'generated/ch17/computational'; OUT.mkdir(parents=True,exist_ok=True)

def save(name):
    plt.tight_layout(); plt.savefig(OUT/name,bbox_inches='tight'); plt.close()

# 1 causal pulse
t=np.linspace(-1,8,1600)*1e-6; delay=3e-6
plt.figure(); plt.plot(t*1e6,gaussian_pulse(t,0,0.45e-6,2e6),label='source')
plt.plot(t*1e6,gaussian_pulse(t-delay,0,0.45e-6,2e6),label='observed')
plt.xlabel('time (microseconds)'); plt.ylabel('normalized field'); plt.legend(); plt.grid(True); save('retarded_pulse.pdf')

# 2 zone scaling
x=np.logspace(-2,2,500); near=[]; ind=[]; rad=[]
for q in x:
    a,b,c=zone_terms(1.0,q); scale=a+b+c; near.append(a/scale); ind.append(b/scale); rad.append(c/scale)
plt.figure(); plt.semilogx(x,near,label='near 1/r^3'); plt.semilogx(x,ind,label='induction 1/r^2'); plt.semilogx(x,rad,label='radiation 1/r')
plt.xlabel('kr'); plt.ylabel('fraction of summed magnitude'); plt.legend(); plt.grid(True); save('near_far_scaling.pdf')

# 3 dipole polar pattern
th=np.linspace(0,2*np.pi,720); ax=plt.figure().add_subplot(111,projection='polar'); ax.plot(th,dipole_power_pattern(th)); ax.set_title('normalized dipole power'); plt.savefig(OUT/'dipole_pattern.pdf',bbox_inches='tight'); plt.close()

# 4 angular convergence
ns=np.array([11,21,41,81,161,321,641,1281]); exact=8*np.pi/3; errs=np.array([abs(dipole_solid_angle_integral(int(n))-exact) for n in ns])
plt.figure(); plt.loglog(ns,errs,'o-'); plt.xlabel('theta samples'); plt.ylabel('absolute integral error'); plt.grid(True); save('angular_convergence.pdf')

# 5 antenna current distributions
z=np.linspace(-.5,.5,500); plt.figure(); plt.plot(z,np.ones_like(z),label='Hertzian idealization'); plt.plot(z,np.cos(np.pi*z),label='half-wave approximation'); plt.xlabel('normalized axial coordinate z/L'); plt.ylabel('normalized current'); plt.legend(); plt.grid(True); save('antenna_current.pdf')

# 6 radiation resistance
ratio=np.linspace(.002,.1,400); rr=np.array([hertzian_radiation_resistance(x,1.0) for x in ratio]); plt.figure(); plt.plot(ratio,rr); plt.xlabel('electrical length l/lambda'); plt.ylabel('radiation resistance (ohm)'); plt.grid(True); save('radiation_resistance.pdf')

# 7 array factors
th=np.linspace(0,np.pi,1000); plt.figure();
for n in [2,4,8]: plt.plot(np.degrees(th),array_factor(th,n,.5,1.0),label=f'N={n}')
plt.xlabel('theta (degrees from array axis)'); plt.ylabel('normalized power factor'); plt.legend(); plt.grid(True); save('array_factor.pdf')

# 8 effective aperture
gain=np.linspace(1,20,300); plt.figure();
for lam in [.1,.3,1.0]: plt.plot(gain,[effective_aperture(g,lam) for g in gain],label=f'lambda={lam:g} m')
plt.xlabel('gain'); plt.ylabel('maximum effective aperture (m^2)'); plt.legend(); plt.grid(True); save('effective_aperture.pdf')

# 9 Friis
r=np.logspace(0,4,500); plt.figure();
for lam in [.03,.1,.3]: plt.loglog(r,[friis_received_power(1,2,2,lam,x) for x in r],label=f'lambda={lam:g} m')
plt.xlabel('range (m)'); plt.ylabel('received power for Pt=1 W'); plt.legend(); plt.grid(True); save('friis_link.pdf')

summary={
 'retarded_delay_s':delay,
 'dipole_solid_angle_integral':dipole_solid_angle_integral(4001),
 'dipole_solid_angle_exact':float(8*np.pi/3),
 'short_element_resistance_ell_over_lambda_0p02_ohm':hertzian_radiation_resistance(.02,1),
 'friis_example_w':friis_received_power(1,2,2,.125,100),
 'figures':9,
}
(OUT/'companion_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
