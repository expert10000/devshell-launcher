import math
import numpy as np
from qft_companion import *

def test_01_rel_energy_rest(): assert relativistic_energy(0,2)==2

def test_02_rel_energy_345(): assert np.isclose(relativistic_energy(3,4),5)

def test_03_rel_energy_array(): assert np.allclose(relativistic_energy([0,3],4),[4,5])

def test_04_bose_positive(): assert bose_occupation(2,1)>0

def test_05_bose_low_t(): assert bose_occupation(5,0.5)<1e-3

def test_06_fermi_half(): assert np.isclose(fermi_occupation(1,2,mu=1),0.5)

def test_07_fermi_bounds(): assert 0<fermi_occupation(2,1)<1

def test_08_scalar_prop_complex(): assert np.iscomplexobj(scalar_propagator(2,0,1))

def test_09_scalar_prop_sign(): assert scalar_propagator(0,0,1).real<0

def test_10_dirac_denominator(): assert dirac_scalar_denominator(2,0,1)==scalar_propagator(2,0,1)

def test_11_yukawa_decay(): assert equal_time_yukawa_correlation(2,1)<equal_time_yukawa_correlation(1,1)

def test_12_yukawa_positive(): assert equal_time_yukawa_correlation(1,2)>0

def test_13_dyson_order0(): assert dyson_exponential_partial(3,2,0)==1

def test_14_dyson_converges(): assert abs(dyson_exponential_partial(.2,.3,8)-np.exp(-1j*.06))<1e-12

def test_15_wick_zero(): assert wick_pairing_count(0)==1

def test_16_wick_four(): assert wick_pairing_count(4)==3

def test_17_wick_six(): assert wick_pairing_count(6)==15

def test_18_wick_odd(): assert wick_pairing_count(5)==0

def test_19_phi4_amp(): assert phi4_tree_amplitude(.7)==-.7

def test_20_kallen_equal(): assert np.isclose(kallen(4,1,1),0)

def test_21_cm_threshold(): assert two_body_cm_momentum(4,1,1)==0

def test_22_cm_massless(): assert np.isclose(two_body_cm_momentum(100,0,0),5)

def test_23_phase_space_positive(): assert two_body_phase_space(100,1,1)>0

def test_24_interval_timelike(): assert invariant_interval(3,2)>0

def test_25_microcausal_spacelike(): assert microcausal_spacelike(1,2)

def test_26_boson_spectrum(): assert np.array_equal(boson_number_spectrum(3),[0,1,2,3])

def test_27_fermion_spectrum(): assert np.array_equal(fermion_number_spectrum(),[0,1])

def test_28_zero_point(): assert scalar_zero_point_energy(2,3)==3

def test_29_charge(): assert charged_state_charge(4,1,q=2)==6

def test_30_graph_topology(): assert connected_tree_loops(3,2)==0 and phi4_vertex_count(4,0)==1
