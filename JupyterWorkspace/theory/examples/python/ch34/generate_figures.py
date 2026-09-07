from pathlib import Path
import math
import numpy as np
import matplotlib.pyplot as plt
plt.rcParams["pdf.fonttype"]=42
plt.rcParams["ps.fonttype"]=42
from qft_companion import *
OUT=Path(__file__).resolve().parents[3]/'generated/ch34/computational'; OUT.mkdir(parents=True,exist_ok=True)

def save(name):
    plt.tight_layout(); plt.savefig(OUT/name,format='pdf'); plt.close()
# 1 dispersion
p=np.linspace(0,5,250); plt.figure(); plt.plot(p,relativistic_energy(p,1)); plt.xlabel('p/m'); plt.ylabel('E/m'); plt.title('Relativistic scalar dispersion'); save('01_scalar_dispersion.pdf')
# 2 Bose/Fermi occupancy
x=np.linspace(.15,6,250); plt.figure(); plt.plot(x,bose_occupation(x,1),label='boson'); plt.plot(x,fermi_occupation(x,1),label='fermion'); plt.xlabel('(E-mu)/T'); plt.ylabel('occupation'); plt.legend(); plt.title('Mode occupation'); save('02_quantum_occupations.pdf')
# 3 propagator pole
p0=np.linspace(-3,3,600); prop=scalar_propagator(p0,0,1,0.05); plt.figure(); plt.plot(p0,np.abs(prop)); plt.xlabel('p0/m'); plt.ylabel('|Delta_F|'); plt.title('Regulated scalar propagator poles'); save('03_propagator_poles.pdf')
# 4 equal time correlation
r=np.linspace(.1,5,250); plt.figure(); plt.semilogy(r,equal_time_yukawa_correlation(r,1)); plt.xlabel('mr'); plt.ylabel('correlation'); plt.title('Massive equal-time correlation scale'); save('04_vacuum_correlation.pdf')
# 5 Dyson convergence
orders=np.arange(0,11); exact=np.exp(-1j*1.5); err=[abs(dyson_exponential_partial(1,1.5,int(n))-exact) for n in orders]; plt.figure(); plt.semilogy(orders,err,marker='o'); plt.xlabel('Dyson/Taylor order'); plt.ylabel('absolute error'); plt.title('Dyson-series convergence for commuting H_I'); save('05_dyson_convergence.pdf')
# 6 Wick pairings
n=np.array([2,4,6,8,10]); counts=np.array([wick_pairing_count(int(k)) for k in n]); plt.figure(); plt.semilogy(n,counts,marker='o'); plt.xlabel('number of fields'); plt.ylabel('complete pairings'); plt.title('Wick contraction combinatorics'); save('06_wick_pairings.pdf')
# 7 tree amplitude
lam=np.linspace(0,2,200); plt.figure(); plt.plot(lam,[phi4_tree_amplitude(z) for z in lam]); plt.xlabel('lambda'); plt.ylabel('M_tree'); plt.title('Tree 2->2 amplitude in phi^4'); save('07_phi4_tree_amplitude.pdf')
# 8 phase space
s=np.linspace(4.01,30,240); ps=np.array([two_body_phase_space(float(z),1,1) for z in s]); plt.figure(); plt.plot(np.sqrt(s),ps); plt.xlabel('sqrt(s)/m'); plt.ylabel('two-body phase space'); plt.title('Relativistic two-body phase space'); save('08_two_body_phase_space.pdf')
# 9 charge sectors
n=np.arange(0,6); plt.figure(); plt.plot(n,[charged_state_charge(int(k),1) for k in n],marker='o'); plt.xlabel('particle occupation n+ (n-=1)'); plt.ylabel('charge / q'); plt.title('Complex-scalar charge sectors'); save('09_charge_sectors.pdf')
