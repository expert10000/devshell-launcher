import numpy as np
from open_system_control import *
def test_fid_initial(): assert gaussian_ou_coherence(0,"FID")==1
def test_echo_improves_late(): assert gaussian_ou_coherence(4,"HAHN")>gaussian_ou_coherence(4,"FID")
def test_cpmg_improves_late(): assert gaussian_ou_coherence(4,"CPMG")>gaussian_ou_coherence(4,"HAHN")
def test_filter_nonnegative(): assert np.all(filter_function([1,2],4,"XY8")>=0)
def test_xy8_has_eight_pulses(): assert len(pulse_times("XY8",4))==8
def test_finite_width_scan_shape(): assert finite_width_scan([0,.1,.2]).shape==(3,)
def test_feedback_shapes():
    t=np.linspace(0,2,200); a,b,c=feedback_rabi_trajectory(t); assert a.shape==b.shape==c.shape
def test_dark_state_monotone():
    f=dark_state_fidelity(np.linspace(0,5,50)); assert np.all(np.diff(f)>=0) and f[-1]>.98
def test_prep_improves_with_kappa():
    f=dissipative_prep_fidelity(np.array([.2,2,10]),.1,.3); assert np.all(np.diff(f)>0)
def test_liouvillian_has_zero_mode():
    vals=np.linalg.eigvals(engineered_jump_liouvillian()); assert np.min(np.abs(vals))<1e-10
def test_liouvillian_stable():
    vals=np.linalg.eigvals(engineered_jump_liouvillian()); assert np.max(vals.real)<1e-10
def test_pareto_ranges():
    a,b,c=pareto_curve(np.linspace(0,4,20)); assert np.all((a>=0)&(a<=1)&(b>=0)&(b<=1)&(c>=0)&(c<=1))
