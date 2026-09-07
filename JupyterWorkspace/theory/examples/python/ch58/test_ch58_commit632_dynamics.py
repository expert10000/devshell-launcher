import importlib.util
from pathlib import Path
import numpy as np

MODULE=Path(__file__).with_name("ch58_commit632_dynamics.py")
spec=importlib.util.spec_from_file_location("ch58_commit632_dynamics",MODULE)
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)


def test_pauli_step_unitary():
    U=m.unitary_from_pauli(0.3,-0.1,0.7,0.2)
    assert np.allclose(U.conj().T@U,np.eye(2),atol=1e-13)


def test_pauli_zero_generator_identity():
    assert np.allclose(m.unitary_from_pauli(0,0,0,1.3),np.eye(2))


def test_propagation_norm_conserved():
    times=np.linspace(0,10,2000)
    psi=m.propagate_pauli(times,[1,0],lambda t:(0.4*np.cos(t),0,0.5))
    assert np.allclose(np.sum(np.abs(psi)**2,axis=1),1,atol=2e-12)


def test_lz_probability_bounds():
    p=m.lz_asymptotic_probability(0.5,1.0)
    assert 0<p<1


def test_lz_stronger_coupling_more_adiabatic():
    assert m.lz_asymptotic_probability(0.8,1.0)<m.lz_asymptotic_probability(0.2,1.0)


def test_finite_lz_probability_bounds():
    p,_,_=m.finite_lz_survival(0.4,1.0,6.0,3000)
    assert 0<=p<=1


def test_finite_lz_approaches_asymptotic():
    g,v=0.35,1.0
    p,_,_=m.finite_lz_survival(g,v,12.0,9000)
    assert abs(p-m.lz_asymptotic_probability(g,v))<0.035


def test_lzs_zero_at_zero_phase_zero_stokes():
    assert abs(m.lzs_probability(0.4,0.0,0.0))<1e-15


def test_lzs_maximum_at_half_splitter():
    p=m.lzs_probability(0.5,np.pi,0.0)
    assert abs(p-1.0)<1e-15


def test_lzs_probability_bounds_grid():
    P=np.linspace(0,1,50)[:,None]
    ph=np.linspace(0,4*np.pi,100)[None,:]
    z=m.lzs_probability(P,ph,0.2)
    assert z.min()>=-1e-15 and z.max()<=1+1e-15


def test_rwa_on_resonance_reaches_one():
    t=np.pi/0.4
    assert abs(m.rabi_rwa_probability([t],0.4,0)[0]-1)<1e-14


def test_rwa_detuning_reduces_maximum():
    t=np.linspace(0,50,5000)
    assert m.rabi_rwa_probability(t,0.4,0.5).max()<0.4


def test_driven_exact_norm():
    t,tr=m.driven_trajectory(1.0,0.3,1.0,10,4000)
    assert np.allclose(np.sum(np.abs(tr)**2,axis=1),1,atol=2e-12)


def test_bloch_siegert_zero_at_zero_drive():
    assert m.bloch_siegert_shift(0.0,1.0,1.0)==0


def test_bloch_siegert_quadratic_scaling():
    a=m.bloch_siegert_shift(0.2,1,1)
    b=m.bloch_siegert_shift(0.4,1,1)
    assert abs(b/a-4)<1e-14


def test_floquet_operator_unitary():
    U=m.floquet_operator(1.0,0.3,0.9,1200)
    assert np.allclose(U.conj().T@U,np.eye(2),atol=2e-11)


def test_floquet_two_quasienergies():
    e=m.floquet_quasienergies(1.0,0.2,0.9,1200)
    assert e.shape==(2,)


def test_floquet_quasienergies_inside_zone():
    wd=0.9
    e=m.floquet_quasienergies(1.0,0.4,wd,1000)
    assert np.all(e<=wd/2+1e-12) and np.all(e>=-wd/2-1e-12)


def test_floquet_trace_zero_symmetry():
    e=m.floquet_quasienergies(1.0,0.25,0.8,1200)
    assert abs(e.sum())<1e-10


def test_sambe_matrix_hermitian():
    F=m.sambe_matrix(1.0,0.3,0.9,2)
    assert np.allclose(F,F.conj().T)


def test_sambe_dimension():
    assert m.sambe_matrix(M=3).shape==(14,14)


def test_sambe_no_drive_block_diagonal():
    F=m.sambe_matrix(omega0=1.0,A=0.0,omega_d=0.8,M=1)
    # all inter-sector 2x2 blocks are zero
    assert np.allclose(F[0:2,2:4],0) and np.allclose(F[2:4,4:6],0)


def test_sambe_folded_inside_zone():
    wd=0.8
    e=m.sambe_quasienergies(1.0,0.2,wd,M=2)
    assert np.all(e<wd/2+1e-12) and np.all(e>=-wd/2-1e-12)


def test_weak_drive_exact_close_to_rwa_early():
    A=0.06
    t,tr=m.driven_trajectory(1.0,A,1.0,tmax=10,steps=6000)
    pe=np.abs(tr[:,0])**2
    rwa=m.rabi_rwa_probability(t,A,0)
    assert np.max(np.abs(pe-rwa))<0.035
