import numpy as np
import pytest
from topological_insulators_companion import *

def test_01_tr_unitary_unitary(): assert np.linalg.norm(TR_UNITARY.conj().T@TR_UNITARY-np.eye(4))<1e-12
def test_02_theta_square_minus_one(): assert np.linalg.norm(TR_UNITARY@TR_UNITARY.conj()+np.eye(4))<1e-12
def test_03_hamiltonian_hermitian():
    H=qsh_hamiltonian(.37,-.51,m=-1,rashba=.2); assert np.linalg.norm(H-H.conj().T)<1e-12
def test_04_time_reversal_covariance_clean(): assert time_reversal_error(.31,.49,m=-1,rashba=0)<1e-12
def test_05_time_reversal_covariance_rashba(): assert time_reversal_error(.31,.49,m=-1,rashba=.3)<1e-12
def test_06_kramers_at_gamma(): assert kramers_pair_splitting(0,0,m=-1,rashba=.2)<1e-12
def test_07_kramers_at_pi0(): assert kramers_pair_splitting(np.pi,0,m=-1,rashba=.2)<1e-12
def test_08_parity_z2_nontrivial_minus1(): assert parity_z2(-1)==1
def test_09_parity_z2_nontrivial_plus1(): assert parity_z2(1)==1
def test_10_parity_z2_trivial_minus3(): assert parity_z2(-3)==0
def test_11_parity_z2_trivial_plus3(): assert parity_z2(3)==0
def test_12_parity_z2_critical_none(): assert parity_z2(0) is None
def test_13_spin_chern_nontrivial_mminus1(): assert abs(spin_block_chern(24,-1))==pytest.approx(1,abs=1e-10)
def test_14_spin_chern_nontrivial_mplus1(): assert abs(spin_block_chern(24,1))==pytest.approx(1,abs=1e-10)
def test_15_spin_chern_trivial(): assert spin_block_chern(24,3)==pytest.approx(0,abs=1e-10)
def test_16_spin_chern_random_gauge():
    a=spin_block_chern(20,-1); b=spin_block_chern(20,-1,random_gauge_seed=5); assert b==pytest.approx(a,abs=1e-10)
def test_17_z2_from_spin_chern(): assert spin_chern_z2(20,-1)==1 and spin_chern_z2(20,3)==0
def test_18_bulk_gap_nontrivial_positive(): assert bulk_gap(32,m=-1,rashba=.15)>.5
def test_19_bulk_gap_closes_m0(): assert bulk_gap(32,m=0,rashba=0)<1e-10
def test_20_wilson_phase_gauge_invariant():
    a=np.sort(wilson_phases(.7,60,m=-1)); b=np.sort(wilson_phases(.7,60,m=-1,random_gauge_seed=9)); assert np.allclose(a,b,atol=1e-9)
def test_21_wilson_kramers_gamma():
    p=wilson_phases(0,80,m=-1); assert abs(np.angle(np.exp(1j*(p[1]-p[0]))))<1e-8
def test_22_helical_edge_symmetric():
    e=helical_edge_energies(np.array([-.4,.4]),velocity=2); assert e[0,0]==pytest.approx(e[1,0]) and e[0,1]==pytest.approx(e[1,1])
def test_23_finite_gap_exponential():
    a=finite_size_gap(6,2); b=finite_size_gap(8,2); assert b/a==pytest.approx(np.exp(-1))
def test_24_penetration_inverse_mass(): assert penetration_depth(.25)==pytest.approx(4)
def test_25_penetration_diverges(): assert np.isinf(penetration_depth(0))
def test_26_surface_dirac_massless_zero(): assert np.allclose(surface_dirac_energies(0,0,mass=0),[0,0])
def test_27_surface_dirac_mass_gap(): assert np.allclose(surface_dirac_energies(0,0,mass=.3),[-.3,.3])
def test_28_surface_spin_tangential():
    s=surface_spin(3,4); k=np.array([3.,4.,0.]); assert np.dot(s,k)==pytest.approx(0,abs=1e-12) and np.linalg.norm(s)==pytest.approx(1)
def test_29_theta_surface_half_hall(): assert surface_hall_from_delta_theta(theta_angle(1))==pytest.approx(.5)
def test_30_surface_bulk_scaling():
    t=np.array([5.,15.]); g=conductance_channels(t,surface_sheet=2,bulk_per_thickness=.1); assert g[1]-g[0]==pytest.approx(1)
