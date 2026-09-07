import numpy as np
import pytest
from correlated_matter_companion import *


def test_01_scaling_variable_zero(): assert critical_scaling_variable(0.0,16,0.7)==pytest.approx(0)
def test_02_scaling_variable_size_growth(): assert critical_scaling_variable(.1,16,.5)>critical_scaling_variable(.1,4,.5)
def test_03_irrelevant_correction_decays(): assert abs(correction_aware_observable(0,64,1,1)-0)<abs(correction_aware_observable(0,4,1,1)-0)
def test_04_rg_relevant_grows(): assert linear_rg_flow(1,1,2)>linear_rg_flow(1,1,0)
def test_05_rg_irrelevant_decays(): assert linear_rg_flow(1,-1,2)<linear_rg_flow(1,-1,0)
def test_06_rg_classification(): assert [classify_rg_direction(x) for x in (1,-1,0)]==['relevant','irrelevant','marginal']
def test_07_green_topological_reconstruction():
    h=np.diag([-2.,3.]); g=green_zero_frequency_from_hamiltonian(h); assert np.allclose(topological_hamiltonian_from_green(g),h)
def test_08_green_rejects_nonsquare():
    with pytest.raises(ValueError): green_zero_frequency_from_hamiltonian(np.ones((2,3)))
def test_09_inverse_condition_number_identity(): assert inverse_condition_number(np.eye(3))==pytest.approx(1)
def test_10_z2_loop_even_negative_links(): assert z2_wilson_loop([-1,-1,1,1])==1
def test_11_z2_loop_odd_negative_links(): assert z2_wilson_loop([-1,1,1])==-1
def test_12_area_law_origin(): assert area_law_wilson(0,0.3)==pytest.approx(1)
def test_13_area_law_decays(): assert area_law_wilson(3,.4)<area_law_wilson(1,.4)
def test_14_fit_string_tension():
    a=np.arange(1,7.); w=area_law_wilson(a,.37); assert fit_string_tension(a,w)==pytest.approx(.37,rel=1e-10)
def test_15_nonfermi_zero(): assert nonfermi_self_energy(0)==pytest.approx(0j)
def test_16_nonfermi_power_ratio(): assert abs(nonfermi_self_energy(8).imag/ nonfermi_self_energy(1).imag)==pytest.approx(4)
def test_17_quasiparticle_ratio_diverges_low_frequency(): assert quasiparticle_decay_ratio(1e-6)>quasiparticle_decay_ratio(1e-2)
def test_18_omega_t_variable(): assert omega_t_variable(6,3)==pytest.approx(2)
def test_19_omega_t_collapse():
    for T in (1.,2.,5.):
        w=1.5*T; scaled=T**.5*omega_t_response(w,T,.5); assert scaled==pytest.approx(1/(1+1.5**2))
def test_20_planckian_linear_temperature(): assert planckian_rate(200)==pytest.approx(2*planckian_rate(100))
def test_21_dwave_nodes(): assert nodal_gap(np.pi/4)==pytest.approx(0,abs=1e-14)
def test_22_dwave_antinode(): assert nodal_gap(0)==pytest.approx(1)
def test_23_dirac_dos_zero(): assert dirac_density_of_states(0,2,3)==pytest.approx(0)
def test_24_dirac_dos_linear(): assert dirac_density_of_states(2,2,3)==pytest.approx(2*dirac_density_of_states(1,2,3))
def test_25_moire_small_angle_approximation():
    a=1.; th=.01; assert moire_length(a,th)==pytest.approx(a/th,rel=1e-5)
def test_26_moire_hierarchy_good(): assert moire_projection_hierarchy(1,10,100)[2]
def test_27_moire_hierarchy_rejects_mixing(): assert not moire_projection_hierarchy(1,10,20)[2]
def test_28_floquet_time_grows_with_frequency(): assert floquet_prethermal_time(8,1)>floquet_prethermal_time(4,1)
def test_29_floquet_time_positive(): assert floquet_prethermal_time(2,3)>0
def test_30_pairing_eigenpair():
    val,vec=leading_pairing_eigenpair(np.array([[-2.,0.],[0.,1.]])); assert val==pytest.approx(2) and abs(vec[0])==pytest.approx(1)
