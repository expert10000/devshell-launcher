import importlib.util
from pathlib import Path
import numpy as np

MODULE=Path(__file__).with_name("ch57_quantitative_prefreeze.py")
spec=importlib.util.spec_from_file_location("ch57_quantitative_prefreeze",MODULE)
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)


def sorted_complex(a):
    return np.array(sorted(a,key=lambda z:(round(z.real,10),round(z.imag,10))),complex)


def test_single_spin_liouvillian_shape():
    assert m.single_spin_liouvillian().shape==(4,4)


def test_single_spin_expected_spectrum():
    w,gd,gu,gp=2.1,0.7,0.2,0.13
    got=np.linalg.eigvals(m.single_spin_liouvillian(w,gd,gu,gp))
    exp=m.expected_single_spin_eigenvalues(w,gd,gu,gp)
    assert np.allclose(sorted_complex(got),sorted_complex(exp),atol=1e-10)


def test_single_spin_left_half_plane():
    vals=np.linalg.eigvals(m.single_spin_liouvillian())
    assert vals.real.max()<1e-10


def test_single_spin_has_zero_mode():
    vals=np.linalg.eigvals(m.single_spin_liouvillian())
    assert np.min(np.abs(vals))<1e-10


def test_trace_preservation_single_spin():
    L=m.single_spin_liouvillian()
    tr=m.trace_left_vector(2)
    assert np.linalg.norm(tr@L)<1e-10


def test_two_spin_liouvillian_shape():
    assert m.two_spin_liouvillian().shape==(16,16)


def test_two_spin_left_half_plane_independent():
    vals=np.linalg.eigvals(m.two_spin_liouvillian(collective=False))
    assert vals.real.max()<1e-9


def test_two_spin_left_half_plane_collective():
    vals=np.linalg.eigvals(m.two_spin_liouvillian(collective=True))
    assert vals.real.max()<1e-9


def test_two_spin_trace_preservation():
    L=m.two_spin_liouvillian(collective=True)
    assert np.linalg.norm(m.trace_left_vector(4)@L)<1e-9


def test_collective_model_has_extra_dark_zero_mode():
    vals=np.linalg.eigvals(m.two_spin_liouvillian(exchange=0.0,collective=True))
    assert np.sum(np.abs(vals)<1e-8)>=2


def test_liouvillian_gap_nonnegative():
    assert m.liouvillian_gap(m.single_spin_liouvillian())>=0


def test_one_magnon_hamiltonian_hermitian():
    H=m.one_magnon_hamiltonian(17)
    assert np.allclose(H,H.conj().T)


def test_exact_propagation_norm_conserved():
    H=m.one_magnon_hamiltonian(21)
    psi0=np.zeros(21,complex); psi0[10]=1
    psi=m.exact_unitary_propagation(H,psi0,[0,1,3,8])
    assert np.allclose(np.sum(np.abs(psi)**2,axis=1),1,atol=1e-12)


def test_exact_propagation_initial_state():
    H=m.one_magnon_hamiltonian(11)
    psi0=np.zeros(11,complex); psi0[5]=1
    psi=m.exact_unitary_propagation(H,psi0,[0])
    assert np.allclose(psi[0],psi0)


def test_disorder_hamiltonian_hermitian():
    H=m.one_magnon_hamiltonian(15,disorder=5.0,seed=2)
    assert np.allclose(H,H.conj().T)


def test_ipr_localized_is_one():
    psi=np.zeros(8,complex); psi[3]=1
    assert abs(m.inverse_participation_ratio(psi)-1)<1e-15


def test_ipr_uniform_is_inverse_N():
    N=10; psi=np.ones(N)/np.sqrt(N)
    assert abs(m.inverse_participation_ratio(psi)-1/N)<1e-15


def test_ep_coalesces_at_zero():
    vals=m.ep_eigenvalues(0.0,gamma=1.3)
    assert np.allclose(vals,[-1.3,-1.3])


def test_ep_matrix_defective_at_zero():
    A=m.ep_matrix(0.0,gamma=1.0)
    rank=np.linalg.matrix_rank(A+np.eye(2))
    assert rank==1


def test_jordan_propagator_at_zero_time_identity():
    assert np.allclose(m.jordan_ep_propagator(0.0),np.eye(2))


def test_jordan_polynomial_term():
    t=0.4; G=m.jordan_ep_propagator(t,gamma=1.0)
    assert abs(G[0,1]-t*np.exp(-t))<1e-15


def test_gaussian_envelope_one_at_zero():
    assert m.gaussian_quasistatic_envelope([0])[0]==1


def test_exponential_envelope_one_at_zero():
    assert m.exponential_envelope([0])[0]==1


def test_ou_spectrum_even():
    s=m.ou_spectrum(np.array([-2.0,2.0]),tau_c=0.7)
    assert np.allclose(s[0],s[1])


def test_ou_ramsey_one_at_zero():
    assert abs(m.ou_ramsey_envelope([0.0])[0]-1)<1e-15


def test_dicke_rate_endpoints():
    r=m.dicke_rates(8)
    assert r[0]==0
    assert r[-1]==8


def test_dicke_middle_enhanced():
    r=m.dicke_rates(20)
    assert r[10]>20


def test_dicke_trajectory_probability_conserved():
    t,P,I=m.dicke_rate_trajectory(8,tmax=1.0,steps=1000)
    assert np.allclose(P.sum(axis=1),1,atol=1e-10)


def test_dicke_intensity_nonnegative():
    t,P,I=m.dicke_rate_trajectory(8,tmax=1.0,steps=1000)
    assert I.min()>=-1e-12


def test_dicke_peak_superlinear():
    _,_,I4=m.dicke_rate_trajectory(4,tmax=2.0,steps=2000)
    _,_,I12=m.dicke_rate_trajectory(12,tmax=2.0,steps=4000)
    assert I12.max()/I4.max()>3.0
