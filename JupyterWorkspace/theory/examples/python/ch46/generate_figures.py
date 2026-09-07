from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from topological_superconductors_companion import *
OUT=Path(__file__).resolve().parents[3]/'generated/ch46/computational'; OUT.mkdir(parents=True,exist_ok=True)
for p in OUT.glob('*.pdf'): p.unlink()
def save(n): plt.tight_layout(); plt.savefig(OUT/n); plt.close()
# 1 uniform BdG spectrum
xi=np.linspace(-2,2,400); e=uniform_bdg_spectrum(xi,.5); plt.figure(figsize=(4.6,3)); plt.plot(xi,e[:,0]); plt.plot(xi,e[:,1]); plt.xlabel(r'$\xi$'); plt.ylabel('E'); plt.title('Uniform BdG quasiparticle gap'); save('01_uniform_bdg_spectrum.pdf')
# 2 Kitaev phase and bulk gap
mu=np.linspace(-3,3,301); gap=np.array([kitaev_bulk_gap(x,n=501) for x in mu]); plt.figure(figsize=(4.6,3)); plt.plot(mu,gap); plt.axvline(-2,linestyle=':'); plt.axvline(2,linestyle=':'); plt.xlabel(r'$\mu/t$'); plt.ylabel('bulk gap'); plt.title('Kitaev-chain topological boundaries'); save('02_kitaev_gap_phase.pdf')
# 3 open-chain lowest energy
N=np.arange(8,81,2); low=np.array([lowest_abs_open_energy(int(n),mu=.5,t=1,delta=.7) for n in N]); plt.figure(figsize=(4.6,3)); plt.semilogy(N,np.maximum(low,1e-14)); plt.xlabel('chain length'); plt.ylabel('lowest |E|'); plt.title('Majorana finite-length splitting envelope'); save('03_majorana_finite_length.pdf')
# 4 ideal Andreev conversion
E=np.linspace(0,2.5,400); A=andreev_probability(E,1); plt.figure(figsize=(4.6,3)); plt.plot(E,A); plt.axvline(1,linestyle=':'); plt.xlabel(r'$|E|/\Delta$'); plt.ylabel('Andreev probability'); plt.title('Transparent NS interface'); save('04_andreev_probability.pdf')
# 5 nanowire k=0 gap versus Zeeman
vz=np.linspace(0,1.2,241); vals=[]
for v in vz:
    ee=np.linalg.eigvalsh(nanowire_hamiltonian(0,mu=.3,vz=v,delta=.4)); vals.append(np.min(np.abs(ee)))
plt.figure(figsize=(4.6,3)); plt.plot(vz,vals); plt.axvline(.5,linestyle=':'); plt.xlabel(r'$V_Z$'); plt.ylabel(r'$E_{\min}(k=0)$'); plt.title('Nanowire gap closing and reopening'); save('05_nanowire_transition.pdf')
# 6 p+ip Chern scan
mus=np.linspace(-6,6,49); cs=np.array([pwave_chern(18,mu=float(m)) for m in mus]); plt.figure(figsize=(4.6,3)); plt.plot(mus,cs,'o-',markersize=2); plt.xlabel(r'$\mu/t$'); plt.ylabel('occupied BdG Chern number'); plt.title('Chiral p-wave lattice topology'); save('06_pwave_chern_scan.pdf')
# 7 gauge-stable Chern convergence
meshes=np.array([9,12,15,18,24,30]); c=np.array([pwave_chern(int(n),mu=-2) for n in meshes]); cg=np.array([pwave_chern(int(n),mu=-2,random_gauge_seed=17) for n in meshes]); plt.figure(figsize=(4.6,3)); plt.plot(meshes,c,'o-',label='native'); plt.plot(meshes,cg,'x--',label='random gauge'); plt.xlabel('mesh n'); plt.ylabel('C'); plt.title('Gauge-stable BdG Chern calculation'); plt.legend(); save('07_pwave_chern_convergence.pdf')
# 8 DIII helical edge
k=np.linspace(-1,1,400); e0=diii_helical_edge_energies(k); em=diii_helical_edge_energies(k,tr_breaking_mass=.2); plt.figure(figsize=(4.6,3)); plt.plot(k,e0[:,0]); plt.plot(k,e0[:,1],label='TR symmetric'); plt.plot(k,em[:,0],'--'); plt.plot(k,em[:,1],'--',label='TR broken'); plt.xlabel('k'); plt.ylabel('E'); plt.title('Helical Majorana boundary'); plt.legend(); save('08_diii_helical_edge.pdf')
# 9 fixed-parity topological Josephson branch
phi=np.linspace(0,4*np.pi,500); ep=josephson_majorana_energy(phi); plt.figure(figsize=(4.6,3)); plt.plot(phi/np.pi,ep); plt.xlabel(r'$\phi/\pi$'); plt.ylabel(r'$E/E_M$'); plt.title('Fixed-parity 4pi Josephson branch'); save('09_topological_josephson_branch.pdf')
print('generated',len(list(OUT.glob('*.pdf'))),'figures in',OUT)
