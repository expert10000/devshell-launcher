
import numpy as np, pytest
from ch60_commit642_trajectories_nonmarkov import *

def test_effective_nonhermitian_has_loss():
    H=effective_nonhermitian(np.zeros((2,2),complex),[np.sqrt(.3)*SM])
    assert H[1,1].imag<0
def test_jump_prob_excited():
    p=jump_probabilities(np.array([0,1],complex),[np.sqrt(.4)*SM],.1)
    assert p[0]==pytest.approx(.04)
def test_jump_prob_ground_zero():
    p=jump_probabilities(np.array([1,0],complex),[np.sqrt(.4)*SM],.1)
    assert p[0]==pytest.approx(0)
def test_trajectory_normalized():
    st,_=quantum_jump_trajectory(np.zeros((2,2)),[np.sqrt(.5)*SM],[0,1],.01,200,2)
    assert np.allclose(np.linalg.norm(st,axis=1),1)
def test_ground_no_jumps():
    _,log=quantum_jump_trajectory(np.zeros((2,2)),[np.sqrt(.5)*SM],[1,0],.01,100,2)
    assert len(log)==0
def test_ensemble_amplitude_damping_reasonable():
    avg=trajectory_density_average(np.zeros((2,2)),[np.sqrt(.5)*SM],[0,1],.01,100,ntraj=1200,seed=4)
    target=np.exp(-.5)
    assert avg[-1,1,1].real==pytest.approx(target,abs=.05)
def test_waiting_time_mean():
    w=waiting_times(2,20000,3);assert np.mean(w)==pytest.approx(.5,abs=.02)
def test_zeno_increases_with_measurements():
    assert projective_zeno_survival(1,2,100)>projective_zeno_survival(1,2,2)
def test_zeno_limit_high():assert projective_zeno_survival(1,1,1000)>.999
def test_weak_measurement_probabilities_sum():
    r=density([1,1]);_,p0=weak_z_measurement(r,.4,0);_,p1=weak_z_measurement(r,.4,1);assert p0+p1==pytest.approx(1)
def test_weak_measurement_state_trace():
    r=density([1,1]);o,p=weak_z_measurement(r,.6,0);assert np.trace(o).real==pytest.approx(1) and p>0
def test_rate_can_be_negative():
    t=np.linspace(0,10,1000);assert np.min(time_local_rate(t,.3,1.8,1.2))<0
def test_trace_distance_initial_one():
    assert dephasing_trace_distance(np.array([0.]))[0]==pytest.approx(1)
def test_backflow_positive_for_negative_rate_model():
    t=np.linspace(0,18,3000);D=dephasing_trace_distance(t,.3,1.8,1.2);assert backflow_measure(D)>0
def test_markov_backflow_zero():
    t=np.linspace(0,10,1000);D=dephasing_trace_distance(t,.3,0,1.2);assert backflow_measure(D)==pytest.approx(0)
def test_structured_population_initial_one():
    assert structured_reservoir_population(np.array([0.]),1,.2)[0]==pytest.approx(1)
def test_structured_population_nonnegative():
    y=structured_reservoir_population(np.linspace(0,20,300),1,.2);assert np.all(y>=0)
def test_structured_revival_present():
    y=structured_reservoir_population(np.linspace(0,30,3000),1,.05);dy=np.diff(y);assert np.any(dy>1e-4)
def test_memory_kernel_initial():assert memory_kernel_exponential(np.array([0.]),.4)[0]==pytest.approx(.4)
def test_no_jump_norm_monotone():
    y=no_jump_norm_proxy(.3,np.linspace(0,5,50));assert np.all(np.diff(y)<=0)
def test_poisson_mean():
    x=photon_count_histogram(.7,3,20000,2);assert np.mean(x)==pytest.approx(2.1,abs=.05)
