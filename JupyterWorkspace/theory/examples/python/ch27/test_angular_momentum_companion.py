import numpy as np
import pytest
from angular_momentum_companion import *

def test_01_normalize(): assert np.allclose(normalize([3,4]),[.6,.8])
def test_02_zero_rejected():
    with pytest.raises(ValueError):normalize([0,0])
def test_03_pauli_x_square(): assert np.allclose(SX@SX,I2)
def test_04_pauli_commutator(): assert np.allclose(commutator(SX,SY),2j*SZ)
def test_05_spin_axis_eigenvalues(): assert np.allclose(np.linalg.eigvalsh(spin_operator([1,2,3])),[-.5,.5])
def test_06_rotation_unitary():
    U=rotation_spin_half([1,2,3],.7);assert np.allclose(U.conj().T@U,I2)
def test_07_two_pi_minus_identity(): assert np.allclose(rotation_spin_half([0,0,1],2*np.pi),-I2)
def test_08_four_pi_identity(): assert np.allclose(rotation_spin_half([0,0,1],4*np.pi),I2)
def test_09_bloch_up(): assert np.allclose(bloch_vector(UP),[0,0,1])
def test_10_bloch_norm_pure(): assert np.isclose(np.linalg.norm(bloch_vector(normalize([1,1j]))),1)
def test_11_measure_z_up(): assert np.allclose(measurement_probabilities(UP,[0,0,1]),[1,0])
def test_12_measure_x_up(): assert np.allclose(measurement_probabilities(UP,[1,0,0]),[.5,.5])
def test_13_projective_probability():
    p,q=projective_measure(UP,[1,0,0],1);assert np.isclose(p,.5) and np.allclose(measurement_probabilities(q,[1,0,0]),[1,0])
def test_14_j_half_dimension(): assert angular_momentum_matrices(.5)[0].shape==(2,2)
def test_15_j_one_dimension(): assert angular_momentum_matrices(1)[0].shape==(3,3)
def test_16_bad_j_rejected():
    with pytest.raises(ValueError):angular_momentum_matrices(.3)
def test_17_j_commutator():
    x,y,z,*_=angular_momentum_matrices(2);assert np.allclose(commutator(x,y),1j*z)
def test_18_casimir_half(): assert np.allclose(casimir(.5),.75*I2)
def test_19_casimir_two(): assert np.allclose(casimir(2),6*np.eye(5))
def test_20_ladder_top_zero():
    *_,jp,jm,m=angular_momentum_matrices(2);assert np.allclose(jp[:,0],0)
def test_21_ladder_bottom_zero():
    *_,jp,jm,m=angular_momentum_matrices(2);assert np.allclose(jm[:,-1],0)
def test_22_cg_unitary():
    C=cg_spin_half_matrix();assert np.allclose(C.conj().T@C,np.eye(4))
def test_23_singlet_normalized(): assert np.isclose(np.linalg.norm(coupled_states()['singlet']),1)
def test_24_singlet_total_spin_zero():
    s=coupled_states()['singlet'];assert np.isclose(expectation(s,total_spin_squared()),0)
def test_25_triplet_total_spin_two():
    t=coupled_states()['triplet_zero'];assert np.isclose(expectation(t,total_spin_squared()),2)
def test_26_spin_dot_triplet(): assert np.isclose(expectation(coupled_states()['triplet_plus'],spin_dot()),.25)
def test_27_spin_dot_singlet(): assert np.isclose(expectation(coupled_states()['singlet'],spin_dot()),-.75)
def test_28_singlet_correlations(): assert np.allclose(correlation_matrix(coupled_states()['singlet']),-np.eye(3))
def test_29_entropy_half_half(): assert np.isclose(entropy_probabilities([.5,.5]),1)
def test_30_y10_normalization():
    th=np.linspace(0,np.pi,20001);val=2*np.pi*np.trapezoid(y10_density(th)*np.sin(th),th);assert np.isclose(val,1,atol=1e-7)
