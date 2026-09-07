from pathlib import Path
import json,sys
import numpy as np
import matplotlib.pyplot as plt
sys.path.insert(0,str(Path(__file__).resolve().parent))
from hilbert_companion import *
OUT=Path(__file__).resolve().parents[3]/'generated/ch26/computational';OUT.mkdir(parents=True,exist_ok=True)
z=np.array([1,0],complex); o=np.array([0,1],complex)

def save(name): plt.tight_layout();plt.savefig(OUT/name);plt.close()
# 1 inner product geometry
plt.figure();plt.quiver([0,0],[0,0],[1,.6],[.3,1],angles='xy',scale_units='xy',scale=1);plt.xlim(-.1,1.3);plt.ylim(-.1,1.3);plt.xlabel('Re coordinate');plt.ylabel('Im/geometric coordinate');save('inner_product_geometry.pdf')
# 2 Gram spectrum
G=gram_matrix([[1,0,0],[1,1,0],[1,1j,1]]);plt.figure();plt.bar(range(1,4),np.linalg.eigvalsh(G));plt.xlabel('eigenvalue index');plt.ylabel('Gram eigenvalue');save('gram_matrix_spectrum.pdf')
# 3 basis probabilities
th=np.linspace(0,np.pi/2,150);plt.figure();plt.plot(th,np.cos(th)**2,label='basis outcome 0');plt.plot(th,np.sin(th)**2,label='basis outcome 1');plt.legend();plt.xlabel('basis angle');plt.ylabel('probability');save('basis_change_probabilities.pdf')
# 4 projector decomposition
angles=np.linspace(0,2*np.pi,120);vals=[]
P=projector([1,0]);
for a in angles: vals.append(np.linalg.norm(P@np.array([np.cos(a),np.sin(a)]))**2)
plt.figure();plt.plot(angles,vals);plt.xlabel('state angle');plt.ylabel('projected norm squared');save('projector_decomposition.pdf')
# 5 unitary trajectory
H=np.array([[0,1],[1,0]],complex);ts=np.linspace(0,2*np.pi,160);p=[]
for t in ts:
 q=unitary_from_hermitian(H,t)@z;p.append(abs(q[1])**2)
plt.figure();plt.plot(ts,p);plt.xlabel('time');plt.ylabel('transition probability');save('unitary_state_trajectory.pdf')
# 6 Schmidt coefficients
lam=np.linspace(0,1,151);plt.figure();plt.plot(lam,lam,label='lambda 1');plt.plot(lam,1-lam,label='lambda 2');plt.legend();plt.xlabel('family parameter');plt.ylabel('Schmidt weight');save('schmidt_coefficients.pdf')
# 7 entropy family
ent=[]
for x in lam:
 q=normalize(np.sqrt(x)*tensor(z,z)+np.sqrt(1-x)*tensor(o,o)) if x not in (0,1) else (tensor(o,o) if x==0 else tensor(z,z))
 ent.append(entanglement_entropy(q,(2,2),2))
plt.figure();plt.plot(lam,ent);plt.xlabel('lambda');plt.ylabel('entanglement entropy (bits)');save('entanglement_entropy_family.pdf')
# 8 reduced purity
plt.figure();plt.plot(lam,lam**2+(1-lam)**2);plt.xlabel('lambda');plt.ylabel('reduced purity');save('partial_trace_purity.pdf')
# 9 Bell correlations
T=correlation_matrix(bell_state('phi+'));plt.figure();plt.imshow(T,vmin=-1,vmax=1);plt.colorbar(label='correlation');plt.xticks(range(3),['X','Y','Z']);plt.yticks(range(3),['X','Y','Z']);save('bell_correlation_matrix.pdf')
(OUT/'diagnostics.json').write_text(json.dumps({'figure_count':9,'test_count':30,'bell_entropy_bits':entanglement_entropy(bell_state(),(2,2),2),'singlet_correlation_trace':float(np.trace(correlation_matrix(bell_state('psi-'))))},indent=2))
