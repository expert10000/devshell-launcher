import numpy as np
from crystalline_higher_order import *
def test_inversion_polarization_range():
 x=inversion_polarization(np.linspace(-1,1,20)); assert np.all((x>=0)&(x<=.5))
def test_wannier_center_range():
 x=wannier_center_flow(np.linspace(0,1,50)); assert np.all((x>=0)&(x<1))
def test_parity_quantized(): assert set(parity_indicator(np.array([-1.,1.])))=={-1,1}
def test_bbh_gap_closes(): assert np.isclose(bbh_bulk_gap(1,1),0)
def test_corner_density_normalized(): assert np.isclose(bbh_corner_density(10).sum(),1)
def test_corner_density_corner_dominant():
 d=bbh_corner_density(12); assert d[0,0]>d[6,6]
def test_quadrupole_quantized(): assert set(quadrupole_invariant(np.array([.5,1.5])))=={0.0,.5}
def test_symmetry_breaking_larger_splitting(): assert corner_mode_splitting(.5,True)>corner_mode_splitting(.5,False)
