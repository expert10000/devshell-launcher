import numpy as np
from many_body_diagnostics import *
def test_double_range(): assert 0<=double_occupancy(2)<=1
def test_attraction_double(): assert double_occupancy(-6)>double_occupancy(6)
def test_bose_var(): assert bose_number_variance(2)>=0
def test_gap_shapes():
 a,b,c=finite_gap_schematic(np.array([0.,1.])); assert a.shape==b.shape==c.shape==(2,)
def test_structure_range():
 x=structure_factor_proxy(np.linspace(-5,5,20)); assert np.all((x>=0)&(x<=1))
def test_entropy_nonnegative(): assert np.all(entanglement_entropy_proxy(np.linspace(-5,5,20))>=0)
def test_fidelity_peak():
 U=np.linspace(-2,3,300); x=fidelity_susceptibility_proxy(U); assert abs(U[np.argmax(x)]-.5)<.03
def test_gap_decreases(): assert np.all(np.diff(finite_size_gap(np.arange(4,20),True))<0)
def test_symmetry_reduces():
 a,b,c,d=symmetry_block_dimensions(6); assert a>=b>=c>=d
def test_pair_decay(): assert np.all(np.diff(pair_correlation_distance(np.arange(10)))<0)
def test_sector_smaller(): assert ed_dimension(12,6)<ed_dimension(12)
