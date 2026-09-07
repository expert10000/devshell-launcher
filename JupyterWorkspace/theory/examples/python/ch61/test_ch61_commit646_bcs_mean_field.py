import numpy as np
from bcs_mean_field import *
def test_binding_positive(): assert np.all(cooper_binding([.2,.5,1])>0)
def test_binding_grows(): assert np.all(np.diff(cooper_binding(np.array([.2,.4,.8])))>0)
def test_gap_at_fermi(): assert np.isclose(bogoliubov_spectrum(np.array([0.]),2)[0],2)
def test_coherence_sum():
 u,v=coherence_factors(np.linspace(-2,2,30),1); assert np.allclose(u+v,1)
def test_gap_zero_at_tc(): assert bcs_gap_temperature(np.array([1.]))[0]==0
def test_gap_monotone(): assert np.all(np.diff(bcs_gap_temperature(np.linspace(.01,.99,100)))<=1e-12)
def test_dos_nonnegative(): assert np.all(bcs_dos(np.linspace(-3,3,100),1)>=0)
def test_condensation_negative(): assert condensation_energy(1)<0
def test_nambu_symmetric():
 vals=np.linalg.eigvalsh(nambu_matrix(.4,.7)); assert np.allclose(vals,[-np.sqrt(.65),np.sqrt(.65)])
def test_pair_binding_attractive(): assert attractive_pair_binding_dimer(-4)<0
