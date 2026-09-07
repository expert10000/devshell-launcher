import numpy as np, pytest
from ch59_commit636_coupled_effective import *
def test_exchange_hermitian():
 H=exchange_hamiltonian();assert np.allclose(H,H.conj().T)
def test_xy_hermitian(): assert np.allclose(xy_hamiltonian(),xy_hamiltonian().conj().T)
def test_zz_hermitian(): assert np.allclose(zz_hamiltonian(),zz_hamiltonian().conj().T)
def test_step_unitary():
 U=hermitian_step(exchange_hamiltonian(),.3);assert np.allclose(U.conj().T@U,np.eye(4))
def test_fidelity_self():
 p=np.array([1,2j,0,1]);assert state_fidelity(p,p)==pytest.approx(1)
def test_product_concurrence_zero(): assert concurrence_pure([1,0,0,0])==pytest.approx(0)
def test_bell_concurrence_one(): assert concurrence_pure(bell_state())==pytest.approx(1)
def test_product_entropy_zero(): assert entanglement_entropy([1,0,0,0])<1e-10
def test_bell_entropy_one(): assert entanglement_entropy(bell_state())==pytest.approx(1)
def test_iswap_unitary():
 U=iswap_unitary();assert np.allclose(U.conj().T@U,np.eye(4))
def test_iswap_maps_01_to_10():
 out=iswap_unitary()@np.array([0,1,0,0],complex);assert abs(out[2])==pytest.approx(1)
def test_cz_unitary():
 U=controlled_phase();assert np.allclose(U.conj().T@U,np.eye(4));assert U[3,3]==pytest.approx(-1+0j)
def test_dispersive_sign(): assert dispersive_shift(2,4)==pytest.approx(1)
def test_dispersive_bad():
 with pytest.raises(ValueError): dispersive_shift(1,0)
def test_sw_trace_preserved():
 H=sw_two_level_effective(5,1,.2);assert np.trace(H).real==pytest.approx(6)
def test_sw_bad():
 with pytest.raises(ValueError):sw_two_level_effective(1,1,.2)
def test_sw_approximates_exact_eigenvalues():
 exact=np.linalg.eigvalsh(exact_two_level(5,1,.1));eff=np.linalg.eigvalsh(sw_two_level_effective(5,1,.1));assert np.max(abs(exact-eff))<1e-4
def test_cr_hermitian():
 H=cross_resonance_hamiltonian(1,.1,.2,.03);assert np.allclose(H,H.conj().T)
def test_swap_trace_bounds():
 p=swap_population_trace(np.linspace(0,3,100));assert p.min()>=0 and p.max()<=1+1e-12
def test_swap_reaches_near_one(): assert swap_population_trace([np.pi/2],1)[0]>0.99
def test_entanglement_trace_bounds():
 e=entanglement_trace(np.linspace(0,2,40));assert e.min()>=-1e-10 and e.max()<=1+1e-10
def test_xy_half_swap_entangles(): assert entanglement_trace([np.pi/4],1)[0]>0.99
