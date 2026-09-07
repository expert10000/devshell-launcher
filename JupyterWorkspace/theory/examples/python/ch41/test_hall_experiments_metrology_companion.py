import math
import numpy as np
import pytest
from hall_experiments_metrology_companion import *

def test_01_rk_value(): assert np.isclose(R_K, 25812.8074593045, rtol=1e-12)
def test_02_i2_plateau(): assert np.isclose(hall_plateau_resistance(2), R_K/2)
def test_03_i4_ratio(): assert np.isclose(hall_plateau_resistance(2)/hall_plateau_resistance(4),2)
def test_04_bad_plateau():
    with pytest.raises(ValueError): hall_plateau_resistance(0)
def test_05_tensor_ideal_hall():
    sxx,sxy=conductivity_from_resistivity(0.0,R_K); assert np.isclose(sxx,0) and np.isclose(sxy,-1/R_K)
def test_06_tensor_roundtrip():
    rxx,ryx=.1,100.0; sxx,sxy=conductivity_from_resistivity(rxx,ryx); r2,y2=resistivity_from_conductivity(sxx,sxy); assert np.allclose([r2,y2],[rxx,ryx])
def test_07_density_hall_slope(): assert np.isclose(density_from_hall_slope(1/(E_EXACT*2e15)),2e15)
def test_08_mobility(): assert np.isclose(mobility_from_sheet_resistance(2e15,1/(2e15*E_EXACT*10)),10)
def test_09_relative_deviation_zero(): assert np.isclose(relative_hall_deviation(hall_plateau_resistance(2),2),0)
def test_10_relative_deviation_ppb(): assert np.isclose(relative_hall_deviation(hall_plateau_resistance(2)*(1+5e-9),2),5e-9,rtol=1e-7)
def test_11_ccc_ratio(): assert np.isclose(ccc_resistance_ratio(129,1),129)
def test_12_ccc_residual(): assert np.isclose(ccc_resistance_ratio(100,10,1e-6),10.00001)
def test_13_uncertainty_independent():
    u=combined_standard_uncertainty([1,1],np.diag([4,9])); assert np.isclose(u,math.sqrt(13))
def test_14_uncertainty_covariance():
    cov=np.array([[1,.5],[.5,1]]); assert np.isclose(combined_standard_uncertainty([1,-1],cov),1)
def test_15_poisson_electron(): assert np.isclose(poisson_shot_noise(E_EXACT,1e-9),2*E_EXACT*1e-9)
def test_16_poisson_e3_ratio(): assert np.isclose(poisson_shot_noise(E_EXACT/3,1e-9)/poisson_shot_noise(E_EXACT,1e-9),1/3)
def test_17_charge_recovery():
    q=E_EXACT/4; I=2e-9; assert np.isclose(effective_charge_from_poisson_noise(poisson_shot_noise(q,I),I),q)
def test_18_finite_noise_zero_bias(): assert finite_temperature_excess_noise(E_EXACT/3,0,0.03,1e-7)==0
def test_19_finite_noise_positive(): assert finite_temperature_excess_noise(E_EXACT/3,30e-6,0.03,1e-7)>0
def test_20_laughlin_charge(): assert np.isclose(laughlin_charge_fraction(3),1/3)
def test_21_laughlin_braid(): assert np.isclose(laughlin_full_braid_phase(3),2*math.pi/3)
def test_22_interferometer_flux_phase(): assert np.isclose(interferometer_phase(1/3,1),2*math.pi/3)
def test_23_interferometer_additive(): assert np.isclose(interferometer_phase(.25,2,.3,.2,.1),math.pi+.6)
def test_24_visibility_half(): assert np.isclose(visibility_ratio(4,8),math.exp(-.5))
def test_25_visibility_zero_length(): assert np.isclose(visibility_ratio(0,8),1)
def test_26_equilibration(): assert np.isclose(equilibration_fraction(2,2),1-math.exp(-1))
def test_27_kappa_linear_T(): assert np.isclose(thermal_hall_conductance(2,0.1)/thermal_hall_conductance(2,0.05),2)
def test_28_heat_current_zero_deltaT(): assert np.isclose(ballistic_heat_current(1,0.02,0.02),0)
def test_29_52_benchmarks(): assert [five_halves_thermal_ratio(x) for x in ['Pfaffian','anti-Pfaffian','PH-Pfaffian']]==[3.5,1.5,2.5]
def test_30_kappa0_formula(): assert np.isclose(KAPPA0, math.pi**2*K_B_EXACT**2/(3*H_EXACT))
