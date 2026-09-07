import numpy as np
import pytest
from chern_invariants_companion import *


def test_01_wrap_zero(): assert wrap_phase(0.0) == pytest.approx(0.0)
def test_02_wrap_twopi(): assert wrap_phase(2*np.pi) == pytest.approx(0.0)
def test_03_sphere_curvature_poles(): assert sphere_lower_curvature(0.0) == pytest.approx(0.0)
def test_04_sphere_chern(): assert sphere_chern_numeric(6001) == pytest.approx(1.0, abs=2e-7)
def test_05_transition_winding_one():
    p=np.linspace(0,2*np.pi,1001); assert winding_from_unwrapped_phase(p,transition_phase(p,1)) == pytest.approx(1.0)
def test_06_transition_winding_minus_two():
    p=np.linspace(0,2*np.pi,1001); assert winding_from_unwrapped_phase(p,transition_phase(p,-2)) == pytest.approx(-2.0)
def test_07_degree_texture_unit_norm():
    v=degree_texture(np.pi/3,np.pi/7,3); assert np.linalg.norm(v) == pytest.approx(1.0)
def test_08_degree_one(): assert degree_numeric(1,6001) == pytest.approx(1.0,abs=2e-7)
def test_09_degree_three(): assert degree_numeric(3,6001) == pytest.approx(3.0,abs=6e-7)
def test_10_degree_orientation(): assert degree_numeric(-2,6001) == pytest.approx(-2.0,abs=4e-7)
def test_11_dirac_curvature_origin_positive_mass(): assert regularized_dirac_curvature(0,0,1,1) == pytest.approx(0.5)
def test_12_dirac_curvature_origin_negative_mass(): assert regularized_dirac_curvature(0,0,-1,1) == pytest.approx(-0.5)
def test_13_dirac_exact_topological(): assert regularized_dirac_chern_exact(1,1) == pytest.approx(1)
def test_14_dirac_exact_trivial(): assert regularized_dirac_chern_exact(-1,1) == pytest.approx(0)
def test_15_dirac_exact_orientation_flip(): assert regularized_dirac_chern_exact(-1,-1) == pytest.approx(-1)
def test_16_dirac_numeric_topological(): assert regularized_dirac_chern_numeric(1,1,24,50001) == pytest.approx(1,abs=1e-3)
def test_17_dirac_numeric_trivial(): assert regularized_dirac_chern_numeric(-1,1,24,50001) == pytest.approx(0,abs=1e-3)
def test_18_gap_closes_at_critical_mass(): assert two_level_gap(0,0,0,1) == pytest.approx(0)
def test_19_gap_positive_away_from_critical(): assert two_level_gap(0,0,0.3,1) == pytest.approx(0.6)
def test_20_projector_trace_one(): assert np.trace(projector_from_state([1,1j])).real == pytest.approx(1)
def test_21_projector_idempotent():
    P=projector_from_state([1,2j]); assert np.linalg.norm(P@P-P)<1e-12
def test_22_occupied_projector_rank_two():
    F=np.array([[1,0],[0,1],[0,0]],complex); assert np.trace(occupied_projector(F)).real == pytest.approx(2)
def test_23_frame_unitary_invariance():
    F=np.array([[1,0],[0,1],[0,0]],complex); U=random_unitary(2,3); assert np.linalg.norm(occupied_projector(F)-occupied_projector(rotate_frame(F,U)))<1e-12
def test_24_random_unitary_is_unitary():
    U=random_unitary(3,4); assert np.linalg.norm(U.conj().T@U-np.eye(3))<1e-12
def test_25_link_has_unit_modulus(): assert abs(normalized_link(2+3j)) == pytest.approx(1)
def test_26_singular_link_rejected():
    with pytest.raises(ValueError): normalized_link(0j)
def test_27_plaquette_gauge_invariance():
    u00=np.array([1,0],complex); u10=np.array([1,1],complex)/np.sqrt(2); u11=np.array([1,1j],complex)/np.sqrt(2); u01=np.array([1,0.5j],complex)/np.sqrt(1.25)
    a=plaquette_phase(u00,u10,u11,u01); b=plaquette_phase(gauge_rephase(u00,.2),gauge_rephase(u10,-.4),gauge_rephase(u11,1.1),gauge_rephase(u01,-2.0)); assert a==pytest.approx(b)
def test_28_hall_sign_pair(): assert hall_sigma_xy(2) == pytest.approx(-hall_sigma_yx(2))
def test_29_pump_equals_chern(): assert pumped_particle_number(-3) == pytest.approx(-3)
def test_30_cumulative_pump_integrates_density():
    t=np.linspace(0,1,1001); q=cumulative_pump_from_density(t,np.ones_like(t)*2); assert q[-1] == pytest.approx(2,abs=1e-12)
