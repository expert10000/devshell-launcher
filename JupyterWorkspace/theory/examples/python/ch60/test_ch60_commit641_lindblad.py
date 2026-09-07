
import numpy as np, pytest
from ch60_commit641_lindblad import *

def rho1():return np.array([[0,0],[0,1]],complex)
def rhop():return np.array([[.5,.5],[.5,.5]],complex)

def test_superoperator_shape():assert amplitude_damping_liouvillian(.2).shape==(4,4)
def test_trace_preservation():assert trace_preservation_residual(amplitude_damping_liouvillian(.2))<1e-12
def test_amplitude_population_exponential():
    r=evolve_liouvillian(rho1(),amplitude_damping_liouvillian(.4),2)
    assert r[1,1].real==pytest.approx(np.exp(-.8),rel=1e-10)
def test_amplitude_trace_one():
    r=evolve_liouvillian(rho1(),amplitude_damping_liouvillian(.4),2);assert np.trace(r).real==pytest.approx(1)
def test_dephasing_populations_fixed():
    r=evolve_liouvillian(rhop(),dephasing_liouvillian(.3),2);assert r[0,0].real==pytest.approx(.5)
def test_dephasing_coherence():
    r=evolve_liouvillian(rhop(),dephasing_liouvillian(.3),2);assert abs(r[0,1])==pytest.approx(.5*np.exp(-.6),rel=1e-10)
def test_t1():assert t1_from_rate(.25)==pytest.approx(4)
def test_t2_relation():assert t2_from_rates(.2,.1)==pytest.approx(5)
def test_t2_infinite_without_noise():assert np.isinf(t2_from_rates(0,0))
def test_thermal_detailed_balance():
    gd,gu=thermal_rates(.4,2);assert gu/gd==pytest.approx(np.exp(-2))
def test_thermal_steady_state_trace():
    r=steady_state(thermal_liouvillian(.3,1.5));assert np.trace(r).real==pytest.approx(1)
def test_thermal_excited_ratio():
    r=steady_state(thermal_liouvillian(.3,1.5))
    assert r[1,1].real/r[0,0].real==pytest.approx(np.exp(-1.5),rel=1e-8)
def test_driven_steady_state_positive():
    r=steady_state(driven_qubit_liouvillian(1,.2,.3,.1));assert positivity_min_eigenvalue(r)>-1e-10
def test_liouvillian_has_zero_mode():
    e=liouvillian_eigenvalues(amplitude_damping_liouvillian(.3));assert np.min(np.abs(e))<1e-10
def test_liouvillian_gap_positive():assert liouvillian_gap(amplitude_damping_liouvillian(.3))>0
def test_purity_bounds():
    r=steady_state(driven_qubit_liouvillian(1,0,.3,.1));assert .5-1e-10<=purity(r)<=1+1e-10
def test_bloch_ground():assert np.allclose(bloch(np.array([[1,0],[0,0]],complex)),[0,0,1])
def test_markov_monotone():
    y=markov_population(.3,np.linspace(0,5,30));assert np.all(np.diff(y)<=0)
def test_exact_exchange_revival():
    t=np.array([0,np.pi/2,np.pi]);y=exact_exchange_population(1,t);assert y[0]==pytest.approx(1) and y[1]<1e-12 and y[2]==pytest.approx(1)
@pytest.mark.parametrize("g",[.05,.2,.8])
def test_cp_example_evolution_positive(g):
    r=evolve_liouvillian(rhop(),amplitude_damping_liouvillian(g),1.3);assert positivity_min_eigenvalue(r)>-1e-10
