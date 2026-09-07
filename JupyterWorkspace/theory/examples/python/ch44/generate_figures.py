from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from haldane_model_companion import *

OUT=Path(__file__).resolve().parents[3]/'generated/ch44/computational'; OUT.mkdir(parents=True,exist_ok=True)
for p in OUT.glob('*.pdf'): p.unlink()

def save(name):
    plt.tight_layout(); plt.savefig(OUT/name); plt.close()

# 1 phase diagram from analytic valley masses
phis=np.linspace(-np.pi,np.pi,241); Ms=np.linspace(-1.2,1.2,221); Z=np.empty((len(Ms),len(phis)))
for i,M in enumerate(Ms):
    for j,ph in enumerate(phis):
        c=chern_from_masses(M,.2,ph,tol=1e-8); Z[i,j]=0 if np.isnan(c) else c
plt.figure(figsize=(4.8,3.2)); plt.imshow(Z,origin='lower',aspect='auto',extent=[-1,1,Ms[0],Ms[-1]],vmin=-1,vmax=1); plt.xlabel(r'$\phi/\pi$'); plt.ylabel(r'$M/t_1$'); plt.title('Haldane Chern phase diagram'); save('01_phase_diagram.pdf')

# 2 Berry-curvature hot spots on reciprocal primitive torus
n=75; u=np.linspace(0,1,n,endpoint=False); cur=np.empty((n,n))
for i,a in enumerate(u):
    for j,b in enumerate(u): cur[j,i]=berry_curvature_uv(a,b,t2=.15,phi=np.pi/2,M=0)
plt.figure(figsize=(4.4,3.4)); plt.imshow(cur,origin='lower',extent=[0,1,0,1],aspect='equal'); plt.xlabel('u'); plt.ylabel('v'); plt.title('Occupied-band Berry curvature'); save('02_berry_curvature.pdf')

# 3 Fukui mesh convergence and random-gauge invariance
meshes=np.array([9,12,15,18,24,30]); clean=np.array([chern_fukui(int(m)) for m in meshes]); gauged=np.array([chern_fukui(int(m),random_gauge_seed=11) for m in meshes])
plt.figure(figsize=(4.6,3.1)); plt.plot(meshes,clean,'o-',label='native gauge'); plt.plot(meshes,gauged,'x--',label='random local phases'); plt.axhline(1,linestyle=':'); plt.xlabel('mesh n'); plt.ylabel('Chern estimate'); plt.title('Gauge-stable Chern convergence'); plt.legend(); save('03_chern_convergence.pdf')

# 4 direct and indirect gaps across a mass sweep
Mgrid=np.linspace(-1.25,1.25,101); dg=[]; ig=[]
for m in Mgrid:
    a,b=gap_scan(24,t2=.15,phi=np.pi/2,M=m); dg.append(a); ig.append(b)
plt.figure(figsize=(4.6,3.1)); plt.plot(Mgrid,dg,label='direct gap'); plt.plot(Mgrid,ig,label='indirect gap'); plt.axhline(0,linestyle=':'); plt.xlabel('M'); plt.ylabel('energy gap'); plt.title('Gap closing and global insulation'); plt.legend(); save('04_gap_scan.pdf')

# 5 controlled ribbon spectral-flow cartoon from continuum edge dispersions
k=np.linspace(-1,1,500); plt.figure(figsize=(4.6,3.1)); plt.fill_between(k,-1.4,-.8,alpha=.18,label='projected bulk'); plt.fill_between(k,.8,1.4,alpha=.18); plt.plot(k,edge_dispersion(k,.95,1),label='edge A'); plt.plot(k,edge_dispersion(k,.95,-1),label='edge B'); plt.ylim(-1.5,1.5); plt.xlabel(r'$k_\parallel$'); plt.ylabel('energy'); plt.title('Chiral ribbon spectral flow'); plt.legend(); save('05_edge_spectral_flow.pdf')

# 6 domain-wall bound-state probability
y=np.linspace(-8,8,1200); p=domain_wall_profile(y,m0=1,lam=1.2); plt.figure(figsize=(4.6,3.1)); plt.plot(y,p); plt.xlabel('transverse coordinate'); plt.ylabel(r'$|\psi_0|^2$'); plt.title('Dirac mass-domain-wall mode'); save('06_domain_wall_profile.pdf')

# 7 finite-width hybridization
W=np.linspace(2,25,250); plt.figure(figsize=(4.6,3.1)); plt.semilogy(W,finite_width_gap(W,xi=3,gap0=1)); plt.xlabel(r'$W/a$'); plt.ylabel('finite-size edge gap'); plt.title('Exponential opposite-edge hybridization'); save('07_finite_width_gap.pdf')

# 8 local-marker acceptance morphology
x=np.linspace(0,100,800); c=local_marker_profile(x,100,C=1,xi=6); plt.figure(figsize=(4.6,3.1)); plt.plot(x,c); plt.axhline(1,linestyle=':'); plt.xlabel('position across open sample'); plt.ylabel('coarse-grained marker'); plt.title('Interior local-Chern plateau morphology'); save('08_local_marker_profile.pdf')

# 9 direct-gap-positive but indirect-overlap example
vals=[]
for ph in np.linspace(.08,.7,90):
    d,ind=gap_scan(24,t2=.4,phi=ph,M=0); vals.append((ph,d,ind))
vals=np.array(vals); plt.figure(figsize=(4.6,3.1)); plt.plot(vals[:,0],vals[:,1],label='direct gap'); plt.plot(vals[:,0],vals[:,2],label='indirect gap'); plt.axhline(0,linestyle=':'); plt.xlabel(r'$\phi$'); plt.ylabel('gap'); plt.title('Chern band versus metallic overlap'); plt.legend(); save('09_indirect_overlap.pdf')
print('generated',len(list(OUT.glob('*.pdf'))),'figures in',OUT)
