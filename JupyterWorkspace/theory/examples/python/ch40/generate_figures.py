from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from composite_fermions_anyons_companion import *
OUT=Path(__file__).resolve().parents[3]/'generated/ch40/computational'; OUT.mkdir(parents=True,exist_ok=True)
def save(name):
    plt.tight_layout(); plt.savefig(OUT/name,format='pdf'); plt.close()
# 1 Jain sequences
p=np.arange(1,9); plt.figure(); plt.plot(p,[jain_fraction(x,1,1) for x in p],marker='o',label='p/(2p+1)'); plt.plot(p,[jain_fraction(x,1,-1) for x in p],marker='s',label='p/(2p-1)'); plt.xlabel('p'); plt.ylabel('electron filling nu'); plt.legend(); save('01_jain_sequences.pdf')
# 2 effective field approaching half filling
nu=np.linspace(.05,.495,300); plt.figure(); plt.plot(nu,[effective_field_ratio(x) for x in nu]); plt.axhline(0,linewidth=.8); plt.xlabel('nu'); plt.ylabel('B* / B'); save('02_effective_field.pdf')
# 3 finite flux map along 2/5 sphere sequence
N=np.arange(4,22,2); Nphi=(5*N//2)-4; Nstar=np.array([finite_effective_flux(int(n),int(ph),1) for n,ph in zip(N,Nphi)]); plt.figure(); plt.plot(N,Nphi,marker='o',label='N_phi'); plt.plot(N,Nstar,marker='s',label='N_phi*'); plt.xlabel('N'); plt.ylabel('flux quanta'); plt.legend(); save('03_finite_flux.pdf')
# 4 half-filled CF Fermi wavevector
dens=np.linspace(.1,2.0,200)*1e15; plt.figure(); plt.plot(dens/1e15,[cf_fermi_wavevector(x)/1e8 for x in dens]); plt.xlabel('density (10^15 m^-2)'); plt.ylabel('k_F (10^8 m^-1)'); save('04_cf_fermi_wavevector.pdf')
# 5 representative parton fillings
names=['111','211','311','-211']; vals=[parton_filling([1,1,1]),parton_filling([2,1,1]),parton_filling([3,1,1]),parton_filling([-2,1,1])]; plt.figure(); plt.bar(np.arange(4),vals); plt.xticks(np.arange(4),names); plt.ylabel('nu'); plt.xlabel('parton integer fillings'); save('05_parton_fillings.pdf')
# 6 Laughlin anyon data
m=np.array([3,5,7,9]); plt.figure(); plt.plot(m,1/m,marker='o',label='|Q|/e'); plt.plot(m,1/m,marker='s',linestyle='--',label='theta/pi'); plt.xlabel('m'); plt.ylabel('fractional topological data'); plt.legend(); save('06_laughlin_anyon_data.pdf')
# 7 Jain K-matrix denominator/minimal charge
p=np.arange(1,7); Kdeg=np.array([torus_degeneracy(jain_kmatrix(int(x),1)) for x in p]); plt.figure(); plt.plot(p,Kdeg,marker='o',label='|det K|'); plt.plot(p,1/Kdeg,marker='s',label='minimal |Q|/e'); plt.xlabel('p'); plt.ylabel('topological scale'); plt.legend(); save('07_jain_kmatrix_data.pdf')
# 8 Ising fusion-space growth
ns=np.arange(2,14,2); dims=[ising_fusion_space_dimension(int(n)) for n in ns]; plt.figure(); plt.semilogy(ns,dims,marker='o',base=2); plt.xlabel('number of sigma anyons'); plt.ylabel('fixed-total fusion-space dimension'); save('08_ising_fusion_space.pdf')
# 9 Read-Rezayi clustered fillings
k=np.arange(2,8); vals=[read_rezayi_filling(int(x),1) for x in k]; plt.figure(); plt.plot(k,vals,marker='o'); plt.xlabel('cluster index k'); plt.ylabel('nu = k/(k+2), M=1'); save('09_read_rezayi_fillings.pdf')
