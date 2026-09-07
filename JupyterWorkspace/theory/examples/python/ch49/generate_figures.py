from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from correlated_matter_companion import *
OUT=Path(__file__).resolve().parents[3]/'generated/ch49/computational'; OUT.mkdir(parents=True,exist_ok=True)
for p in OUT.glob('*.pdf'): p.unlink()
def save(name):
    plt.tight_layout(); plt.savefig(OUT/name); plt.close()

# 1 finite-size crossing with irrelevant correction
d=np.linspace(-.08,.08,300); plt.figure(figsize=(4.6,3))
for L in (8,16,32,64): plt.plot(d,correction_aware_observable(d,L,.7,1.0),label=f'L={L}')
plt.xlabel('delta'); plt.ylabel('dimensionless R'); plt.title('Correction-aware finite-size crossing'); plt.legend(); save('01_finite_size_scaling.pdf')

# 2 linearized RG flow
ell=np.linspace(0,3,250); plt.figure(figsize=(4.6,3))
for y in (-1.,0.,1.): plt.plot(ell,linear_rg_flow(.15,y,ell),label=f'y={y:g}')
plt.xlabel('RG scale ell'); plt.ylabel('coupling u'); plt.title('Linearized RG trajectories'); plt.legend(); save('02_rg_flow.pdf')

# 3 Green-function conditioning across a pole/zero-like parameter
m=np.linspace(-2,2,500); cond=[]
for x in m:
    g=np.diag([1/(x+1j*.08),1/(2+x*x)]); cond.append(inverse_condition_number(g))
plt.figure(figsize=(4.6,3)); plt.plot(m,cond); plt.xlabel('control parameter'); plt.ylabel('inverse condition number'); plt.title('Green-function singularity diagnostic'); save('03_green_pole_zero.pdf')

# 4 Wilson area law
area=np.linspace(0,12,300); plt.figure(figsize=(4.6,3))
for s in (.08,.2,.4): plt.plot(area,area_law_wilson(area,s),label=f'sigma={s:g}')
plt.xlabel('loop area'); plt.ylabel('<W(C)>'); plt.title('Z2 Wilson-loop area law'); plt.legend(); save('04_z2_wilson_area_law.pdf')

# 5 apparent critical crossing drift
plt.figure(figsize=(4.6,3))
for L in (8,12,20,32): plt.plot(d,correction_aware_observable(d,L,.75,.65,.35),label=f'L={L}')
plt.xlabel('delta'); plt.ylabel('R'); plt.title('Finite-size drift near deconfined criticality'); plt.legend(); save('05_dqcp_crossing_drift.pdf')

# 6 non-Fermi-liquid self energy
w=np.logspace(-5,0,300); plt.figure(figsize=(4.6,3)); plt.loglog(w,-nonfermi_self_energy(w).imag,label='|Im Sigma| ~ omega^(2/3)'); plt.loglog(w,w,'--',label='omega'); plt.xlabel('omega'); plt.ylabel('energy scale'); plt.title('Quasiparticle breakdown benchmark'); plt.legend(); save('06_nonfermi_self_energy.pdf')

# 7 omega/T collapse
x=np.linspace(-5,5,400); plt.figure(figsize=(4.6,3))
for T in (1.,2.,4.):
    w=x*T; scaled=T**.5*omega_t_response(w,T,.5); plt.plot(x,scaled,label=f'T={T:g}')
plt.xlabel('omega/T'); plt.ylabel('T^x chi'); plt.title('Synthetic omega/T collapse'); plt.legend(); save('07_omega_T_collapse.pdf')

# 8 nodal gap
th=np.linspace(0,2*np.pi,500); plt.figure(figsize=(4.6,3)); plt.plot(th,nodal_gap(th)); plt.axhline(0,linestyle=':'); plt.xlabel('Fermi-surface angle'); plt.ylabel('Delta(theta)/Delta0'); plt.title('d-wave nodal gap'); save('08_nodal_gap.pdf')

# 9 Floquet prethermal timescale
ratio=np.linspace(.5,8,300); tau=np.array([floquet_prethermal_time(r,1) for r in ratio]); plt.figure(figsize=(4.6,3)); plt.semilogy(ratio,tau); plt.xlabel('drive frequency / local scale'); plt.ylabel('prethermal time (arb.)'); plt.title('Floquet prethermal timescale'); save('09_floquet_prethermal_time.pdf')
print('generated',len(list(OUT.glob('*.pdf'))),'figures in',OUT)
