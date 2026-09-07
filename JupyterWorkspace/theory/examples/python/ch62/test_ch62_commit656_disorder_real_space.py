import numpy as np
from disorder_real_space_topology import *
def test_qwz_realspace_hermitian():
 H=qwz_realspace(3,-1,1,seed=1); assert np.allclose(H,H.conj().T)
def test_projector_properties():
 P,e,v=occupied_projector(qwz_realspace(3,-1,0)); assert np.allclose(P,P.conj().T) and np.allclose(P@P,P)
def test_ipr_bounds():
 x=np.ones(10)/np.sqrt(10); assert 0<ipr(x)<=1
def test_extended_ipr():
 x=np.ones(20)/np.sqrt(20); assert np.isclose(ipr(x),1/20)
def test_bott_finite(): assert np.isfinite(bott_index(qwz_realspace(3,-1,0),3))
def test_marker_shape(): assert local_chern_marker_proxy(8).shape==(8,8)
def test_hall_nonnegative(): assert np.all(hall_plateau(np.linspace(-2,2,20))>=0)
def test_anderson_indicator_binary(): assert set(np.unique(topological_anderson_indicator(np.array([-1.,1.]),np.array([0.,2.])))).issubset({0.,1.})
def test_localization_length_positive(): assert np.all(localization_length_proxy(np.array([0.,2.]),10)>0)
