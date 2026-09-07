from pathlib import Path
import math
import numpy as np
import matplotlib.pyplot as plt
from berry_geometry_companion import *

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'generated/ch42/computational'; OUT.mkdir(parents=True,exist_ok=True)

def save(name):
    plt.tight_layout(); plt.savefig(OUT/name); plt.close()

# 1 spin-half phase
th=np.linspace(0,math.pi,300)
plt.figure(figsize=(4.6,3.2)); plt.plot(th/math.pi,[spin_half_berry_phase(x,+1)/math.pi for x in th],label='upper'); plt.plot(th/math.pi,[spin_half_berry_phase(x,-1)/math.pi for x in th],label='lower'); plt.xlabel(r'$\theta/\pi$'); plt.ylabel(r'$\gamma/\pi$'); plt.title('Spin-1/2 geometric phase'); plt.legend(); save('01_spin_half_phase.pdf')
# 2 Dirac curvature slice
k=np.linspace(-3,3,400)
plt.figure(figsize=(4.6,3.2)); plt.plot(k,massive_dirac_curvature(k,0,1,-1),label='m=+1'); plt.plot(k,massive_dirac_curvature(k,0,-1,-1),label='m=-1'); plt.xlabel(r'$k_x$'); plt.ylabel(r'$\mathcal{F}_{k_xk_y}$'); plt.title('Massive Dirac curvature hot spot'); plt.legend(); save('02_dirac_curvature.pdf')
# 3 anomalous velocity
F=np.linspace(-2,2,200)
plt.figure(figsize=(4.6,3.2)); plt.plot(F,anomalous_velocity_y(F,.5),label=r'$\Omega_z=+0.5$'); plt.plot(F,anomalous_velocity_y(F,-.5),label=r'$\Omega_z=-0.5$'); plt.xlabel(r'$F_x$'); plt.ylabel(r'$v_y^{\rm anom}$'); plt.title('Anomalous transverse velocity'); plt.legend(); save('03_anomalous_velocity.pdf')
# 4 SSH Zak phase across ratio away from transition
rat=np.r_[np.linspace(.15,.92,45),np.linspace(1.08,1.85,45)]
gam=np.array([abs(ssh_zak_phase(r,1,241))/math.pi for r in rat])
plt.figure(figsize=(4.6,3.2)); plt.plot(rat,gam,'.-'); plt.axvline(1,ls='--'); plt.xlabel(r'$v/w$'); plt.ylabel(r'$|\gamma_{Zak}|/\pi$'); plt.title('Gauge-invariant SSH Zak phase'); save('04_ssh_zak_phase.pdf')
# 5 polarization winding
u=np.linspace(0,1,250); P=polarization_pump_branch(u,1)
plt.figure(figsize=(4.6,3.2)); plt.plot(u,P,label='unwrapped branch'); plt.plot(u,((P+.5)%1)-.5,label='modulo polarization quantum'); plt.xlabel('cycle parameter'); plt.ylabel(r'$P/e$'); plt.title('Adiabatic pump polarization winding'); plt.legend(); save('05_polarization_pump.pdf')
# 6 discrete Berry link convergence
Ns=np.array([12,20,32,48,72,108,160,240]); err=[]
for n in Ns: err.append(abs(abs(ssh_zak_phase(.5,1,int(n)))-math.pi))
plt.figure(figsize=(4.6,3.2)); plt.loglog(Ns,np.maximum(err,1e-16),'o-'); plt.xlabel('k-grid points'); plt.ylabel('phase error'); plt.title('Discrete link-variable convergence'); save('06_link_convergence.pdf')
# 7 Wilson phases
lam=np.linspace(0,1,200); p1=[];p2=[]
for x in lam:
    W=unitary_from_hermitian_connection(np.diag([x,-x]),math.pi/2); p=wilson_eigenphases(W); p1.append(p[0]);p2.append(p[1])
plt.figure(figsize=(4.6,3.2)); plt.plot(lam,p1,label=r'$\vartheta_1$'); plt.plot(lam,p2,label=r'$\vartheta_2$'); plt.xlabel(r'$\lambda$'); plt.ylabel('Wilson phase'); plt.title('Non-Abelian Wilson-loop spectrum'); plt.legend(); save('07_wilson_spectrum.pdf')
# 8 quantum metric sphere
plt.figure(figsize=(4.6,3.2)); plt.plot(th/math.pi,[quantum_metric_sphere(x)[0,0] for x in th],label=r'$g_{\theta\theta}$'); plt.plot(th/math.pi,[quantum_metric_sphere(x)[1,1] for x in th],label=r'$g_{\phi\phi}$'); plt.xlabel(r'$\theta/\pi$'); plt.ylabel('metric component'); plt.title('Two-level quantum metric'); plt.legend(); save('08_quantum_metric.pdf')
# 9 geometry identity
D=np.array([np.linalg.det(quantum_metric_sphere(x)) for x in th]); F2=np.array([berry_curvature_sphere(x,-1)**2/4 for x in th])
plt.figure(figsize=(4.6,3.2)); plt.plot(th/math.pi,D,label=r'$\det g$'); plt.plot(th/math.pi,F2,'--',label=r'$\mathcal{F}^2/4$'); plt.xlabel(r'$\theta/\pi$'); plt.ylabel('geometric density'); plt.title('Metric-curvature equality for a two-level ray'); plt.legend(); save('09_metric_curvature_identity.pdf')
print(f'generated {len(list(OUT.glob("*.pdf")))} figures in {OUT}')
