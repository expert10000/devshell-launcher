
import numpy as np, pytest
from ch59_commit639_networks_prefreeze import *
def test_dimension():assert hilbert_dimension(4)==16
def test_xy_graph_hermitian():
    H=graph_hamiltonian(3,[(0,1,1),(1,2,.7)],"xy");assert np.allclose(H,H.conj().T)
def test_ising_graph_hermitian():
    H=graph_hamiltonian(3,[(0,2,.2)],"ising");assert np.allclose(H,H.conj().T)
def test_heisenberg_graph_hermitian():
    H=graph_hamiltonian(3,[(0,1,1)],"heisenberg");assert np.allclose(H,H.conj().T)
def test_unknown_model_rejected():
    with pytest.raises(ValueError):graph_hamiltonian(2,[(0,1,1)],"bad")
def test_xy_conserves_excitation():
    H=graph_hamiltonian(3,[(0,1,1),(1,2,1)],"xy");N=excitation_number(3);assert np.allclose(H@N,N@H)
def test_single_excitation_matrix_symmetric():
    M=single_excitation_matrix(4,[(0,1,1),(2,3,.2)]);assert np.allclose(M,M.T)
def test_single_excitation_probabilities_normalized():
    p=single_excitation_probabilities(3,[(0,1,1),(1,2,1)],0,np.linspace(0,3,20));assert np.allclose(p.sum(axis=1),1)
def test_ghz_norm():assert np.linalg.norm(ghz_state(4))==pytest.approx(1)
def test_ghz_one_site_entropy():assert entropy_one(ghz_state(3),0,3)==pytest.approx(1)
def test_product_entropy_zero():
    psi=np.zeros(8,complex);psi[0]=1;assert entropy_one(psi,1,3)==pytest.approx(0)
def test_residual_zz_hermitian():
    H=residual_zz_matrix(3,[(0,2,.01)]);assert np.allclose(H,H.conj().T)
def test_crosstalk_phase():assert crosstalk_phase(.02,5)==pytest.approx(.1)
def test_gap_nonnegative():
    H=graph_hamiltonian(3,[(0,1,1),(1,2,.5)],"heisenberg");assert spectral_gap(H)>=0
def test_adjacency():
    A=interaction_adjacency(3,[(0,2,.4)]);assert A[0,2]==pytest.approx(.4) and A[2,0]==pytest.approx(.4)
def test_refocused_identity():
    H=np.kron(Z,Z);assert np.allclose(refocused_average(H,[np.eye(4),np.eye(4)]),H)
def test_three_body_hermitian():
    H=three_body_zzz();assert np.allclose(H,H.conj().T)
def test_three_body_requires_three():
    with pytest.raises(ValueError):three_body_zzz(2)
def test_state_fidelity_identical():
    a=ghz_state(3);assert state_fidelity(a,a)==pytest.approx(1)
@pytest.mark.parametrize("n",[2,3,4,5])
def test_hilbert_scaling(n):assert hilbert_dimension(n)==2**n
def test_evolution_norm():
    H=graph_hamiltonian(3,[(0,1,1),(1,2,1)],"xy");psi=np.zeros(8,complex);psi[4]=1;assert np.linalg.norm(evolve(H,psi,2))==pytest.approx(1)
