
import numpy as np, pytest
from ch59_commit638_effective_engineering import *
def test_sw_hermitian(): assert np.allclose(sw_second_order(2,-2,.1),sw_second_order(2,-2,.1).conj().T)
def test_sw_zero_coupling_exact(): assert sw_error(2,-2,0)==pytest.approx(0)
def test_sw_improves_small_ratio():
    assert sw_error(2,-2,.05)<sw_error(2,-2,.5)
def test_sw_degenerate_rejected():
    with pytest.raises(ValueError):sw_second_order(1,1,.1)
def test_mediated_exchange_formula():assert mediated_exchange(.2,.3,2)==pytest.approx(.03)
def test_dispersive_shift_sign():assert dispersive_shift(.2,-2)<0
def test_bus_hamiltonian_hermitian():
    H=bus_single_excitation_hamiltonian(1,1.2,3,.1,.2);assert np.allclose(H,H.conj().T)
def test_bus_population_basis():assert bus_population([0,0,1])==pytest.approx(1)
def test_effective_block_hermitian():
    H=effective_qubit_block(1,1.1,3,.1,.15);assert np.allclose(H,H.conj().T)
def test_effective_block_denominator_rejected():
    with pytest.raises(ValueError):effective_qubit_block(3,1,3,.1,.1)
def test_elimination_scale_quadratic():
    assert adiabatic_elimination_population_scale(.2,2)==pytest.approx(.01)
def test_magnus_average_constant():
    H=.4*X;assert np.allclose(magnus_first_average([H,H],[1,2]),H)
def test_commutator_antisymmetric():
    assert np.allclose(commutator(X,Y),-commutator(Y,X))
def test_second_magnus_zero_commuting():
    assert np.allclose(magnus_second_term([X,2*X],[.2,.3]),0)
def test_second_magnus_nonzero_noncommuting():
    assert np.linalg.norm(magnus_second_term([X,Y],[.2,.3]))>0
def test_toggling_identity_returns_H():
    assert np.allclose(toggling_average(Z,[I,I]),Z)
def test_echo_cancels_zz():
    assert np.linalg.norm(echoed_zz_average())<1e-12
def test_floquet_unitary():
    U=floquet_two_step(.2*X,.3*Z,.1);assert np.allclose(U.conj().T@U,I,atol=1e-12)
def test_quasienergy_count():assert len(quasienergies(floquet_two_step(.2*X,.3*Z,.1),.2))==2
def test_exact_effective_identical_zero():
    H=.2*X;psi=np.array([1,0],complex);assert exact_effective_state_error(H,H,psi,2)==pytest.approx(0,abs=1e-12)
@pytest.mark.parametrize("ratio",[.02,.05,.1,.2])
def test_sw_error_nonnegative(ratio):assert sw_error(1,-1,ratio)>=0
def test_evolution_norm():
    psi=evolve(exact_two_level(1,-1,.2),[1,0],3);assert np.linalg.norm(psi)==pytest.approx(1)
