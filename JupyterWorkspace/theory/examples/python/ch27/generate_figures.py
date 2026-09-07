from pathlib import Path
import json,sys
import numpy as np
import matplotlib.pyplot as plt
sys.path.insert(0,str(Path(__file__).resolve().parent))
from angular_momentum_companion import *
OUT=Path(__file__).resolve().parents[3]/'generated/ch27/computational';OUT.mkdir(parents=True,exist_ok=True)
def save(name):plt.tight_layout();plt.savefig(OUT/name);plt.close()
# 1 spin rotation probabilities
ang=np.linspace(0,2*np.pi,240);p=[]
for a in ang:p.append(measurement_probabilities(rotation_spin_half([0,1,0],a)@UP,[0,0,1])[0])
plt.figure();plt.plot(ang,p);plt.xlabel('rotation angle');plt.ylabel('probability of +z');save('spin_half_rotation_probabilities.pdf')
# 2 Bloch trajectory
r=np.array([bloch_vector(rotation_spin_half([0,0,1],a)@normalize([1,1])) for a in ang])
plt.figure();plt.plot(r[:,0],r[:,1]);plt.xlabel('Bloch x');plt.ylabel('Bloch y');plt.axis('equal');save('bloch_rotation_trajectory.pdf')
# 3 sequential SG
axes=np.linspace(0,np.pi,180);plt.figure();plt.plot(axes,(1+np.cos(axes))/2);plt.xlabel('analyzer angle');plt.ylabel('conditional + probability');save('stern_gerlach_sequence.pdf')
# 4 ladder coefficients
j=3;m=np.arange(-j,j+1);coef=np.sqrt((j-m)*(j+m+1));plt.figure();plt.bar(m,coef);plt.xlabel('m');plt.ylabel('raising coefficient / hbar');save('ladder_coefficients_j3.pdf')
# 5 commutator residual by j
js=np.arange(.5,6,.5);res=[]
for q in js:
 x,y,z,*_=angular_momentum_matrices(q);res.append(np.linalg.norm(commutator(x,y)-1j*z))
plt.figure();plt.semilogy(js,np.maximum(res,1e-18));plt.xlabel('j');plt.ylabel('commutator residual');save('angular_momentum_commutator_residual.pdf')
# 6 Y10 density polar profile
th=np.linspace(0,np.pi,300);rad=y10_density(th);plt.figure();ax=plt.subplot(111,projection='polar');ax.plot(th,rad);ax.plot(-th,rad);save('spherical_harmonic_y10_density.pdf')
# 7 CG matrix
C=np.abs(cg_spin_half_matrix())**2;plt.figure();plt.imshow(C,vmin=0,vmax=1);plt.colorbar(label='squared amplitude');plt.xlabel('coupled basis column');plt.ylabel('product basis row');save('clebsch_gordan_matrix.pdf')
# 8 singlet correlations
T=correlation_matrix(coupled_states()['singlet']);plt.figure();plt.imshow(T,vmin=-1,vmax=1);plt.colorbar(label='correlation');plt.xticks(range(3),['X','Y','Z']);plt.yticks(range(3),['X','Y','Z']);save('singlet_triplet_correlations.pdf')
# 9 coupling spectrum
vals=np.linalg.eigvalsh(total_spin_squared());plt.figure();plt.bar(range(4),vals);plt.xlabel('eigenvalue index');plt.ylabel('J squared / hbar squared');save('spin_coupling_spectrum.pdf')
(OUT/'diagnostics.json').write_text(json.dumps({'figure_count':9,'test_count':30,'singlet_spin_squared':float(np.real(expectation(coupled_states()['singlet'],total_spin_squared()))),'triplet_spin_squared':float(np.real(expectation(coupled_states()['triplet_zero'],total_spin_squared())))},indent=2))
