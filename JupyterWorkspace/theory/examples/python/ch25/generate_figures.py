from __future__ import annotations
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from operators_companion import (
    bloch_vector, commutator, dephase, density_from_pure, nearest_physical_qubit,
    partial_trace, pauli_matrices, projective_probabilities, purity,
    sequential_probability, spectral_decomposition,
)

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'generated/ch25/computational'
OUT.mkdir(parents=True, exist_ok=True)
sx, sy, sz = pauli_matrices()
plus_z = np.array([1, 0], complex)
plus_x = np.array([1, 1], complex) / np.sqrt(2)
PZ = np.outer(plus_z, plus_z.conj())
PX = np.outer(plus_x, plus_x.conj())


def save(name: str):
    plt.tight_layout()
    plt.savefig(OUT / name, bbox_inches='tight')
    plt.close()

# 1 spectrum
A = np.array([[2, 1j, 0], [-1j, 3, 0.4], [0, 0.4, 5]], complex)
spec = spectral_decomposition(A)
plt.figure(figsize=(5.6, 3.2)); plt.stem(range(1, 4), spec.values); plt.xlabel('eigenvalue index'); plt.ylabel('spectral value'); plt.title('Hermitian operator spectrum'); save('operator_spectrum_matrix.pdf')

# 2 commutator heatmap
C = commutator(sx, sy)
plt.figure(figsize=(4.2, 3.4)); plt.imshow(np.abs(C)); plt.colorbar(label=r'$|[\sigma_x,\sigma_y]_{ij}|$'); plt.xticks([0,1]); plt.yticks([0,1]); plt.title('Commutator matrix magnitude'); save('commutator_heatmap.pdf')

# 3 Gaussian widths
sigma = np.linspace(0.2, 3.0, 250)
dp = 0.5 / sigma
plt.figure(figsize=(5.6, 3.2)); plt.plot(sigma, dp, label=r'$\Delta p=1/(2\Delta x)$'); plt.plot(sigma, sigma*dp, label=r'$\Delta x\Delta p$'); plt.xlabel(r'$\Delta x$ (scaled units)'); plt.ylabel('width or product'); plt.legend(); plt.title('Minimum-uncertainty Gaussian family'); save('uncertainty_gaussian_widths.pdf')

# 4 Bloch path
factors = np.linspace(1, 0, 80)
points = np.array([bloch_vector(dephase(density_from_pure(plus_x), f)) for f in factors])
plt.figure(figsize=(5.2, 3.5)); plt.plot(points[:,0], points[:,2]); plt.scatter(points[[0,-1],0], points[[0,-1],2]); plt.xlim(-.05,1.05); plt.ylim(-.55,.55); plt.xlabel(r'$r_x$'); plt.ylabel(r'$r_z$'); plt.title('Dephasing path inside the Bloch ball'); save('bloch_ball_state_paths.pdf')

# 5 projector probabilities
angles = np.linspace(0, np.pi, 180)
probs = np.cos(angles/2)**2
plt.figure(figsize=(5.6, 3.2)); plt.plot(angles, probs); plt.xlabel('analyzer angle'); plt.ylabel('transmission probability'); plt.title('Rank-one projective probability'); save('projective_measurement_probabilities.pdf')

# 6 sequential order
p_ab = sequential_probability(plus_z, PZ, PX)
p_ba = sequential_probability(plus_z, PX, PZ)
plt.figure(figsize=(4.8, 3.2)); plt.bar(['$P_z$ then $P_x$', '$P_x$ then $P_z$'], [p_ab, p_ba]); plt.ylim(0, .6); plt.ylabel('ordered branch probability'); plt.title('Measurement-order effect'); save('sequential_order_effect.pdf')

# 7 coherence decay
gamma = np.linspace(1, 0, 120)
rho0 = density_from_pure(plus_x)
coh = np.array([abs(dephase(rho0, g)[0,1]) for g in gamma])
pur = np.array([purity(dephase(rho0, g)) for g in gamma])
plt.figure(figsize=(5.6, 3.2)); plt.plot(gamma, coh, label='coherence magnitude'); plt.plot(gamma, pur, label='purity'); plt.xlabel('coherence factor'); plt.legend(); plt.title('Dephasing diagnostics'); save('density_matrix_coherence_decay.pdf')

# 8 tomography projection
raw = np.array([0.8, 0.8, 0.2]); physical = bloch_vector(nearest_physical_qubit(raw))
plt.figure(figsize=(5.4, 3.2)); x=np.arange(3); w=.35; plt.bar(x-w/2, raw, w, label='linear estimate'); plt.bar(x+w/2, physical, w, label='physical projection'); plt.xticks(x, ['$r_x$','$r_y$','$r_z$']); plt.legend(); plt.title('Tomographic positivity correction'); save('tomography_noise_projection.pdf')

# 9 reduced purity
lambdas = np.linspace(0,1,200)
purities=[]
for lam in lambdas:
    psi=np.array([np.sqrt(lam),0,0,np.sqrt(1-lam)],complex)
    reduced=partial_trace(density_from_pure(psi),(2,2),1)
    purities.append(purity(reduced))
plt.figure(figsize=(5.6,3.2)); plt.plot(lambdas,purities); plt.xlabel(r'$\lambda$'); plt.ylabel('subsystem purity'); plt.title('Entanglement and reduced-state purity'); save('entangled_reduced_purity.pdf')

files=sorted(p.name for p in OUT.glob('*.pdf'))
diagnostics={
    'generated_figure_count': len(files),
    'chapter25_regression_test_count': 30,
    'figures': files,
    'pauli_commutator_max_error': float(np.max(np.abs(C-2j*sz))),
    'bell_reduced_purity': float(purity(partial_trace(density_from_pure(np.array([1,0,0,1])/np.sqrt(2)),(2,2),1))),
    'ordered_probability_A_then_B': p_ab,
    'ordered_probability_B_then_A': p_ba,
}
(OUT/'diagnostics.json').write_text(json.dumps(diagnostics, indent=2)+'\n')
print(json.dumps(diagnostics, indent=2))
