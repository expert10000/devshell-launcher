import numpy as np
from many_body_launch import *
def test_fock_dimension(): assert fock_dimension(6)==64 and fock_dimension(6,3)==20
def test_basis_particle_count(): assert all(s.bit_count()==2 for s in fermion_basis(6,2))
def test_hubbard_hermitian():
    H,_=hubbard_matrix(2,U=3,N=2); assert np.allclose(H,H.T)
def test_tight_binding_bounds():
    e=tight_binding_spectrum(20); assert e.min()>=-2.000001 and e.max()<=2.000001
def test_bose_hermitian():
    H=bose_two_site_matrix(3,U=2); assert np.allclose(H,H.T)
def test_bose_probs_normalized():
    _,p=bose_ground_probabilities(2,U=1); assert np.isclose(p.sum(),1)
def test_attraction_binds_pair(): assert pair_binding_energy(U=-4)<0
def test_blocks_sum_full_space(): assert particle_number_blocks(8).sum()==2**8
def test_reduced_bcs_hermitian():
    H,_=reduced_bcs_matrix([-1,0,1],g=.3,npairs=1); assert np.allclose(H,H.T)
def test_reduced_bcs_pair_basis(): assert reduced_bcs_matrix([-1,0,1,2],npairs=2)[0].shape==(6,6)
