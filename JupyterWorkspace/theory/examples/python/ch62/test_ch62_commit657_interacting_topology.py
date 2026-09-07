import numpy as np
from interacting_topology import *
def test_berry_phase_range():
 x=many_body_berry_phase(np.linspace(0,2*np.pi,20)); assert np.all((x>=0)&(x<2*np.pi+1e-12))
def test_chern_converges():
 n=np.array([4.,16.,64.]); c=many_body_chern_convergence(n); assert np.all(np.diff(c)>0) and c[-1]>.999
def test_resta_range():
 p=resta_polarization(np.linspace(-2,2,20)); assert np.all((p>=0)&(p<=.5))
def test_entanglement_shape(): assert entanglement_levels(np.array([0.,1.])).shape==(2,4)
def test_flux_branches_shape(): assert flux_spectral_branches(np.linspace(0,1,5)).shape==(5,4)
def test_multiplet_splitting_decreases():
 x=multiplet_splitting(np.array([4.,8.,16.])); assert np.all(np.diff(x)<0)
def test_fractional_charge_integrates():
 x=np.linspace(-8,8,1000); q=fractional_charge_profile(x); assert abs(np.trapezoid(q,x)-1/3)<1e-4
def test_interaction_gap_positive(): assert np.all(interaction_gap(np.linspace(0,4,20))>0)
def test_many_body_invariant_range():
 x=many_body_invariant(np.linspace(0,4,20)); assert np.all((x>=0)&(x<=1))
