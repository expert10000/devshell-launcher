import numpy as np
import pytest
from edge_states_companion import *

def test_01_magnetic_length_positive(): assert magnetic_length(4)>0
def test_02_magnetic_length_scaling(): assert np.isclose(magnetic_length(4),0.5*magnetic_length(1))
def test_03_magnetic_length_zero_error():
    with pytest.raises(ValueError): magnetic_length(0)
def test_04_guiding_center_orientation(): assert guiding_center(2,lB=1,orientation=-1)==-2
def test_05_dispersion_linear(): assert np.isclose(smooth_edge_dispersion(2,E0=1,gradient=.5,lB=1,orientation=-1),0)
def test_06_velocity_from_slope(): assert group_velocity_from_slope(3,hbar=2)==1.5
def test_07_smooth_velocity_matches_derivative():
    k=np.array([-1.,1.]); E=smooth_edge_dispersion(k,0,.4,1,-1); assert np.isclose((E[1]-E[0])/(k[1]-k[0]),smooth_edge_velocity(.4,1,1,-1))
def test_08_landauer_quantum(): assert landauer_current(2)==2
def test_09_landauer_transmission(): assert landauer_current(2,.25)==.5
def test_10_landauer_bad_T():
    with pytest.raises(ValueError): landauer_current(1,1.2)
def test_11_multichannel_integer(): assert multichannel_conductance([1,1,1])==3
def test_12_multichannel_partial(): assert np.isclose(multichannel_conductance([1,.5]),1.5)
def test_13_multichannel_bad_T():
    with pytest.raises(ValueError): multichannel_conductance([1,-.1])
def test_14_ring_current_conservation(): assert np.isclose(np.sum(chiral_ring_currents([1,1,0,0],2)),0)
def test_15_ring_global_shift_invariant(): assert np.allclose(chiral_ring_currents([1,1,0,0]),chiral_ring_currents([6,6,5,5]))
def test_16_hall_probe_pattern(): assert np.allclose(ideal_hall_probe_voltages(1,0),[1,1,1,0,0,0])
def test_17_hall_probe_reversal(): assert np.allclose(ideal_hall_probe_voltages(1,0,direction=-1),[1,0,0,0,1,1])
def test_18_hall_resistance(): assert hall_resistance_from_channels(4)==.25
def test_19_hall_resistance_error():
    with pytest.raises(ValueError): hall_resistance_from_channels(0)
def test_20_qpc_conductance(): assert np.isclose(qpc_conductance([1,1,.35]),2.35)
def test_21_equilibration_equal_weights(): assert equilibration_potential([3,1])==2
def test_22_equilibration_weighted(): assert np.isclose(equilibration_potential([3,1],[3,1]),2.5)
def test_23_equilibration_profile_conserves_mean():
    a,b=equilibration_profile([0,2],3,1,1); assert np.allclose((a+b)/2,2)
def test_24_tunneling_decays(): assert interedge_tunneling_scale(3)<interedge_tunneling_scale(1)
def test_25_bulk_boundary_difference(): assert bulk_boundary_index(5,2)==3
def test_26_reconstruction_preserves_index(): assert reconstructed_edge_index(3,1)==reconstructed_edge_index(2,0)
def test_27_spectral_flow_shape(): assert spectral_flow_levels(np.linspace(0,1,5),(0,1,2)).shape==(3,5)
def test_28_pumped_charge(): assert pumped_charge(3,2)==6
def test_29_local_filling(): assert np.allclose(local_filling([2,4],2),[1,2])
def test_30_incompressible_mask(): assert np.array_equal(incompressible_mask([.95,1.2,2.03],.08),[True,False,True])
