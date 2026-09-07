import math
import numpy as np
import pytest
from berry_geometry_companion import *

def test_01_wrap_zero(): assert wrap_phase(0)==0
def test_02_wrap_2pi(): assert np.isclose(wrap_phase(2*math.pi),0)
def test_03_solid_north(): assert np.isclose(solid_angle_cone(0),0)
def test_04_solid_equator(): assert np.isclose(solid_angle_cone(math.pi/2),2*math.pi)
def test_05_spin_upper_equator(): assert np.isclose(spin_half_berry_phase(math.pi/2,+1),-math.pi)
def test_06_spin_opposite_branches(): assert np.isclose(spin_half_berry_phase(.7,+1),-spin_half_berry_phase(.7,-1))
def test_07_spin_bad_branch():
    with pytest.raises(ValueError): spin_half_berry_phase(.2,0)
def test_08_dirac_lower_origin_positive_mass(): assert np.isclose(massive_dirac_curvature(0,0,2,-1),1/8)
def test_09_dirac_branches_opposite(): assert np.isclose(massive_dirac_curvature(.2,.3,1,+1),-massive_dirac_curvature(.2,.3,1,-1))
def test_10_dirac_mass_reversal(): assert np.isclose(massive_dirac_curvature(.2,.3,-1,-1),-massive_dirac_curvature(.2,.3,1,-1))
def test_11_anomalous_linear_force(): assert np.isclose(anomalous_velocity_y(2,3),6)
def test_12_anomalous_zero_curvature(): assert np.isclose(anomalous_velocity_y(7,0),0)
def test_13_polarization_pi(): assert np.isclose(polarization_from_zak(math.pi),-.5)
def test_14_polarization_shift(): assert np.isclose(polarization_from_zak(3*math.pi)-polarization_from_zak(math.pi),-1)
def test_15_pump_c1(): assert np.isclose(pumped_charge_from_chern(1),1)
def test_16_pump_sign(): assert np.isclose(pumped_charge_from_chern(-2),-2)
def test_17_discrete_constant():
    z=np.tile(np.array([1,0],complex),(20,1)); assert np.isclose(berry_phase_discrete(z),0)
def test_18_discrete_gauge_invariance():
    z=ssh_lower_states(.5,1,101); p=berry_phase_discrete(z); phases=np.exp(1j*np.linspace(0,7,len(z))); assert np.isclose(abs(wrap_phase(berry_phase_discrete(z*phases[:,None])-p)),0,atol=1e-10)
def test_19_ssh_trivial(): assert abs(ssh_zak_phase(1.5,1,301))<1e-6
def test_20_ssh_topological(): assert np.isclose(abs(ssh_zak_phase(.5,1,301)),math.pi,atol=1e-6)
def test_21_ssh_gap_close():
    with pytest.raises(ValueError): ssh_zak_phase(1,1)
def test_22_wilson_unitary():
    W=unitary_from_hermitian_connection(np.array([[.2,.1],[.1,-.2]]),2); assert np.allclose(W.conj().T@W,np.eye(2))
def test_23_wilson_diagonal_phases():
    W=unitary_from_hermitian_connection(np.diag([.2,-.4]),1); assert np.allclose(wilson_eigenphases(W),[-.4,.2])
def test_24_wilson_conjugation_spectrum():
    A=np.diag([.2,-.4]); U=np.array([[1,1],[-1,1]],complex)/math.sqrt(2); p=wilson_eigenphases(unitary_from_hermitian_connection(A)); q=wilson_eigenphases(unitary_from_hermitian_connection(U.conj().T@A@U)); assert np.allclose(p,q)
def test_25_metric_north(): assert np.allclose(quantum_metric_sphere(0),[[.25,0],[0,0]])
def test_26_metric_equator(): assert np.allclose(quantum_metric_sphere(math.pi/2),.25*np.eye(2))
def test_27_curvature_equator_lower(): assert np.isclose(berry_curvature_sphere(math.pi/2,-1),.5)
def test_28_curvature_orientation(): assert np.isclose(berry_curvature_sphere(.8,+1),-berry_curvature_sphere(.8,-1))
def test_29_twolevel_geometry_equality(): assert abs(two_level_metric_curvature_residual(.9,-1))<1e-14
def test_30_polarization_branch_winding(): assert np.isclose(polarization_pump_branch([0,1],2)[1]-polarization_pump_branch([0,1],2)[0],2)
