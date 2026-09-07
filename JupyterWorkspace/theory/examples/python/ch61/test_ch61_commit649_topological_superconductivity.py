import numpy as np
from topological_superconductivity import *
def test_bulk_gap_nonnegative(): assert bulk_gap(.3)>=0
def test_phase_criterion(): assert topological(0) and not topological(3)
def test_bdg_hermitian():
    H=kitaev_bdg(8,.4); assert np.allclose(H,H.conj().T)
def test_spectrum_particle_hole():
    e=spectrum(10,.3); assert np.allclose(e,-e[::-1],atol=1e-10)
def test_topological_has_small_open_mode(): assert min_abs_energy(40,.2)<1e-5
def test_trivial_open_mode_not_zero(): assert min_abs_energy(30,3.0)>0.2
def test_profile_normalized(): assert np.isclose(lowest_mode_profile(20,.2).sum(),1)
def test_profile_edge_weight():
    p=lowest_mode_profile(50,.2); assert p[:5].sum()+p[-5:].sum()>.7
def test_winding_distinguishes_phases():
    assert abs(winding_number(.2))==1 and winding_number(3.0)==0
def test_disorder_stat_nonnegative(): assert disorder_gap_stat(18,.2,1.0,samples=4)>=0
def test_nanowire_critical_field_positive(): assert np.all(nanowire_critical_field(np.array([-1.,0.,1.]))>0)
