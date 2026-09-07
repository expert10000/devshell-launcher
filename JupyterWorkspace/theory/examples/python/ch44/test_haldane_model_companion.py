import numpy as np
import pytest
from haldane_model_companion import *


def test_01_reciprocal_duality_a1_g1(): assert np.dot(A1,G1) == pytest.approx(2*np.pi)
def test_02_reciprocal_duality_a1_g2(): assert np.dot(A1,G2) == pytest.approx(0.0,abs=1e-12)
def test_03_valley_masses_symmetric_at_M0():
    a,b=valley_masses(0,.2,np.pi/2); assert a == pytest.approx(-b)
def test_04_mass_formula_value():
    a,b=valley_masses(0,.2,np.pi/2); assert b == pytest.approx(3*np.sqrt(3)*.2)
def test_05_chern_mass_topological_positive(): assert chern_from_masses(0,.15,np.pi/2) == 1
def test_06_chern_mass_topological_negative(): assert chern_from_masses(0,.15,-np.pi/2) == -1
def test_07_chern_mass_trivial(): assert chern_from_masses(2,.15,np.pi/2) == 0
def test_08_chern_mass_critical_nan(): assert np.isnan(chern_from_masses(3*np.sqrt(3)*.15,.15,np.pi/2))
def test_09_hamiltonian_hermitian():
    H=haldane_hamiltonian(.17,.41); assert np.linalg.norm(H-H.conj().T)<1e-12
def test_10_band_ordering():
    e=band_energies(.2,.3); assert e[0] <= e[1]
def test_11_lower_state_normalized(): assert np.linalg.norm(lower_state(.2,.3)) == pytest.approx(1)
def test_12_link_unit_modulus(): assert abs(normalized_link(2+3j)) == pytest.approx(1)
def test_13_singular_link_rejected():
    with pytest.raises(ValueError): normalized_link(0j)
def test_14_fukui_chern_positive(): assert chern_fukui(18,t2=.15,phi=np.pi/2,M=0) == pytest.approx(1,abs=1e-10)
def test_15_fukui_chern_negative(): assert chern_fukui(18,t2=.15,phi=-np.pi/2,M=0) == pytest.approx(-1,abs=1e-10)
def test_16_fukui_chern_trivial(): assert chern_fukui(18,t2=.15,phi=np.pi/2,M=2) == pytest.approx(0,abs=1e-10)
def test_17_random_gauge_invariance():
    a=chern_fukui(18,t2=.15,phi=np.pi/2,M=0); b=chern_fukui(18,random_gauge_seed=7,t2=.15,phi=np.pi/2,M=0); assert b == pytest.approx(a,abs=1e-10)
def test_18_bulk_direct_gap_positive():
    d,_=gap_scan(30,t2=.15,phi=np.pi/2,M=0); assert d > .5
def test_19_direct_gap_closes_on_boundary():
    M=3*np.sqrt(3)*.15; d,_=gap_scan(30,t2=.15,phi=np.pi/2,M=M); assert d < 1e-10
def test_20_indirect_overlap_possible():
    d,ind=gap_scan(30,t2=.4,phi=.2,M=0); assert d>0 and ind<0
def test_21_edge_dispersion_positive_chirality(): assert edge_dispersion(2,velocity=3,chirality=1) == pytest.approx(6)
def test_22_edge_dispersion_reverses(): assert edge_dispersion(2,velocity=3,chirality=-1) == pytest.approx(-6)
def test_23_crossing_index(): assert edge_crossing_index([2,1,-3]) == 1
def test_24_domain_wall_profile_normalized():
    y=np.linspace(-12,12,5001); p=domain_wall_profile(y); assert np.trapezoid(p,y) == pytest.approx(1,abs=2e-6)
def test_25_domain_wall_profile_center_max():
    y=np.linspace(-8,8,2001); p=domain_wall_profile(y); assert np.argmax(p) == len(y)//2
def test_26_penetration_inverse_mass(): assert penetration_depth(.5) == pytest.approx(2)
def test_27_penetration_diverges_at_transition(): assert np.isinf(penetration_depth(0))
def test_28_finite_width_gap_exponential():
    a=finite_width_gap(5,2); b=finite_width_gap(7,2); assert b/a == pytest.approx(np.exp(-1))
def test_29_local_marker_has_bulk_plateau():
    x=np.linspace(0,100,1001); c=local_marker_profile(x,100,C=1,xi=4); assert c[len(c)//2] > .99999 and c[0] == pytest.approx(0)
def test_30_hall_tensor_antisymmetry(): assert hall_sigma_xy(2) == pytest.approx(-hall_sigma_yx(2))
