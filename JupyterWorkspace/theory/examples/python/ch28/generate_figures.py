from pathlib import Path
import json,sys
import numpy as np
import matplotlib.pyplot as plt
sys.path.insert(0,str(Path(__file__).resolve().parent))
from hydrogen_companion import *
OUT=Path(__file__).resolve().parents[3]/'generated/ch28/computational';OUT.mkdir(parents=True,exist_ok=True)
def save(name):
    plt.tight_layout();plt.savefig(OUT/name);plt.close()
# 1 energy ladder
n=np.arange(1,9);plt.figure();plt.plot(n,[energy_ev(int(q)) for q in n],'o-');plt.axhline(0,ls='--');plt.xlabel('n');plt.ylabel('energy (eV)');save('hydrogen_energy_spectrum.pdf')
# 2 radial functions
r=np.linspace(0,20,700);plt.figure()
for q,l,lab in [(1,0,'1s'),(2,0,'2s'),(2,1,'2p'),(3,2,'3d')]:plt.plot(r,radial(q,l,r),label=lab)
plt.xlabel('r / reduced Bohr radius');plt.ylabel('R_nl');plt.legend();save('normalized_radial_functions.pdf')
# 3 radial probabilities
plt.figure()
for q,l,lab in [(1,0,'1s'),(2,0,'2s'),(2,1,'2p'),(3,2,'3d')]:plt.plot(r,radial_probability(q,l,r),label=lab)
plt.xlabel('r / reduced Bohr radius');plt.ylabel('radial probability');plt.legend();save('radial_probability_distributions.pdf')
# 4 cumulative probability
plt.figure()
rr=np.linspace(0,15,180);plt.plot(rr,[cumulative_radial_probability(1,0,x) for x in rr],label='1s');plt.plot(rr,[cumulative_radial_probability(2,1,x) for x in rr],label='2p');plt.xlabel('R');plt.ylabel('probability inside R');plt.legend();save('cumulative_radial_probability.pdf')
# 5 expectation radius scaling
ns=np.arange(1,11);plt.figure();plt.plot(ns,[expectation_r(int(q),0) for q in ns],label='s states');plt.plot(ns,[expectation_r(int(q),int(q-1)) for q in ns],label='circular states');plt.xlabel('n');plt.ylabel('mean radius');plt.legend();save('expectation_radius_scaling.pdf')
# 6 nodes
pts=[]
for q in range(1,8):
 for l in range(q):pts.append((q,l,radial_nodes(q,l)))
plt.figure();plt.scatter([p[0] for p in pts],[p[1] for p in pts],c=[p[2] for p in pts]);plt.colorbar(label='radial nodes');plt.xlabel('n');plt.ylabel('l');save('radial_node_map.pdf')
# 7 series wavelengths
plt.figure()
for nf,label in [(1,'Lyman'),(2,'Balmer'),(3,'Paschen')]:
 ni=np.arange(nf+1,11);plt.plot(ni,[transition_wavelength_nm(int(q),nf) for q in ni],'o-',label=label)
plt.xlabel('initial n');plt.ylabel('wavelength (nm)');plt.yscale('log');plt.legend();save('spectral_series_wavelengths.pdf')
# 8 isotope shifts
masses=np.array([1836.152673,3670.482967,5496.921535]);names=['H','D','T'];rat=np.array([reduced_mass_ratio(x) for x in masses]);plt.figure();plt.bar(names,(rat-rat[0])*1e6);plt.ylabel('Rydberg shift relative to H (ppm)');save('hydrogen_isotope_shifts.pdf')
# 9 analytic vs finite-difference s energies
fd=finite_difference_s_energies(grid_points=1800,rmax=120,levels=5);nn=np.arange(1,6);plt.figure();plt.plot(nn,[-.5/q**2 for q in nn],'o-',label='analytic');plt.plot(nn,fd,'x--',label='finite difference');plt.xlabel('s-state index n');plt.ylabel('energy (a.u.)');plt.legend();save('finite_difference_spectrum.pdf')
(OUT/'diagnostics.json').write_text(json.dumps({'figure_count':9,'test_count':30,'normalization_1s':radial_normalization(1,0),'normalization_3d':radial_normalization(3,2),'lyman_alpha_nm':transition_wavelength_nm(2,1),'fd_energies':fd.tolist()},indent=2))
