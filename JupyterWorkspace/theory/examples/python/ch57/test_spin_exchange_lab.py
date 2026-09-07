import numpy as np
import spin_exchange_lab as lab

def test_pauli_hermitian():
    for s in lab.PAULI: assert np.allclose(s,s.conj().T)
def test_pauli_squared_identity():
    for s in lab.PAULI: assert np.allclose(s@s,lab.I2)
def test_spin_hamiltonian_hermitian():
    H=lab.spin_hamiltonian([0.2,-0.4,0.7],gamma=-1.3);assert np.allclose(H,H.conj().T)
def test_zeeman_z_energies(): assert np.allclose(lab.zeeman_energies([0,0,2],gamma=1.5),[-1.5,1.5])
def test_zeeman_gap_is_abs_gamma_b():
    e=lab.zeeman_energies([1,2,2],gamma=-2);assert np.isclose(e[1]-e[0],6.0)
def test_larmor_frequency(): assert np.isclose(lab.larmor_frequency([0,3,4],gamma=-2),10.0)
def test_zero_field_unitary_identity(): assert np.allclose(lab.spin_unitary([0,0,0],7,gamma=2),lab.I2)
def test_spin_unitary_is_unitary():
    U=lab.spin_unitary([0.2,0.3,0.7],1.2,gamma=-0.9);assert np.allclose(U.conj().T@U,lab.I2,atol=1e-13)
def test_up_state_bloch_vector(): assert np.allclose(lab.bloch_vector(lab.UP),[0,0,1])
def test_x_plus_state_bloch_vector():
    psi=(lab.UP+lab.DOWN)/np.sqrt(2);assert np.allclose(lab.bloch_vector(psi),[1,0,0],atol=1e-13)
def test_larmor_rotation_preserves_bloch_norm():
    psi=(lab.UP+lab.DOWN)/np.sqrt(2);p=lab.evolve_spinor(psi,[0,0,1],2.3,gamma=1.7);assert np.isclose(np.linalg.norm(lab.bloch_vector(p)),1,atol=1e-13)
def test_resonance_detuning_zero(): assert np.isclose(lab.resonance_detuning(6,3,gamma=-2),0)
def test_two_spin_operator_dimensions():
    assert lab.two_spin_operator(lab.SX,1).shape==(4,4);assert lab.two_spin_operator(lab.SX,2).shape==(4,4)
def test_spin1_spin2_commute():
    a=lab.two_spin_operator(lab.SX,1);b=lab.two_spin_operator(lab.SY,2);assert np.allclose(a@b,b@a)
def test_singlet_normalized():
    s=lab.singlet_triplet_states()['S'];assert np.isclose(np.vdot(s,s),1)
def test_triplets_orthonormal():
    st=lab.singlet_triplet_states();T=np.column_stack([st['T+'],st['T0'],st['T-']]);assert np.allclose(T.conj().T@T,np.eye(3))
def test_singlet_orthogonal_to_triplets():
    st=lab.singlet_triplet_states();assert all(abs(np.vdot(st['S'],st[k]))<1e-14 for k in ['T+','T0','T-'])
def test_total_spin_squared_singlet_zero():
    s=lab.singlet_triplet_states()['S'];assert abs(np.vdot(s,lab.total_spin_squared()@s))<1e-13
def test_total_spin_squared_triplet_two():
    t=lab.singlet_triplet_states()['T0'];assert np.isclose(np.real(np.vdot(t,lab.total_spin_squared()@t)),2)
def test_exchange_hamiltonian_spectrum_antiferromagnetic():
    e=np.linalg.eigvalsh(lab.exchange_hamiltonian(0.8));assert np.allclose(e,[-0.6,0.2,0.2,0.2])
def test_exchange_gap_signed():
    assert np.isclose(lab.exchange_gap(0.8),0.8);assert np.isclose(lab.exchange_gap(-0.8),-0.8)
def test_swap_eigenvalue_singlet_minus_one():
    s=lab.singlet_triplet_states()['S'];assert np.allclose(lab.swap_operator()@s,-s)
def test_swap_eigenvalue_triplet_plus_one():
    t=lab.singlet_triplet_states()['T0'];assert np.allclose(lab.swap_operator()@t,t)
def test_singlet_triplet_projectors_close_identity():
    Ps=lab.singlet_projector();Pt=lab.triplet_projector();assert np.allclose(Ps+Pt,np.eye(4));assert np.allclose(Ps@Ps,Ps);assert np.allclose(Pt@Pt,Pt)
