import math
import numpy as np
import pytest
from waves_radiation_companion import (
    C0, array_factor, dipole_power_pattern, dipole_solid_angle_integral,
    directivity_from_axisymmetric_pattern, effective_aperture,
    friis_received_power, half_wave_power_pattern, harmonic_dipole_power,
    hertzian_radiation_resistance, radiation_zone_parameter, retarded_time,
    zone_terms,
)

def test_retarded_time():
    assert retarded_time(2e-6, 300.0) == pytest.approx(2e-6 - 300.0/C0)

def test_retarded_time_rejects_negative_distance():
    with pytest.raises(ValueError): retarded_time(0.0, -1.0)

def test_zone_ratios_equal_kr():
    k, r = 3.0, 2.0
    near, induction, radiation = zone_terms(k, r)
    assert induction/near == pytest.approx(k*r)
    assert radiation/induction == pytest.approx(k*r)

def test_radiation_zone_parameter():
    assert radiation_zone_parameter(2.0, 5.0) == pytest.approx(10.0)

def test_dipole_pattern_nulls_and_maximum():
    vals = dipole_power_pattern(np.array([0.0, np.pi/2, np.pi]))
    assert vals[0] == pytest.approx(0.0, abs=1e-15)
    assert vals[1] == pytest.approx(1.0)
    assert vals[2] == pytest.approx(0.0, abs=1e-15)

def test_dipole_solid_angle_integral():
    assert dipole_solid_angle_integral(4001) == pytest.approx(8*np.pi/3, rel=2e-7)

def test_dipole_directivity_is_three_halves():
    th=np.linspace(0,np.pi,4001)
    assert directivity_from_axisymmetric_pattern(th,dipole_power_pattern(th)) == pytest.approx(1.5, rel=2e-7)

def test_harmonic_dipole_power_quartic_frequency():
    p1=harmonic_dipole_power(1e-12,1e9); p2=harmonic_dipole_power(1e-12,2e9)
    assert p2/p1 == pytest.approx(16.0)

def test_hertzian_radiation_resistance():
    assert hertzian_radiation_resistance(0.02,1.0) == pytest.approx(80*np.pi**2*0.02**2)

def test_half_wave_pattern_broadside_and_axis():
    vals=half_wave_power_pattern(np.array([0.0,np.pi/2,np.pi]))
    assert vals[0] == pytest.approx(0.0,abs=1e-15)
    assert vals[1] == pytest.approx(1.0)
    assert vals[2] == pytest.approx(0.0,abs=1e-15)

def test_uniform_array_broadside_maximum():
    # z-axis array, d=lambda/2, zero phase: broadside theta=pi/2 is coherent.
    assert array_factor(np.array([np.pi/2]),4,0.5,1.0)[0] == pytest.approx(1.0)

def test_two_element_array_axis_null():
    # z-axis array, d=lambda/2: endfire phase difference is pi.
    assert array_factor(np.array([0.0]),2,0.5,1.0)[0] == pytest.approx(0.0,abs=1e-14)

def test_effective_aperture_relation():
    assert effective_aperture(4.0,0.5) == pytest.approx(4*0.25/(4*np.pi))

def test_friis_inverse_square_and_domain_check():
    p1=friis_received_power(1.0,2.0,2.0,0.1,10.0)
    p2=friis_received_power(1.0,2.0,2.0,0.1,20.0)
    assert p2/p1 == pytest.approx(0.25)
    with pytest.raises(ValueError): friis_received_power(1,1,1,0.1,0)
