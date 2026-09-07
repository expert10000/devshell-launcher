import numpy as np
from tensor_network_diagnostics import *
def test_probabilities_normalized(): assert np.isclose(schmidt_probabilities().sum(),1)
def test_discarded_decreases(): assert discarded_weight(16)<discarded_weight(8)
def test_entropy_bound_grows(): assert entropy_bound(32)>entropy_bound(8)
def test_mps_params_polynomial(): assert mps_parameter_count(20,chi=16)<full_state_dimension(20)
def test_variational_error_decreases():
 x=variational_energy_error(np.array([8.,16.,32.])); assert np.all(np.diff(x)<0)
def test_sweep_error_decreases():
 x=dmrg_sweep_energy_error(np.arange(8)); assert np.all(np.diff(x)<0)
def test_exact_mps_reconstruction():
 rng=np.random.default_rng(1); psi=rng.normal(size=64)+1j*rng.normal(size=64); psi/=np.linalg.norm(psi)
 A,disc=state_to_mps(psi,6); rec=mps_to_state(A); assert disc<1e-12 and normalized_fidelity(psi,rec)>1-1e-10
def test_truncation_fidelity_bounded():
 rng=np.random.default_rng(2); psi=rng.normal(size=64); A,disc=state_to_mps(psi,6,max_bond=2); rec=mps_to_state(A); assert 0<=normalized_fidelity(psi,rec)<=1 and disc>=0
def test_correlation_nonnegative(): assert np.all(correlation_profile(np.arange(10),8)>=0)
