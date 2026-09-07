import numpy as np
from bdg_josephson import *
def test_bdg_symmetry():
 m,p=bdg_spectrum(np.array([-.2,.4]),1); assert np.allclose(m,-p)
def test_gap_boundary(): assert gap_profile(np.array([0.]))[0]==0
def test_gap_recovers(): assert gap_profile(np.array([8.]))[0]>.999
def test_meissner_monotone(): assert np.all(np.diff(meissner_field(np.linspace(0,5,50)))<0)
def test_ring_minimum(): assert ring_energy(np.array([1.]),1)[0]==0
def test_josephson_periodic(): assert np.isclose(josephson_energy(0),josephson_energy(2*np.pi))
def test_current_zero(): assert np.isclose(josephson_current(0),0)
def test_squid_node(): assert squid_critical_current(np.array([.5]))[0]<1e-12
def test_andreev_positive(): assert np.all(andreev_energy(np.linspace(-np.pi,np.pi,30),tau=.9)>=0)
def test_andreev_current_odd(): assert np.isclose(andreev_current(-.8),-andreev_current(.8))
