import numpy as np
import pytest
from topological_superconductors_companion import *

def test_01_uniform_bdg_particle_hole(): assert np.allclose(uniform_bdg_spectrum(2,3),[-np.sqrt(13),np.sqrt(13)])
def test_02_uniform_gap_at_fermi(): assert np.allclose(uniform_bdg_spectrum(0,.4),[-.4,.4])
def test_03_coherence_normalization():
    u2,v2=coherence_factors(.3,.7); assert u2+v2==pytest.approx(1)
def test_04_coherence_at_fermi(): assert coherence_factors(0,.7)==pytest.approx((.5,.5))
def test_05_andreev_subgap_unity(): assert andreev_probability(.2,1)==pytest.approx(1)
def test_06_andreev_above_gap_decreases(): assert andreev_probability(2,1)<1

def test_07_kitaev_spectrum_ph_symmetric():
    e=kitaev_spectrum(.7,mu=.2,t=1,delta=.8); assert e[0]==pytest.approx(-e[1])
def test_08_kitaev_topological(): assert kitaev_z2(0,1)==1
def test_09_kitaev_trivial(): assert kitaev_z2(3,1)==0
def test_10_kitaev_transition(): assert kitaev_z2(2,1) is None
def test_11_kitaev_gap_closes_boundary(): assert kitaev_bulk_gap(2,t=1,delta=1,n=2001)<1e-8
def test_12_open_bdg_hermitian():
    H=kitaev_open_bdg(12,mu=.4,t=1,delta=.7); assert np.linalg.norm(H-H.conj().T)<1e-12
def test_13_open_bdg_spectral_symmetry():
    e=np.linalg.eigvalsh(kitaev_open_bdg(10,mu=.2,t=1,delta=.8)); assert np.allclose(e,-e[::-1],atol=1e-10)
def test_14_exact_dimerization_zero_modes(): assert lowest_abs_open_energy(16,mu=0,t=1,delta=1)<1e-12

def test_15_majorana_envelope_decay(): assert majorana_envelope(10,5)==pytest.approx(np.exp(-2))
def test_16_majorana_splitting_envelope():
    a=abs(majorana_splitting(10,5,kf=0)); b=abs(majorana_splitting(15,5,kf=0)); assert b/a==pytest.approx(np.exp(-1))

def test_17_nanowire_hermitian():
    H=nanowire_hamiltonian(.4,mu=.2,alpha=.7,vz=.8,delta=.3); assert np.linalg.norm(H-H.conj().T)<1e-12
def test_18_nanowire_phs(): assert nanowire_phs_error(.51,mu=.2,alpha=.7,vz=.9,delta=.3)<1e-12
def test_19_nanowire_trivial_below_criterion(): assert nanowire_topological(.2,.3,.4)==0
def test_20_nanowire_topological_above_criterion(): assert nanowire_topological(.8,.3,.4)==1
def test_21_nanowire_transition_none(): assert nanowire_topological(.5,.3,.4) is None
def test_22_nanowire_gap_closes_at_k0_criterion(): assert nanowire_gap(mu=.3,vz=.5,delta=.4,n=1201)<1e-8

def test_23_pwave_hermitian():
    H=pwave_hamiltonian(.2,-.4,mu=-2); assert np.linalg.norm(H-H.conj().T)<1e-12
def test_24_pwave_chern_quantized_topological(): assert abs(round(pwave_chern(24,mu=-2)))==1
def test_25_pwave_chern_trivial(): assert pwave_chern(24,mu=-6)==pytest.approx(0,abs=1e-10)
def test_26_pwave_chern_random_gauge():
    a=pwave_chern(20,mu=-2); b=pwave_chern(20,mu=-2,random_gauge_seed=8); assert b==pytest.approx(a,abs=1e-10)
def test_27_pwave_gap_closes_mu_minus4(): assert pwave_bulk_gap(mu=-4,n=120)<1e-8

def test_28_diii_helical_kramers_crossing(): assert np.allclose(diii_helical_edge_energies(0),[0,0])
def test_29_diii_tr_breaking_mass_gaps(): assert np.allclose(diii_helical_edge_energies(0,tr_breaking_mass=.2),[-.2,.2])
def test_30_majorana_thermal_and_josephson():
    assert thermal_majorana_units(1)==pytest.approx(1); assert josephson_majorana_energy(2*np.pi)==pytest.approx(-1)
