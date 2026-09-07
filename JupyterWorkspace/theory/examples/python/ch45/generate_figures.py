from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from topological_insulators_companion import *
OUT=Path(__file__).resolve().parents[3]/'generated/ch45/computational'; OUT.mkdir(parents=True,exist_ok=True)
for p in OUT.glob('*.pdf'): p.unlink()
def save(n): plt.tight_layout(); plt.savefig(OUT/n); plt.close()
# 1 parity/Z2 phase diagram
m=np.linspace(-3.5,3.5,500); z=np.array([np.nan if parity_z2(x) is None else parity_z2(x) for x in m]); plt.figure(figsize=(4.6,3.0)); plt.plot(m,z); plt.ylim(-.15,1.15); plt.xlabel('lattice mass m'); plt.ylabel(r'$\nu$'); plt.title('Spinful lattice Z2 phase sectors'); save('01_z2_phase_diagram.pdf')
# 2 bulk gap sweep
mg=np.linspace(-3,3,121); gap=np.array([bulk_gap(28,m=x) for x in mg]); plt.figure(figsize=(4.6,3.0)); plt.plot(mg,gap); plt.xlabel('m'); plt.ylabel('direct bulk gap'); plt.title('Bulk gap closings at topological boundaries'); save('02_bulk_gap_scan.pdf')
# 3 spin-block Chern convergence
meshes=np.array([9,12,15,18,24,30]); c=np.array([spin_block_chern(int(n),-1) for n in meshes]); cg=np.array([spin_block_chern(int(n),-1,random_gauge_seed=11) for n in meshes]); plt.figure(figsize=(4.6,3.0)); plt.plot(meshes,c,'o-',label='native'); plt.plot(meshes,cg,'x--',label='random gauge'); plt.xlabel('mesh n'); plt.ylabel(r'$C_\uparrow$'); plt.title('Gauge-stable spin-block Chern parity'); plt.legend(); save('03_spin_chern_convergence.pdf')
# 4 Wilson eigenphase flow
ky=np.linspace(0,np.pi,101); phases=np.array([wilson_phases(y,70,m=-1) for y in ky]); un=np.unwrap(phases,axis=0); plt.figure(figsize=(4.6,3.1)); plt.plot(ky/np.pi,un[:,0]/(2*np.pi)); plt.plot(ky/np.pi,un[:,1]/(2*np.pi)); plt.xlabel(r'$k_y/\pi$'); plt.ylabel(r'Wilson phase / $2\pi$'); plt.title('Occupied Wilson-loop spectrum'); save('04_wilson_flow.pdf')
# 5 finite width edge gap
W=np.linspace(2,30,250); plt.figure(figsize=(4.6,3.0)); plt.semilogy(W,finite_size_gap(W,3)); plt.xlabel('width / thickness'); plt.ylabel('hybridization gap'); plt.title('Opposite-boundary hybridization'); save('05_finite_size_gap.pdf')
# 6 helical edge spectrum with and without hybridization
k=np.linspace(-1,1,400); e0=helical_edge_energies(k,1,0); e1=helical_edge_energies(k,1,.15); plt.figure(figsize=(4.6,3.0)); plt.plot(k,e0[:,0],label='wide edge'); plt.plot(k,e0[:,1]); plt.plot(k,e1[:,0],'--',label='finite-width'); plt.plot(k,e1[:,1],'--'); plt.xlabel('k'); plt.ylabel('E'); plt.title('Helical edge and finite-size gap'); plt.legend(); save('06_helical_edge_spectrum.pdf')
# 7 surface Dirac cone line cut
kx=np.linspace(-1,1,400); e0=surface_dirac_energies(kx,0,mass=0); em=surface_dirac_energies(kx,0,mass=.25); plt.figure(figsize=(4.6,3.0)); plt.plot(kx,e0[:,0]); plt.plot(kx,e0[:,1],label='TR surface'); plt.plot(kx,em[:,0],'--'); plt.plot(kx,em[:,1],'--',label='magnetic mass'); plt.xlabel(r'$k_x$'); plt.ylabel('E'); plt.title('Surface Dirac cone and magnetic gap'); plt.legend(); save('07_surface_dirac_gap.pdf')
# 8 spin-momentum locking arrows
ang=np.linspace(0,2*np.pi,17)[:-1]; x=np.cos(ang); y=np.sin(ang); u=-np.sin(ang); v=np.cos(ang); plt.figure(figsize=(3.8,3.8)); plt.plot(np.cos(np.linspace(0,2*np.pi,300)),np.sin(np.linspace(0,2*np.pi,300))); plt.quiver(x,y,u,v,angles='xy',scale_units='xy',scale=4); plt.axis('equal'); plt.xlabel(r'$k_x$'); plt.ylabel(r'$k_y$'); plt.title('Surface spin-momentum locking'); save('08_surface_spin_texture.pdf')
# 9 surface vs bulk scaling acceptance model
t=np.linspace(0,30,200); g=conductance_channels(t,2,.08); plt.figure(figsize=(4.6,3.0)); plt.plot(t,g,label='total'); plt.axhline(2,linestyle=':',label='two-surface term'); plt.xlabel('sample thickness'); plt.ylabel('sheet conductance (arb.)'); plt.title('Surface-bulk transport separation'); plt.legend(); save('09_surface_bulk_scaling.pdf')
print('generated',len(list(OUT.glob('*.pdf'))),'figures in',OUT)
