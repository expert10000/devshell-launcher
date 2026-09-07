import math
import numpy as np
import pytest
from landau_quantization_companion import *

def test_01_mag_length(): assert np.isclose(magnetic_length(4),0.5)
def test_02_mag_length_scaling(): assert np.isclose(magnetic_length(9),magnetic_length(1)/3)
def test_03_cyclotron_frequency(): assert cyclotron_frequency(3,m=2,q=2)==3
def test_04_landau_ground(): assert landau_energy(0,2)==1
def test_05_landau_spacing(): assert np.isclose(landau_energy(2,3)-landau_energy(1,3),3)
def test_06_flux_quantum(): assert np.isclose(flux_quantum(q=2,h=10),5)
def test_07_flux_degeneracy(): assert np.isclose(flux_degeneracy(20,5,q=2,h=10),20)
def test_08_degeneracy_linear_area(): assert np.isclose(flux_degeneracy(2,1),2*flux_degeneracy(1,1))
def test_09_degeneracy_linear_B(): assert np.isclose(flux_degeneracy(1,2),2*flux_degeneracy(1,1))
def test_10_state_density(): assert np.isclose(state_density(2,h=4),0.5)
def test_11_filling(): assert np.isclose(filling_factor(1,2,h=4),2)
def test_12_filling_inverse_B(): assert np.isclose(filling_factor(1,2),0.5*filling_factor(1,1))
def test_13_gc_spacing(): assert np.isclose(guiding_center_spacing(2*math.pi,1),1)
def test_14_gc_count(): assert len(guiding_centers(5,2*math.pi,1))==5
def test_15_gc_inside():
    x=guiding_centers(5,2*math.pi,1); assert np.all((x>0)&(x<5))
def test_16_hermite0(): assert np.allclose(hermite_phys(0,[0,1]),[1,1])
def test_17_hermite1(): assert np.allclose(hermite_phys(1,[0,1]),[0,2])
def test_18_hermite2_at0(): assert np.isclose(hermite_phys(2,np.array([0.]))[0],-2)
def test_19_orbital_ground_peak(): assert landau_gauge_orbital(0,np.array([0.]))[0]>landau_gauge_orbital(0,np.array([1.]))[0]
def test_20_orbital_shift(): assert np.isclose(landau_gauge_orbital(0,np.array([2.]),X=2)[0],math.pi**(-0.25))
def test_21_lll_nonnegative(): assert np.all(lll_radial_probability(3,np.linspace(0,8,50))>=0)
def test_22_lll_peak_moves_outward():
    r=np.linspace(0,8,1000); p0=r[np.argmax(lll_radial_probability(0,r))]; p4=r[np.argmax(lll_radial_probability(4,r))]; assert p4>p0
def test_23_zeeman_linear_B(): assert zeeman_splitting(4,g=2,muB=.5)==4
def test_24_spin_branches_separate(): assert spin_resolved_energy(0,1,2)>spin_resolved_energy(0,-1,2)
def test_25_spin_average_orbital():
    a=spin_resolved_energy(2,1,3); b=spin_resolved_energy(2,-1,3); assert np.isclose((a+b)/2,landau_energy(2,3))
def test_26_dos_positive(): assert np.all(gaussian_broadened_dos(np.linspace(-1,5,30),[1,3],.2)>=0)
def test_27_dos_peak_near_level():
    E=np.linspace(0,2,1001); D=gaussian_broadened_dos(E,[1],.1); assert abs(E[np.argmax(D)]-1)<.01
def test_28_dos_gamma_error():
    with pytest.raises(ValueError): gaussian_broadened_dos([0],[0],0)
def test_29_density_equals_inv_area_cell(): assert np.isclose(state_density(3),1/(2*math.pi*magnetic_length(3)**2))
def test_30_flux_filling_identity():
    A=7; B=2; N=5; assert np.isclose(N/flux_degeneracy(A,B),filling_factor(N/A,B))
