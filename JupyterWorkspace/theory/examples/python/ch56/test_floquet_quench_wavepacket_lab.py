import numpy as np
import pytest
import floquet_quench_wavepacket_lab as lab


def test_qwz_hermitian():
    H=lab.qwz_hamiltonian(0.31,-0.42,-1.0);assert np.allclose(H,H.conj().T)


def test_hermitian_exponential_unitary():
    U=lab.hermitian_exponential(lab.qwz_hamiltonian(.2,.4,-1),.7);assert np.linalg.norm(U.conj().T@U-np.eye(2))<1e-13


def test_floquet_operator_unitary():
    assert lab.floquet_unitarity_error(m_a=3,m_b=-3,period=.6)<1e-12


def test_floquet_reconstruction():
    assert lab.floquet_reconstruction_error(period=.6)<1e-12

@pytest.mark.parametrize('nk',[15,21,25,31])
def test_floquet_chern_stable(nk):
    assert lab.floquet_band_chern(3,-3,.6,nk)==-1


def test_both_static_halves_are_trivial_regimes():
    # |m|>2 is the trivial QWZ regime for each static half of the drive.
    assert abs(3.0)>2 and abs(-3.0)>2


def test_floquet_zero_gap_open():
    assert lab.floquet_zero_pi_gaps(3,-3,.6,31)['zero_gap']>0.1


def test_floquet_pi_gap_open():
    assert lab.floquet_zero_pi_gaps(3,-3,.6,31)['pi_gap']>6.0

@pytest.mark.parametrize('kxy',[(0,0),(.3,.4),(-1.2,2.0),(2.5,-2.1)])
def test_quasienergies_inside_floquet_zone(kxy):
    e,_=lab.floquet_quasienergies_and_vectors(*kxy,3,-3,.6);assert np.max(np.abs(e))<=np.pi/.6+1e-12


def test_stroboscopic_zero_periods_identity():
    U=lab.floquet_square_pulse_operator(.2,.1);psi=np.array([1,0],complex);assert np.allclose(lab.stroboscopic_state(U,psi,0),psi)


def test_stroboscopic_norm_conserved():
    U=lab.floquet_square_pulse_operator(.2,.1);psi=np.array([1,1j],complex)/np.sqrt(2);out=lab.stroboscopic_state(U,psi,17);assert abs(np.vdot(out,out)-1)<1e-12


def test_stroboscopic_negative_rejected():
    with pytest.raises(ValueError):lab.stroboscopic_state(np.eye(2),np.array([1,0]),-1)


def test_ssh_hermitian():
    H=lab.ssh_hamiltonian(.7,1.4,.6);assert np.allclose(H,H.conj().T)

@pytest.mark.parametrize('k',[0,.5,1.1,2.0,np.pi])
def test_excitation_probability_bounded(k):
    p=lab.post_quench_excitation_probability(k);assert 0<=p<=1+1e-14


def test_quench_excitation_density_reference():
    assert abs(lab.quench_excitation_density(nk=801)-2/7)<2e-12


def test_critical_mode_near_half_excitation():
    d=lab.quench_critical_mode(nk=2001);assert abs(d['excitation_probability']-.5)<1e-3


def test_critical_mode_k_reference():
    d=lab.quench_critical_mode(nk=2001);assert abs(d['k']-2.3813272314210634)<2e-3


def test_critical_time_reference():
    d=lab.quench_critical_mode(nk=2001);assert abs(d['first_critical_time']-1.49594)<3e-3


def test_loschmidt_initial_rate_zero():
    assert lab.loschmidt_rate(0.0,nk=401)<1e-12


def test_loschmidt_rate_enhanced_near_critical_time():
    tc=lab.quench_critical_mode(nk=1501)['first_critical_time'];assert lab.loschmidt_rate(tc,nk=601)>0.7

@pytest.mark.parametrize('t',[0,.4,1.0,2.2])
def test_loschmidt_amplitude_bounded(t):
    assert abs(lab.loschmidt_amplitude(1.2,t))<=1+1e-12


def test_chain_hamiltonian_hermitian():
    H=lab.chain_hamiltonian(31,1,2,3);assert np.allclose(H,H.conj().T)


def test_delta_packet_normalized():
    assert abs(np.linalg.norm(lab.delta_packet(31))-1)<1e-14


def test_delta_packet_bad_site_rejected():
    with pytest.raises(ValueError):lab.delta_packet(10,11)

@pytest.mark.parametrize('t,expected',[(1,2),(2,8),(3,18),(4,32),(5,50)])
def test_clean_ballistic_variance_exact(t,expected):
    H=lab.chain_hamiltonian(101);psi=lab.evolve_state(H,lab.delta_packet(101),t);d=lab.packet_diagnostics(psi);assert abs(d['variance']-expected)<1e-10


def test_clean_packet_center_fixed():
    H=lab.chain_hamiltonian(101);d=lab.packet_diagnostics(lab.evolve_state(H,lab.delta_packet(101),5));assert abs(d['mean']-50)<1e-12


def test_clean_packet_norm_conserved():
    H=lab.chain_hamiltonian(101);d=lab.packet_diagnostics(lab.evolve_state(H,lab.delta_packet(101),5));assert abs(d['norm']-1)<1e-12


def test_clean_spreading_exponent_two():
    ts=np.array([1,2,3,4,5],float);vs=np.array([2,8,18,32,50],float);assert abs(lab.spreading_exponent(ts,vs)-2)<1e-12


def test_disorder_suppresses_t8_spreading():
    dis=lab.disorder_packet_ensemble(8,81,1,4,range(5));assert dis['mean_variance']<30


def test_disorder_ipr_positive():
    dis=lab.disorder_packet_ensemble(8,81,1,4,range(5));assert dis['mean_ipr']>0.1

@pytest.mark.parametrize('seed',[0,1,2,3])
def test_disordered_packet_norm_conserved(seed):
    H=lab.chain_hamiltonian(51,1,4,seed);d=lab.packet_diagnostics(lab.evolve_state(H,lab.delta_packet(51),3));assert abs(d['norm']-1)<1e-12


def test_qwz_open_hermitian():
    H=lab.qwz_open_hamiltonian(4,-1);assert np.allclose(H,H.conj().T)


def test_half_projector_idempotent():
    P=lab.half_filled_projector(lab.qwz_open_hamiltonian(4,3));assert np.linalg.norm(P@P-P)<1e-12


def test_evolved_projector_idempotent():
    H0=lab.qwz_open_hamiltonian(4,3);H1=lab.qwz_open_hamiltonian(4,-1);P=lab.evolve_projector(lab.half_filled_projector(H0),H1,1);assert np.linalg.norm(P@P-P)<1e-12


def test_quench_local_marker_total_compensates():
    d=lab.quench_local_marker(5,3,-1,1,1);assert abs(d['total_marker'])<1e-10


def test_quench_local_marker_bulk_transient():
    d=lab.quench_local_marker(5,3,-1,1,1);assert -0.5<d['bulk_marker']<-0.2


def test_quench_projector_error_small():
    assert lab.quench_local_marker(5,3,-1,1,1)['projector_error']<1e-12

@pytest.mark.parametrize('t',[0,.5,1,2,3])
def test_closed_state_chern_conserved_zero(t):
    assert lab.quench_state_chern(3,-1,t,19)==0


def test_reference_summary():
    r=lab.reference_summary();assert r['floquet_chern_trivial_halves']==-1 and r['closed_state_chern_t2']==0 and abs(r['clean_spreading_exponent']-2)<1e-12
