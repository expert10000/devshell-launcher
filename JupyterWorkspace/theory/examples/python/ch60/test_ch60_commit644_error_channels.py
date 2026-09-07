import numpy as np
from error_channels import *
def test_pauli_trace():
    rho=np.array([[1,0],[0,0]],complex); out=pauli_channel(rho,[.9,.05,.03,.02]); assert np.isclose(np.trace(out),1)
def test_ent_fid_identity_weight(): assert entanglement_fidelity_pauli([.97,.01,.01,.01])==.97
def test_avg_gate_fidelity(): assert np.isclose(average_gate_fidelity_from_entanglement(1),1)
def test_compose_normalized(): assert np.isclose(compose_pauli(np.array([.9,.1,0,0]),np.array([.8,.2,0,0])).sum(),1)
def test_repeated_error_grows():
    d=np.arange(1,20); e=repeated_depolarizing_error(.01,d); assert np.all(np.diff(e)>0)
def test_correlated_dfs_slower():
    c,d=correlated_dephasing_density(np.array([2.]),rho_c=.9); assert d[0]>c[0]
def test_collective_dark_rate(): assert collective_decay_rates()["antisymmetric"]==0
def test_psd_positive(): assert np.all(lorentzian_psd(np.logspace(-2,2,20))>0)
def test_echo_longer_than_ramsey(): assert echo_coherence(np.array([2.]))[0]>ramsey_coherence(np.array([2.]))[0]
def test_zne_recovers_intercept():
    s=np.array([1.,2.,3.]); y=.8-.1*s; assert abs(zne_extrapolate(s,y)-.8)<1e-10
def test_pec_overhead_one_at_zero(): assert pec_sampling_overhead(0,10)==1
def test_fisher_has_interior_maximum():
    t=np.linspace(0,5,400); f=dephasing_fisher_information(t,T2=1); assert 0<np.argmax(f)<len(f)-1
def test_t2_formula():
    _,T2=t1_t2_limited_coherence(np.array([0,1]),2,4); assert np.isclose(T2,2)
def test_diamond_pauli_identity(): assert diamond_upper_bound_pauli([1,0,0,0])==0
