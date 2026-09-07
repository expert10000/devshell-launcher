import numpy as np
import pytest
from integer_qhe_companion import *

def test_01_sigma_quantum(): assert hall_conductivity(1)==1
def test_02_sigma_integer(): assert hall_conductivity(4)==4
def test_03_resistance_inverse(): assert hall_resistance(4)==.25
def test_04_resistance_zero_error():
    with pytest.raises(ValueError): hall_resistance(0)
def test_05_filling(): assert filling_factor(6,2)==3
def test_06_filling_inverse_B(): assert filling_factor(2,4)==.5*filling_factor(2,2)
def test_07_tensor_shape(): assert conductivity_tensor(.1,2).shape==(2,2)
def test_08_tensor_antisym():
    s=conductivity_tensor(.1,2); assert s[0,1]==-s[1,0]
def test_09_rho_plateau():
    r=resistivity_tensor(0,4); assert np.isclose(abs(r[0,1]),.25)
def test_10_rho_inverse():
    s=conductivity_tensor(.2,1.3); r=resistivity_tensor(.2,1.3); assert np.allclose(s@r,np.eye(2))
def test_11_singular_error():
    with pytest.raises(ValueError): resistivity_tensor(0,0)
def test_12_plateau_floor(): assert plateau_integer(3.7)==3
def test_13_plateau_nonnegative(): assert plateau_integer(-.2)==0
def test_14_dos_nonnegative(): assert np.all(gaussian_broadened_dos(np.linspace(-2,4,40),[0,2],.2)>=0)
def test_15_dos_peak():
    E=np.linspace(-1,1,1001); d=gaussian_broadened_dos(E,[0],.1); assert abs(E[np.argmax(d)])<.01
def test_16_dos_gamma_error():
    with pytest.raises(ValueError): gaussian_broadened_dos([0],[0],0)
def test_17_localized_center_zero(): assert localized_tail_weight([0],0,1,.2)[0]==0
def test_18_localized_tail_positive(): assert localized_tail_weight([2],0,1,.2)[0]>0
def test_19_kubo_three(): assert kubo_integer_conductivity(3)==3
def test_20_flux_shift_sign(): assert flux_guiding_center_shift(1,2,4)<0
def test_21_flux_shift_scale(): assert np.isclose(flux_guiding_center_shift(2,2,4),2*flux_guiding_center_shift(1,2,4))
def test_22_pumped_charge(): assert pumped_charge(3)==3
def test_23_two_flux_quanta(): assert pumped_charge(3,2)==6
def test_24_chern_equals_kubo(): assert chern_hall_conductivity(5)==kubo_integer_conductivity(5)
def test_25_four_terminal_rxx(): assert four_terminal_resistances(2,.01)[0]==.01
def test_26_four_terminal_rxy(): assert four_terminal_resistances(2)[1]==.5
def test_27_edge_velocity(): assert edge_group_velocity(3,hbar=2)==1.5
def test_28_thermal_positive(): assert np.all(thermal_smearing(np.linspace(-2,2,20),0,.2)>0)
def test_29_thermal_peak_mu():
    E=np.linspace(-1,1,1001); d=thermal_smearing(E,0,.1); assert abs(E[np.argmax(d)])<.01
def test_30_thermal_error():
    with pytest.raises(ValueError): thermal_smearing([0],0,0)
