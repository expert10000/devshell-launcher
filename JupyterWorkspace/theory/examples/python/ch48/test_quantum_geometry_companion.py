import numpy as np
import pytest
from quantum_geometry_companion import *

def test_01_two_level_metric_positive():
    gxx,gyy,gxy,f=two_level_lower_geometry(.3,.4,1.2); assert gxx>0 and gyy>0 and metric_determinant(gxx,gyy,gxy)>0

def test_02_two_level_determinant_saturation():
    gxx,gyy,gxy,f=two_level_lower_geometry(.3,.4,1.2); assert determinant_bound_margin(gxx,gyy,gxy,f)==pytest.approx(0,abs=1e-14)

def test_03_curvature_changes_sign_with_mass():
    assert two_level_lower_geometry(.2,.5,1)[3]==pytest.approx(-two_level_lower_geometry(.2,.5,-1)[3])

def test_04_metric_is_even_in_mass():
    assert np.allclose(two_level_lower_geometry(.2,.5,1)[:3],two_level_lower_geometry(.2,.5,-1)[:3])

def test_05_trace_bound_nonnegative():
    gxx,gyy,gxy,f=two_level_lower_geometry(.9,.1,.7); assert trace_bound_margin(gxx,gyy,f)>=-1e-14

def test_06_integrated_metric_bound_c2(): assert integrated_metric_lower_bound(2)==pytest.approx(4*np.pi)

def test_07_lll_form_factor_at_zero(): assert landau_form_factor(0,0.0)==pytest.approx(1)

def test_08_first_ll_zero(): assert landau_form_factor(1,np.sqrt(2.0))==pytest.approx(0,abs=1e-14)

def test_09_lll_form_factor_decays(): assert landau_form_factor(0,2.0)<landau_form_factor(0,1.0)<1

def test_10_laguerre_n2_origin(): assert laguerre(2,0.0)==pytest.approx(1)

def test_11_gmp_parallel_zero(): assert gmp_coefficient([1,0],[2,0])==pytest.approx(0)

def test_12_gmp_antisymmetry(): assert gmp_coefficient([.4,.1],[-.2,.7])==pytest.approx(-gmp_coefficient([-.2,.7],[.4,.1]))

def test_13_gmp_small_q_linear_limit():
    q=np.array([1e-3,0]); qp=np.array([0,2e-3]); assert gmp_coefficient(q,qp)==pytest.approx(gmp_linear_coefficient(q,qp),rel=1e-10)

def test_14_gmp_scales_with_ell_squared_at_small_q():
    q=[1e-4,0]; qp=[0,2e-4]; assert gmp_linear_coefficient(q,qp,2)==pytest.approx(4*gmp_linear_coefficient(q,qp,1))

def test_15_uniform_fluctuation_zero(): assert normalized_rms_fluctuation(np.ones(8))==pytest.approx(0)

def test_16_nonuniform_fluctuation_positive(): assert normalized_rms_fluctuation([1,2,1,2])>0

def test_17_geometry_quality_pair(): assert geometry_quality([1,1,1],[2,2,2])==(pytest.approx(0),pytest.approx(0))

def test_18_fci_hierarchy_good(): assert fci_projection_hierarchy(.4,8,80)[2]

def test_19_fci_hierarchy_rejects_large_width(): assert not fci_projection_hierarchy(4,8,80)[2]

def test_20_fci_hierarchy_rejects_band_mixing(): assert not fci_projection_hierarchy(.4,8,20)[2]

def test_21_fractional_response_one_third(): assert fractional_hall_response(1,3)==pytest.approx(1/3)

def test_22_fractional_response_two_fifths(): assert fractional_hall_response(2,5)==pytest.approx(2/5)

def test_23_mean_orbital_spin_from_shift(): assert mean_orbital_spin(3)==pytest.approx(1.5)

def test_24_hall_viscosity_laughlin_third(): assert hall_viscosity(2,3)==pytest.approx(1.5)

def test_25_sphere_flux_laughlin_third(): assert sphere_flux(10,1/3,3)==pytest.approx(27)

def test_26_wen_zee_sphere_inverts_flux_count(): assert wen_zee_particle_number(1/3,27,3,2)==pytest.approx(10)

def test_27_guiding_center_spin_laughlin_third(): assert guiding_center_spin(3)==pytest.approx(-1)

def test_28_structure_factor_bound_laughlin_third(): assert structure_factor_s4_bound(3)==pytest.approx(.25)

def test_29_projected_structure_factor_q4_scaling(): assert projected_structure_factor_leading(.2,.25)==pytest.approx(16*projected_structure_factor_leading(.1,.25))

def test_30_zero_q_projected_structure_factor(): assert projected_structure_factor_leading(0,.25)==pytest.approx(0)
