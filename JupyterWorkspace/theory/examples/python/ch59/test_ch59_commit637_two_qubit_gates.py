
import numpy as np
import pytest
from ch59_commit637_two_qubit_gates import *

def test_xy_hermitian(): assert np.allclose(xy_hamiltonian(),xy_hamiltonian().conj().T)
def test_xy_conserves_excitation():
    N=.5*(2*np.eye(4)-ZI-IZ)
    assert np.allclose(xy_hamiltonian()@N,N@xy_hamiltonian())
def test_complete_xy_transfer():
    p=evolve(xy_hamiltonian(1),basis(1),np.pi/2)
    assert abs(p[2])**2 == pytest.approx(1,abs=1e-12)
def test_half_xy_is_max_entangled():
    p=bell_from_xy()
    assert concurrence_pure(p)==pytest.approx(1,abs=1e-12)
    assert entanglement_entropy(p)==pytest.approx(1,abs=1e-12)
def test_product_concurrence_zero(): assert concurrence_pure(basis(0))==pytest.approx(0)
def test_reduced_density_trace(): assert np.trace(reduced_density_first(bell_from_xy())).real==pytest.approx(1)
def test_cp_pi_is_cz(): assert np.allclose(controlled_phase(np.pi),np.diag([1,1,1,-1]))
def test_average_fidelity_identity(): assert average_gate_fidelity(np.eye(4),np.eye(4))==pytest.approx(1)
def test_global_phase_fidelity(): assert average_gate_fidelity(-np.eye(4),np.eye(4))==pytest.approx(1)
def test_local_z_unitary():
    U=local_z(.2,-.4); assert np.allclose(U.conj().T@U,np.eye(4))
def test_cr_hermitian(): assert np.allclose(cross_resonance_hamiltonian(),cross_resonance_hamiltonian().conj().T)
def test_echo_cr_unitary():
    U=echo_cross_resonance_unitary();assert np.allclose(U.conj().T@U,np.eye(4),atol=1e-12)
def test_calibration_map_shape():
    F=gate_calibration_map(np.linspace(.9,1.1,7),np.linspace(.6,.95,9));assert F.shape==(9,7)
def test_calibration_nominal_peak():
    Js=np.array([.9,1.,1.1]);ts=np.array([.9*np.pi/4,np.pi/4,1.1*np.pi/4])
    F=gate_calibration_map(Js,ts);assert F[1,1]==pytest.approx(F.max(),rel=1e-10)
@pytest.mark.parametrize("name",["identity","cz","cnot","iswap","sqrt-iswap","swap"])
def test_canonical_coordinates_shape(name): assert canonical_nonlocal_coordinates(name).shape==(3,)
def test_cz_cnot_same_nonlocal_coordinates():
    assert np.allclose(canonical_nonlocal_coordinates("cz"),canonical_nonlocal_coordinates("cnot"))
def test_iswap_has_two_nonzero_coordinates():
    c=canonical_nonlocal_coordinates("iswap");assert c[0]>0 and c[1]>0 and c[2]==0
def test_entangling_power_identity_zero(): assert entangling_power_proxy([0,0,0])==pytest.approx(0)
def test_entangling_power_nonnegative(): assert entangling_power_proxy(canonical_nonlocal_coordinates("iswap"))>=0
def test_spectator_phase_linear(): assert spectator_zz_phase(.02,5)==pytest.approx(.1)
def test_two_qubit_hamiltonian_hermitian():
    H=two_qubit_hamiltonian(1,1.2,.1,.2,.03);assert np.allclose(H,H.conj().T)
def test_sqrt_iswap_unitary():
    U=sqrt_iswap();assert np.allclose(U.conj().T@U,np.eye(4))
