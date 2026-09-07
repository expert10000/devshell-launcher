
import numpy as np
import pytest
from ch60_commit640_open_foundations import *

def test_density_trace_one():
    assert np.trace(density([1,2])).real == pytest.approx(1)
def test_density_pure():
    assert purity(density([1,1j])) == pytest.approx(1)
def test_zero_state_rejected():
    with pytest.raises(ValueError): density([0,0])
def test_bell_reduced_maximally_mixed():
    rho=density(bell_state())
    r=partial_trace_bipartite(rho,(2,2),1)
    assert np.allclose(r, np.eye(2)/2)
def test_bell_entropy_one():
    r=partial_trace_bipartite(density(bell_state()),(2,2),1)
    assert von_neumann_entropy(r)==pytest.approx(1)
def test_schmidt_bell():
    s=schmidt_coefficients(bell_state(),(2,2))
    assert np.allclose(np.sort(s), [1/np.sqrt(2),1/np.sqrt(2)])
def test_amplitude_kraus_complete():
    assert np.allclose(kraus_completeness(amplitude_damping_kraus(.3)),I2)
def test_phase_kraus_complete():
    assert np.allclose(kraus_completeness(phase_damping_kraus(.2)),I2)
def test_depolarizing_kraus_complete():
    assert np.allclose(kraus_completeness(depolarizing_kraus(.4)),I2)
@pytest.mark.parametrize("g",[0,.2,.7,1])
def test_amplitude_damping_excited_population(g):
    rho=np.array([[0,0],[0,1]],complex)
    out=apply_channel(rho,amplitude_damping_kraus(g))
    assert out[1,1].real==pytest.approx(1-g)
def test_amplitude_ground_fixed():
    rho=np.array([[1,0],[0,0]],complex)
    assert np.allclose(apply_channel(rho,amplitude_damping_kraus(.8)),rho)
def test_phase_damping_preserves_populations():
    r=density([1,1])
    o=apply_channel(r,phase_damping_kraus(.4))
    assert o[0,0].real==pytest.approx(.5) and o[1,1].real==pytest.approx(.5)
def test_bloch_vector_ground():
    assert np.allclose(bloch_vector(np.array([[1,0],[0,0]],complex)),[0,0,1])
def test_purification_recovers_density():
    r=np.diag([.7,.3]).astype(complex);p=purification_from_density(r)
    red=partial_trace_bipartite(density(p),(2,2),1)
    assert np.allclose(red,r,atol=1e-12)
def test_dilation_unitary():
    U=unitary_dilation_amplitude_damping(.3)
    assert np.allclose(U.conj().T@U,np.eye(4),atol=1e-12)
def test_trace_distance_identical():
    r=density([1,0]);assert trace_distance(r,r)==pytest.approx(0)
def test_trace_distance_orthogonal():
    assert trace_distance(density([1,0]),density([0,1]))==pytest.approx(1)
def test_population_curve_monotone():
    y=channel_population_curve(np.linspace(0,1,20));assert np.all(np.diff(y)<=1e-12)
def test_coherence_curve_nonnegative():
    y=channel_coherence_curve(np.linspace(0,1,20));assert np.all(y>=0)
