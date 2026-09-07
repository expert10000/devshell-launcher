import numpy as np
import pytest
from anyons_tqc_companion import *

def test_01_golden_ratio_identity():
    p=golden_ratio(); assert p*p==pytest.approx(p+1)
def test_02_fibonacci_total_dimension():
    p=golden_ratio(); assert fibonacci_total_dimension()**2==pytest.approx(1+p*p)
def test_03_fusion_dimension_one_tau(): assert fibonacci_fusion_dimensions(1)==(0,1)
def test_04_fusion_dimension_six_tau(): assert fibonacci_fusion_dimensions(6)==(5,8)
def test_05_f_matrix_unitary():
    F=fibonacci_f_matrix(); assert np.linalg.norm(F.conj().T@F-np.eye(2))<1e-12
def test_06_f_matrix_involution():
    F=fibonacci_f_matrix(); assert np.linalg.norm(F@F-np.eye(2))<1e-12
def test_07_r_symbols_unit_modulus(): assert np.allclose(np.abs(np.diag(fibonacci_r_matrix())),1)
def test_08_fibonacci_braids_unitary():
    for B in fibonacci_braid_generators(): assert np.linalg.norm(B.conj().T@B-np.eye(2))<1e-12
def test_09_fibonacci_braid_relation(): assert braid_relation_residual(*fibonacci_braid_generators())<1e-12
def test_10_fibonacci_braids_noncommute():
    a,b=fibonacci_braid_generators(); assert np.linalg.norm(a@b-b@a)>1e-3

def test_11_word_inverse_returns_identity():
    U=braid_word_unitary((1,2,-2,-1)); assert projective_distance(U,np.eye(2))<1e-12
def test_12_projective_distance_self_zero(): assert projective_distance(np.eye(2),np.eye(2))==pytest.approx(0)
def test_13_projective_global_phase_invariant(): assert projective_distance(np.eye(2),np.exp(.37j)*np.eye(2))<1e-12
def test_14_projective_distance_bounded():
    a,b=fibonacci_braid_generators(); d=projective_distance(a,b); assert 0<=d<=1
def test_15_compilation_best_error_monotonic():
    H=np.array([[1,1],[1,-1]],complex)/np.sqrt(2); d4=best_braid_approximation(H,4)[0]; d5=best_braid_approximation(H,5)[0]; assert d5<=d4+1e-15
def test_16_compilation_finds_nontrivial_approximation():
    H=np.array([[1,1],[1,-1]],complex)/np.sqrt(2); assert best_braid_approximation(H,8)[0]<0.25

def test_17_ising_braid_relation(): assert braid_relation_residual(*ising_braid_generators())<1e-12
def test_18_ising_braids_noncommute():
    a,b=ising_braid_generators(); assert np.linalg.norm(a@b-b@a)>1e-3
def test_19_fibonacci_orbit_outgrows_ising(): assert distinct_projective_orbit_count(6,'fibonacci')>distinct_projective_orbit_count(6,'ising')

def test_20_forced_zero_attempts(): assert forced_success_probability(.5,0)==pytest.approx(0)
def test_21_forced_five_half_trials(): assert forced_success_probability(.5,5)==pytest.approx(31/32)
def test_22_expected_forced_attempts(): assert expected_forced_attempts(.5)==pytest.approx(2)
def test_23_forced_probability_monotonic(): assert forced_success_probability(.3,6)>forced_success_probability(.3,5)

def test_24_magic_state_zero_phase_error(): assert magic_state_phase_fidelity(0)==pytest.approx(1)
def test_25_magic_state_pi_phase_error_orthogonal(): assert magic_state_phase_fidelity(np.pi)==pytest.approx(0,abs=1e-15)

def test_26_leakage_no_operations(): assert leakage_survival(.2,0)==pytest.approx(1)
def test_27_leakage_accumulation_formula(): assert leakage_survival(.01,10)==pytest.approx(.99**10)
def test_28_poisoning_at_zero_time(): assert poisoning_probability(0,2)==pytest.approx(0)
def test_29_poisoning_half_at_log2_tau(): assert poisoning_probability(np.log(2),1)==pytest.approx(.5)
def test_30_adiabatic_window_exists_and_orders_bounds():
    tmin,tmax,ok=adiabatic_operation_window(.01,100); assert ok and tmin<tmax and tmin==pytest.approx(.01) and tmax==pytest.approx(100)
