import numpy as np
import pytest
from hilbert_companion import *

z=np.array([1,0],complex); o=np.array([0,1],complex)

def test_01_normalize(): assert np.allclose(normalize([3,4]),[.6,.8])
def test_02_zero_rejected():
    with pytest.raises(ValueError): normalize([0,0])
def test_03_inner_conjugate(): assert inner([1,1j],[1,1j])==2
def test_04_gram_hermitian():
    G=gram_matrix([[1,0],[1,1j]]); assert np.allclose(G,G.conj().T)
def test_05_gram_psd(): assert np.min(np.linalg.eigvalsh(gram_matrix([[1,0],[1,1]])))>=-1e-12
def test_06_gram_schmidt_orthonormal():
    Q=gram_schmidt([[1,1],[1,0]]); assert np.allclose(Q.conj().T@Q,np.eye(2))
def test_07_dependent_vector_removed(): assert gram_schmidt([[1,0],[2,0]]).shape==(2,1)
def test_08_rank_one_projector():
    P=projector([1,1j]); assert np.allclose(P@P,P)
def test_09_projector_hermitian():
    P=projector([1,2]); assert np.allclose(P,P.conj().T)
def test_10_subspace_projector_rank(): assert round(np.trace(subspace_projector(np.eye(3)[:,:2])).real)==2
def test_11_unitary_hadamard(): assert is_unitary(np.array([[1,1],[1,-1]])/np.sqrt(2))
def test_12_nonunitary_rejected(): assert not is_unitary(np.array([[1,1],[0,1]]))
def test_13_basis_roundtrip():
    B=np.array([[1,1],[1,-1]],complex)/np.sqrt(2); q=normalize([1,2j]); assert np.allclose(reconstruct(basis_coordinates(q,B),B),q)
def test_14_tensor_dimension(): assert tensor(z,o,z).shape==(8,)
def test_15_tensor_norm(): assert np.isclose(np.linalg.norm(tensor(normalize([1,1]),normalize([1,1j]))),1)
def test_16_density_trace(): assert np.isclose(np.trace(density([1,1])),1)
def test_17_density_pure(): assert np.isclose(purity(density([1,1j])),1)
def test_18_partial_trace_product():
    q=tensor(normalize([1,1]),o); assert np.allclose(partial_trace(density(q),(2,2),'B'),density([1,1]))
def test_19_partial_trace_bell(): assert np.allclose(partial_trace(density(bell_state()),(2,2),'B'),np.eye(2)/2)
def test_20_schmidt_product(): assert np.allclose(schmidt_coefficients(tensor(z,o),(2,2)),[1,0])
def test_21_schmidt_bell(): assert np.allclose(schmidt_coefficients(bell_state(),(2,2)),[.5,.5])
def test_22_entropy_product(): assert np.isclose(entanglement_entropy(tensor(z,o),(2,2),2),0)
def test_23_entropy_bell(): assert np.isclose(entanglement_entropy(bell_state(),(2,2),2),1)
def test_24_fidelity_global_phase(): assert np.isclose(fidelity_pure([1,1],np.exp(1j*.4)*np.array([1,1])),1)
def test_25_unitary_evolution_unitary():
    U=unitary_from_hermitian(np.diag([0,2]),.7); assert is_unitary(U)
def test_26_stationary_phase():
    U=unitary_from_hermitian(np.diag([0,2]),.7); assert np.isclose(abs(U[1,1]),1)
def test_27_expectation_real_hermitian(): assert abs(expectation([1,1j],np.array([[1,1j],[-1j,2]])).imag)<1e-12
def test_28_bell_orthonormal():
    labels=['phi+','phi-','psi+','psi-']; G=gram_matrix([bell_state(x) for x in labels]); assert np.allclose(G,np.eye(4))
def test_29_phi_correlations(): assert np.allclose(np.diag(correlation_matrix(bell_state('phi+'))),[1,-1,1])
def test_30_singlet_correlations(): assert np.allclose(correlation_matrix(bell_state('psi-')),-np.eye(3))
