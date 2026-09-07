import importlib.util
from pathlib import Path
import numpy as np

MODULE=Path(__file__).with_name("ch58_commit633_control.py")
spec=importlib.util.spec_from_file_location("ch58_commit633_control",MODULE)
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)


def test_gate_fidelity_identity():
    assert abs(m.average_gate_fidelity(np.eye(2),np.eye(2))-1)<1e-15


def test_gate_fidelity_global_phase_invariant():
    U=m.rx(np.pi/3)
    assert abs(m.average_gate_fidelity(np.exp(0.7j)*U,U)-1)<1e-15


def test_dqd_energies_symmetric():
    em,ep=m.dqd_energies(np.array([-2,0,2]),0.7)
    assert np.allclose(em,-ep)


def test_dqd_minimum_gap():
    em,ep=m.dqd_energies(np.array([0.0]),0.9)
    assert abs((ep-em)[0]-1.8)<1e-15


def test_dqd_polarization_zero_at_sweet_spot():
    assert abs(m.dqd_ground_polarization([0.0],0.5)[0])<1e-15


def test_transmon_anharmonicity_near_minus_ec():
    EJ,EC=30.0,0.25
    assert abs(m.transmon_anharmonicity(EJ,EC)+EC)<1e-12


def test_unitary_hermitian_is_unitary():
    H=np.array([[1,0.2],[0.2,-0.4]],complex)
    U=m.unitary_from_hermitian(H,0.3)
    assert np.allclose(U.conj().T@U,np.eye(2),atol=1e-13)


def test_arp_probability_bounds():
    p,_,_=m.arp_transfer(beta=0.2,omega=1.0,detuning_span=7.0,steps=2500)
    assert 0<=p<=1


def test_slow_arp_beats_fast_arp():
    pslow,_,_=m.arp_transfer(beta=0.06,omega=1.0,detuning_span=8.0,steps=6000)
    pfast,_,_=m.arp_transfer(beta=1.2,omega=1.0,detuning_span=8.0,steps=3000)
    assert pslow>pfast


def test_primitive_pi_is_x_gate():
    assert m.average_gate_fidelity(m.primitive_x(np.pi),m.rx(np.pi))>1-1e-14


def test_bb1_exact_without_error():
    assert m.average_gate_fidelity(m.bb1(np.pi,0),m.rx(np.pi))>1-1e-13


def test_bb1_improves_moderate_amplitude_error():
    e=0.12
    target=m.rx(np.pi)
    f0=m.average_gate_fidelity(m.primitive_x(np.pi,e),target)
    f1=m.average_gate_fidelity(m.bb1(np.pi,e),target)
    assert f1>f0


def test_corpse_exact_on_resonance():
    target=m.rx(np.pi)
    assert m.average_gate_fidelity(m.corpse_pi(0),target)>1-1e-13


def test_corpse_improves_detuning_error():
    d=0.25
    target=m.rx(np.pi)
    f0=m.average_gate_fidelity(m.primitive_x(np.pi,0,d),target)
    f1=m.average_gate_fidelity(m.corpse_pi(d),target)
    assert f1>f0


def test_bias_modulated_excitation_bounds():
    p=m.bias_modulated_max_excitation(0.8,0.3,0.7,0.8,periods=3,steps_per_period=40)
    assert 0<=p<=1+1e-12


def test_lz_scatter_unitary():
    S=m.lz_scatter(0.37,0.2)
    assert np.allclose(S.conj().T@S,np.eye(2),atol=1e-13)


def test_phase_gate_unitary():
    D=m.phase_gate(1.2)
    assert np.allclose(D.conj().T@D,np.eye(2),atol=1e-14)


def test_stuckelberg_gate_unitary():
    U=m.stuckelberg_gate(0.4,1.1,0.2)
    assert np.allclose(U.conj().T@U,np.eye(2),atol=1e-13)


def test_remove_global_phase_unit_determinant():
    U=np.exp(0.4j)*m.rx(0.7)
    V=m.remove_global_phase(U)
    assert abs(np.linalg.det(V)-1)<1e-12


def test_su2_angle_axis_identity():
    th,n=m.su2_angle_axis(np.eye(2))
    assert abs(th)<1e-12


def test_floquet_operator_unitary():
    U=m.floquet_operator(1.0,0.3,0.9,0.1,500)
    assert np.allclose(U.conj().T@U,np.eye(2),atol=2e-11)


def test_floquet_gap_nonnegative():
    g=m.floquet_quasienergy_gap(1.0,0.3,0.9,0.1,500)
    assert g>=0


def test_floquet_gap_within_zone_width():
    wd=0.9
    g=m.floquet_quasienergy_gap(1.0,0.4,wd,0.1,500)
    assert g<=wd/2+1e-12


def test_floquet_gate_fidelity_bounds():
    target=m.rx(np.pi/2)
    f=m.floquet_gate_fidelity(target,1.0,0.4,0.9,0.1,500)
    assert 1/3-1e-12<=f<=1+1e-12


def test_bb1_high_order_near_zero():
    target=m.rx(np.pi)
    e1=0.02
    e2=0.04
    i1=1-m.average_gate_fidelity(m.bb1(np.pi,e1),target)
    i2=1-m.average_gate_fidelity(m.bb1(np.pi,e2),target)
    assert i2/i1>20


def test_corpse_symmetric_detuning_fidelity():
    target=m.rx(np.pi)
    fp=m.average_gate_fidelity(m.corpse_pi(0.2),target)
    fm=m.average_gate_fidelity(m.corpse_pi(-0.2),target)
    assert abs(fp-fm)<1e-12
