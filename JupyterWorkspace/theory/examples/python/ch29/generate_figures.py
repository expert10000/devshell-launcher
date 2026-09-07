from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from many_particle_companion import *
OUT=Path(__file__).resolve().parents[3]/'generated/ch29/computational'; OUT.mkdir(parents=True,exist_ok=True)

def save(name):
    plt.tight_layout(); plt.savefig(OUT/name); plt.close()

m=np.arange(4,13); plt.figure(); plt.plot(m,[bosonic_dimension(4,int(x)) for x in m],marker='o',label='4 bosons'); plt.plot(m,[fermionic_dimension(4,int(x)) for x in m],marker='s',label='4 fermions'); plt.xlabel('number of modes'); plt.ylabel('basis dimension'); plt.legend(); save('basis_dimension_growth.pdf')
a=boson_annihilation(8); plt.figure(); plt.plot(np.arange(1,9),[a[n-1,n] for n in range(1,9)],marker='o'); plt.xlabel('occupation n'); plt.ylabel('annihilation amplitude'); save('bosonic_ladder_factors.pdf')
c=fermion_annihilation(); plt.figure(); plt.imshow(c); plt.xticks([0,1]); plt.yticks([0,1]); plt.title('fermion annihilation matrix'); plt.colorbar(); save('fermionic_ladder_matrix.pdf')
plt.figure(); plt.bar(np.arange(4),[1,1,0,0],label='Slater'); plt.plot(np.arange(4),[.92,.88,.12,.08],marker='o',label='correlated'); plt.xlabel('natural orbital'); plt.ylabel('occupation'); plt.legend(); save('natural_occupation_spectra.pdf')
plt.figure(); plt.bar(['number n=1','coherent','thermal'],[g2_single_mode(1),coherent_g2(),thermal_g2()]); plt.ylabel(r'$g^{(2)}(0)$'); save('pair_correlation_statistics.pdf')
us=np.linspace(0,8,41); spec=[]
for u in us: spec.append(np.linalg.eigvalsh(bose_hubbard_dimer(3,1,float(u))[0]))
plt.figure(); plt.plot(us,np.array(spec)); plt.xlabel('U/t'); plt.ylabel('energy/t'); save('bose_hubbard_spectrum.pdf')
vals=[]
for u in us:
 h,b=bose_hubbard_dimer(4,1,float(u)); _,psi=ground_state(h); vals.append(np.sum(np.abs(psi)**2*np.array([(x[0]-x[1])**2 for x in b])))
plt.figure(); plt.plot(us,vals); plt.xlabel('U/t'); plt.ylabel('number-imbalance variance'); save('bose_hubbard_number_fluctuations.pdf')
r=np.linspace(0,4,300); plt.figure(); plt.plot(r,exchange_hole_gaussian(r)); plt.xlabel('separation / width'); plt.ylabel(r'$g^{(2)}$ model'); save('exchange_hole_model.pdf')
theta=np.linspace(0,np.pi/4,200); ent=[]
for x in theta:
 psi=np.array([np.cos(x),0,0,np.sin(x)]); ent.append(von_neumann_entropy(partial_trace_two_qubits(density_matrix(psi))))
plt.figure(); plt.plot(theta,ent); plt.xlabel('Schmidt angle'); plt.ylabel('one-body entropy (bits)'); save('reduced_density_entropy.pdf')
