from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from chern_invariants_companion import *

OUT=Path(__file__).resolve().parents[3]/'generated/ch43/computational'; OUT.mkdir(parents=True,exist_ok=True)

def save(name):
    plt.tight_layout(); plt.savefig(OUT/name); plt.close()

# 1 closed-sphere curvature/flux density
th=np.linspace(0,np.pi,500)
plt.figure(figsize=(4.6,3.1)); plt.plot(th,sphere_lower_curvature(th)); plt.xlabel(r'$\theta$'); plt.ylabel('Berry curvature F_theta_phi'); plt.title('Sphere Berry curvature'); save('01_sphere_curvature.pdf')
# 2 transition winding
ph=np.linspace(0,2*np.pi,500)
plt.figure(figsize=(4.6,3.1));
for n in (-1,1,2): plt.plot(ph/np.pi,transition_phase(ph,n)/(2*np.pi),label=f'w={n}')
plt.xlabel(r'$\phi/\pi$'); plt.ylabel(r'$\chi/(2\pi)$'); plt.title('Transition-function winding'); plt.legend(); save('02_patch_winding.pdf')
# 3 degree density
plt.figure(figsize=(4.6,3.1));
for n in (1,2,3): plt.plot(th,degree_density(th,n),label=f'degree {n}')
plt.xlabel(r'$\theta$'); plt.ylabel('integrated degree density'); plt.title('Degree-map density'); plt.legend(); save('03_degree_density.pdf')
# 4 regularized Dirac curvature
k=np.linspace(0,5,700)
plt.figure(figsize=(4.6,3.1));
for m in (-1,0.35,1): plt.plot(k,regularized_dirac_curvature(k,0,m,1),label=f'm={m:g}')
plt.xlabel(r'$|k|$'); plt.ylabel(r'$\Omega_-(k)$'); plt.title('Regularized Dirac curvature'); plt.legend(); save('04_regularized_dirac_curvature.pdf')
# 5 Chern transition and gap
m=np.linspace(-2,2,401); c=np.array([regularized_dirac_chern_exact(x,1) if abs(x)>1e-12 else np.nan for x in m]); gap=2*np.abs(m)
plt.figure(figsize=(4.6,3.1)); plt.plot(m,c,label=r'$C_-$'); plt.plot(m,gap/np.max(gap),label='gap / max gap'); plt.xlabel('mass'); plt.title('Gap closing permits Chern transfer'); plt.legend(); save('05_chern_transition.pdf')
# 6 finite cutoff convergence
K=np.linspace(1.5,25,90); vals=[regularized_dirac_chern_numeric(1,1,x,5001) for x in K]
plt.figure(figsize=(4.6,3.1)); plt.plot(K,vals); plt.axhline(1,linestyle='--'); plt.xlabel(r'$k_{\max}$'); plt.ylabel('integrated Chern estimate'); plt.title('Ultraviolet convergence'); save('06_uv_convergence.pdf')
# 7 gauge-invariant plaquette phase under random rephasings
u00=np.array([1,0],complex); u10=np.array([1,1],complex)/np.sqrt(2); u11=np.array([1,1j],complex)/np.sqrt(2); u01=np.array([1,.5j],complex)/np.sqrt(1.25)
rng=np.random.default_rng(7); trials=np.arange(80); vals=[]
for _ in trials:
    a=rng.uniform(-np.pi,np.pi,4); vals.append(plaquette_phase(gauge_rephase(u00,a[0]),gauge_rephase(u10,a[1]),gauge_rephase(u11,a[2]),gauge_rephase(u01,a[3])))
plt.figure(figsize=(4.6,3.1)); plt.plot(trials,vals,'.'); plt.xlabel('random gauge trial'); plt.ylabel('plaquette phase'); plt.title('Link-product gauge invariance'); save('07_link_gauge_invariance.pdf')
# 8 TKNN response values
Cs=np.arange(-3,4); plt.figure(figsize=(4.6,3.1)); plt.step(Cs,[hall_sigma_yx(x) for x in Cs],where='mid'); plt.xlabel('occupied Chern number'); plt.ylabel(r'$\sigma_{yx}/(e^2/h)$'); plt.title('TKNN response'); save('08_tknn_response.pdf')
# 9 pump accumulation with nonuniform local density but unit integral
x=np.linspace(0,1,800); dens=1+0.55*np.sin(2*np.pi*x); q=cumulative_pump_from_density(x,dens)
plt.figure(figsize=(4.6,3.1)); plt.plot(x,q,label='pumped number'); plt.plot(x,dens,label='instantaneous density'); plt.xlabel('cycle fraction'); plt.title('Chern pump: local rate, integer cycle'); plt.legend(); save('09_pump_cycle.pdf')
print('generated',len(list(OUT.glob('*.pdf'))),'figures in',OUT)
