import math
import numpy as np
from magnetic_fields_companion import *

def test_01_cyclotron_positive(): assert cyclotron_frequency(-2,3,4)==1.5
def test_02_signed_frequency(): assert signed_cyclotron_frequency(-2,3,6)==-1
def test_03_radius(): assert cyclotron_radius(4,2,2,3)==3
def test_04_radius_inverse_B(): assert np.isclose(cyclotron_radius(1,1,2,1),0.5*cyclotron_radius(1,1,1,1))
def test_05_guiding_center_initial(): assert np.allclose(guiding_center(1,2,3,4,1,2,2),(5, -1))
def test_06_orbit_period_closes():
    t=np.array([0,2*math.pi]); x,y=cyclotron_trajectory(t,1,2,3,4,1,1,1); assert np.allclose([x[0],y[0]],[x[1],y[1]])
def test_07_orbit_center_constant():
    t=np.linspace(0,2,9); x,y=cyclotron_trajectory(t,1,2,3,4,1,2,2); w=1; vx=3*np.cos(t)+4*np.sin(t); vy=4*np.cos(t)-3*np.sin(t); X,Y=guiding_center(x,y,vx,vy,1,2,2); assert np.ptp(X)<1e-12 and np.ptp(Y)<1e-12
def test_08_exb_direction(): assert np.allclose(exb_drift([1,0,0],[0,0,2]),[0,-.5,0])
def test_09_exb_charge_independent(): assert np.allclose(exb_drift([2,0,0],[0,0,4]),[0,-.5,0])
def test_10_exb_zero_E(): assert np.allclose(exb_drift([0,0,0],[0,0,3]),0)
def test_11_magnetic_length(): assert np.isclose(magnetic_length(2,2,8),math.sqrt(2))
def test_12_mag_length_scaling(): assert np.isclose(magnetic_length(1,4),0.5)
def test_13_flux_quantum(): assert np.isclose(flux_quantum(2,h=10),5)
def test_14_flux_cell(): assert np.isclose(flux_cell_area(2,5,h=10),1)
def test_15_state_count(): assert np.isclose(landau_state_count(20,2,5,h=10),20)
def test_16_pi_commutator_sign(): assert kinetic_momentum_commutator_scale(-1,2)==-2
def test_17_gc_commutator_sign(): assert guiding_center_commutator_scale(-1,2)==0.5
def test_18_commutator_area_relation(): assert np.isclose(abs(guiding_center_commutator_scale(2,3)),magnetic_length(2,3)**2)
def test_19_landau_gauge_origin(): assert np.allclose(landau_gauge_A(0,0,3),[0,0,0])
def test_20_landau_gauge_value(): assert np.allclose(landau_gauge_A(2,1,3),[0,6,0])
def test_21_symmetric_gauge_value(): assert np.allclose(symmetric_gauge_A(2,4,3),[-6,3,0])
def test_22_gauge_function(): assert np.isclose(gauge_function_landau_to_symmetric(2,4,3),-12)
def test_23_phase_modulus(): assert np.isclose(abs(gauge_phase(2,3)),1)
def test_24_phase_zero(): assert gauge_phase(3,0)==1
def test_25_energy_positive(): assert magnetic_energy([3,4,0],2)==25
def test_26_energy_speed_only(): assert magnetic_energy([3,4,0],2)==magnetic_energy([-4,3,0],2)
def test_27_hall_current_direction(): assert np.allclose(hall_drift_current_density(2,-1,[1,0,0],[0,0,2]),[0,1,0])
def test_28_state_count_linear_area(): assert np.isclose(landau_state_count(2,1,1),2*landau_state_count(1,1,1))
def test_29_state_count_linear_B(): assert np.isclose(landau_state_count(1,1,2),2*landau_state_count(1,1,1))
def test_30_zero_B_errors():
    import pytest
    with pytest.raises(ValueError): exb_drift([1,0,0],[0,0,0])
