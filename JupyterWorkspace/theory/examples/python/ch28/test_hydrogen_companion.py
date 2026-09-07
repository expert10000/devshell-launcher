import math
import numpy as np
import pytest
from hydrogen_companion import *

def test_reduced_mass_limit(): assert reduced_mass_ratio(1e12)==pytest.approx(1,rel=2e-12)
def test_reduced_mass_equal(): assert reduced_mass_ratio(1)==pytest.approx(.5)
def test_bohr_z_scaling(): assert bohr_radius_scale(2)==pytest.approx(.5)
def test_energy_ground(): assert energy_au(1)==pytest.approx(-.5)
def test_energy_n_scaling(): assert energy_au(2)==pytest.approx(energy_au(1)/4)
def test_energy_z_scaling(): assert energy_ev(1,2)==pytest.approx(4*energy_ev(1))
def test_transition_lyman_alpha(): assert transition_energy_ev(2,1)==pytest.approx(RYDBERG_EV*.75)
def test_wavelength_lyman_alpha(): assert transition_wavelength_nm(2,1)==pytest.approx(121.5,rel=4e-3)
def test_r10_origin(): assert radial(1,0,0)==pytest.approx(2.0)
def test_r20_node(): assert radial(2,0,2.0)==pytest.approx(0,abs=2e-12)
def test_r21_origin(): assert radial(2,1,0)==pytest.approx(0,abs=1e-14)
def test_norm_1s(): assert radial_normalization(1,0)==pytest.approx(1,abs=2e-9)
def test_norm_2s(): assert radial_normalization(2,0)==pytest.approx(1,abs=2e-9)
def test_norm_3d(): assert radial_normalization(3,2)==pytest.approx(1,abs=2e-9)
def test_overlap_1s_2s(): assert radial_overlap(1,0,2,0)==pytest.approx(0,abs=2e-9)
def test_overlap_different_l_zero_by_angular_sector(): assert radial_overlap(2,0,2,1)==0
def test_expect_r_1s(): assert expectation_r(1,0)==pytest.approx(1.5)
def test_expect_r_2p(): assert expectation_r(2,1)==pytest.approx(5.0)
def test_expect_r2_1s(): assert expectation_r2(1,0)==pytest.approx(3.0)
def test_expect_inv_r_3(): assert expectation_inv_r(3,2)==pytest.approx(1/9)
def test_virial(): assert virial_components_ev(1)==pytest.approx((RYDBERG_EV,-2*RYDBERG_EV))
def test_radial_nodes(): assert radial_nodes(5,2)==2
def test_angular_nodes(): assert angular_nodes(3)==3
def test_shell_degeneracy(): assert shell_degeneracy(4)==16
def test_shell_degeneracy_spin(): assert shell_degeneracy(4,True)==32
def test_dipole_allowed(): assert dipole_allowed(1,0,0,0)
def test_dipole_forbidden_delta_l_zero(): assert not dipole_allowed(0,0,0,0)
def test_cumulative_probability(): assert cumulative_radial_probability(1,0,50)>0.999999
def test_most_probable_1s(): assert most_probable_radius(1,0)==pytest.approx(1,abs=.02)
def test_finite_difference_spectrum():
    vals=finite_difference_s_energies(grid_points=1400,rmax=100,levels=3)
    assert vals[0]==pytest.approx(-.5,abs=2e-3)
    assert vals[1]==pytest.approx(-.125,abs=2e-3)
