import math
import numpy as np
import pytest
from fractional_hall_companion import *

def test_01_magnetic_length_positive(): assert magnetic_length(4)>0
def test_02_magnetic_length_scaling(): assert np.isclose(magnetic_length(4),0.5*magnetic_length(1))
def test_03_magnetic_length_zero_error():
    with pytest.raises(ValueError): magnetic_length(0)
def test_04_coulomb_scale_sqrt_B(): assert np.isclose(coulomb_scale(4),2*coulomb_scale(1))
def test_05_mixing_ratio(): assert np.isclose(landau_mixing_parameter(8,20),.4)
def test_06_mixing_bad_gap():
    with pytest.raises(ValueError): landau_mixing_parameter(1,0)
def test_07_laughlin_flux(): assert laughlin_sphere_flux(12,3)==33
def test_08_even_m_rejected():
    with pytest.raises(ValueError): laughlin_sphere_flux(8,2)
def test_09_sphere_orbitals(): assert sphere_orbitals(33)==34
def test_10_hilbert_dimension(): assert hilbert_dimension(3,5)==10
def test_11_hilbert_bad():
    with pytest.raises(ValueError): hilbert_dimension(6,5)
def test_12_filling_factor(): assert np.isclose(filling_factor(10,30),1/3)
def test_13_pair_power_m1(): assert np.isclose(pair_correlation_short_distance(.5,1),.25)
def test_14_pair_power_m3(): assert np.isclose(pair_correlation_short_distance(.5,3),.5**6)
def test_15_stronger_correlation_hole(): assert pair_correlation_short_distance(.4,3)<pair_correlation_short_distance(.4,1)
def test_16_quasihole_charge(): assert np.isclose(quasihole_charge(3),1/3)
def test_17_braid_phase(): assert np.isclose(full_braid_phase(3),2*math.pi/3)
def test_18_exchange_half_braid(): assert np.isclose(exchange_angle(5),math.pi/5)
def test_19_fractional_hall_conductance(): assert np.isclose(hall_conductance(1/3),1/3)
def test_20_flux_pump(): assert np.isclose(pumped_charge(1/3,3),1)
def test_21_torus_degeneracy(): assert torus_degeneracy(5)==5
def test_22_bundle_response(): assert np.isclose(bundle_response(1,5),.2)
def test_23_uniform_curvature_chern():
    n=100; dtheta=2*math.pi/n; F=np.full((n,n),uniform_trace_curvature(1)); assert np.isclose(chern_from_grid(F,dtheta,dtheta),1)
def test_24_splitting_decays(): assert topological_splitting(8,2)<topological_splitting(2,2)
def test_25_parent_zero_mode(): assert parent_energy([0,0],[1,2])==0
def test_26_parent_positive(): assert parent_energy([.2,.1],[1,2])>0
def test_27_neutral_gap(): assert np.isclose(neutral_gap(1.2,1.27),.07)
def test_28_gap_extrapolation():
    N=np.array([6,8,10,12.]); gaps=.08+.3/N; intercept,_=linear_gap_extrapolation(N,gaps); assert np.isclose(intercept,.08)
def test_29_spectral_flow_shape(): assert spectral_flow_levels(np.linspace(0,1,7),3).shape==(3,7)
def test_30_small_q_q4(): assert np.isclose(small_q_structure_factor(2)/small_q_structure_factor(1),16)
