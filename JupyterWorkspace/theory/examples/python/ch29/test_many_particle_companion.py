import numpy as np
import pytest
from many_particle_companion import *

def test_bosonic_basis_count(): assert len(bosonic_basis(3,4))==20
def test_bosonic_basis_sums(): assert all(sum(x)==3 for x in bosonic_basis(3,4))
def test_fermionic_basis_count(): assert len(fermionic_basis(3,5))==10
def test_fermionic_binary(): assert all(set(x)<= {0,1} for x in fermionic_basis(2,5))
def test_bosonic_dimension(): assert bosonic_dimension(4,3)==15
def test_fermionic_dimension(): assert fermionic_dimension(3,6)==20
def test_boson_ladder_shape(): assert boson_annihilation(5).shape==(6,6)
def test_boson_ladder_factor(): assert boson_annihilation(4)[2,3]==pytest.approx(np.sqrt(3))
def test_boson_commutator_interior():
    a=boson_annihilation(8); c=a@a.T-a.T@a
    assert np.allclose(np.diag(c)[:-1],1)
def test_fermion_nilpotent():
    c=fermion_annihilation(); assert np.allclose(c@c,0)
def test_fermion_anticommutator():
    c=fermion_annihilation(); assert np.allclose(c@c.T+c.T@c,np.eye(2))
def test_number_boson():
    n=number_operator_from_annihilation(boson_annihilation(4)); assert np.allclose(np.diag(n),np.arange(5))
def test_number_fermion():
    n=number_operator_from_annihilation(fermion_annihilation()); assert np.allclose(np.diag(n),[0,1])
def test_occupation_rdm_trace(): assert np.trace(one_rdm_from_occupation((2,0,1)))==3
def test_occupation_rdm_positive(): assert np.all(np.linalg.eigvalsh(one_rdm_from_occupation((2,0,1)))>=0)
def test_slater_rdm_trace():
    c=np.eye(4)[:,:2]; assert np.trace(slater_one_rdm(c))==pytest.approx(2)
def test_slater_rdm_idempotent():
    c=np.eye(4)[:,:2]; g=slater_one_rdm(c); assert np.allclose(g@g,g)
def test_natural_occupations_order(): assert np.allclose(natural_occupations(np.diag([.2,1.4,.4])),[1.4,.4,.2])
def test_g2_number_zero(): assert g2_single_mode(0)==0
def test_g2_number_one(): assert g2_single_mode(1)==0
def test_g2_number_large(): assert g2_single_mode(100)==pytest.approx(.99)
def test_coherent_g2(): assert coherent_g2()==1
def test_thermal_g2(): assert thermal_g2()==2
def test_hubbard_dimension(): assert bose_hubbard_dimer(4,1,.5)[0].shape==(5,5)
def test_hubbard_hermitian():
    h,_=bose_hubbard_dimer(4,1,.5); assert np.allclose(h,h.T)
def test_hubbard_noninteracting_ground():
    h,_=bose_hubbard_dimer(2,1,0); e,_=ground_state(h); assert e==pytest.approx(-2)
def test_occupation_expectation_balanced():
    b=[(2,0),(1,1),(0,2)]; assert np.allclose(occupation_expectation(np.array([.25,.5,.25]),b),[1,1])
def test_exchange_hole_origin(): assert exchange_hole_gaussian(0)==pytest.approx(0)
def test_exchange_hole_far(): assert exchange_hole_gaussian(8)>0.999999
def test_bell_reduced_entropy():
    psi=np.array([1,0,0,1])/np.sqrt(2); red=partial_trace_two_qubits(density_matrix(psi)); assert von_neumann_entropy(red)==pytest.approx(1)
