import numpy as np
import pytest
import kubo_disorder_scattering_lab as lab

def test_qwz_hamiltonian_hermitian():
    H=lab.qwz_hamiltonian(0.3,-0.7,-1.0)
    assert np.allclose(H,H.conj().T)

def test_qwz_spectrum_particle_hole_symmetric():
    e=np.linalg.eigvalsh(lab.qwz_hamiltonian(0.4,0.8,-1.0))
    assert np.allclose(e[0],-e[1])

@pytest.mark.parametrize("m,expected",[(-3.0,0),(-1.0,-1),(1.0,1),(3.0,0)])
def test_qwz_phase_diagram_kubo(m,expected):
    c=lab.kubo_chern_number(m,41)
    assert abs(c-expected)<2e-6

@pytest.mark.parametrize("kx,ky,m",[(0.2,0.3,-1.0),(1.0,0.5,-1.0),(-0.8,1.2,1.0),(2.0,-1.0,3.0)])
def test_kubo_curvature_matches_dvector_formula(kx,ky,m):
    assert abs(lab.kubo_berry_curvature(kx,ky,m)-lab.dvector_berry_curvature(kx,ky,m))<2e-13

@pytest.mark.parametrize("nk,tol",[(11,3e-3),(21,3e-6),(31,3e-9),(41,3e-12)])
def test_kubo_chern_convergence_topological(nk,tol):
    assert abs(lab.kubo_chern_number(-1.0,nk)+1.0)<tol

@pytest.mark.parametrize("nk,tol",[(11,2e-3),(21,2e-6),(31,2e-9)])
def test_kubo_chern_trivial_converges_zero(nk,tol):
    assert abs(lab.kubo_chern_number(3.0,nk))<tol

@pytest.mark.parametrize("m",[ -1.0, 1.0 ])
def test_qwz_bulk_gap_reference_phases(m):
    assert lab.qwz_bulk_gap(m,81)>1.99

def test_qwz_realspace_hamiltonian_hermitian():
    H=lab.qwz_realspace_torus(4,-1.0,0.5,3)
    assert np.allclose(H,H.conj().T)

@pytest.mark.parametrize("m,expected",[(-3.0,0),(-1.0,-1),(1.0,1),(3.0,0)])
def test_clean_bott_phase_diagram(m,expected):
    b=lab.qwz_bott_index(5,m)
    assert abs(b-expected)<2e-10

@pytest.mark.parametrize("L",[4,5,6])
def test_bott_topological_finite_sizes(L):
    assert abs(lab.qwz_bott_index(L,-1.0)+1.0)<2e-10

@pytest.mark.parametrize("seed",[0,1,2,3])
def test_bott_robust_to_weak_disorder(seed):
    assert abs(lab.qwz_bott_index(6,-1.0,2.0,seed)+1.0)<2e-10

def test_disorder_bott_ensemble_all_topological_at_W2():
    r=lab.disorder_bott_ensemble(6,-1.0,2.0,seeds=range(4))
    assert r["topological_fraction"]==1.0
    assert all(v==-1 for v in r["rounded_values"])

def test_ssh_chain_hermitian():
    H=lab.ssh_chain_hamiltonian(8,0.8,1.2,bond_disorder=0.1,seed=2)
    assert np.allclose(H,H.conj().T)

@pytest.mark.parametrize("t1,t2",[(1.2,0.8),(0.8,1.2)])
def test_wideband_scattering_unitary(t1,t2):
    H=lab.ssh_chain_hamiltonian(12,t1,t2)
    S=lab.wideband_scattering_matrix(H,gamma_left=0.6,gamma_right=0.6)
    assert lab.scattering_unitarity_error(S)<2e-9

@pytest.mark.parametrize("t1,t2,expected",[(1.2,0.8,1),(0.8,1.2,-1)])
def test_ssh_reflection_invariant_clean(t1,t2,expected):
    assert lab.ssh_reflection_invariant(16,t1,t2)==expected

@pytest.mark.parametrize("seed",[0,1,2,3])
def test_topological_reflection_invariant_survives_bond_disorder(seed):
    assert lab.ssh_reflection_invariant(16,0.8,1.2,bond_disorder=0.2,seed=seed)==-1

def test_clean_matched_chain_has_unit_transmission():
    H=lab.uniform_chain(8)
    assert abs(lab.landauer_transmission(H,gamma_left=2.0,gamma_right=2.0)-1.0)<2e-11

def test_disorder_reduces_average_transmission():
    clean=lab.disorder_averaged_transmission(8,0.0,seeds=range(20),gamma=2.0)["mean"]
    dis=lab.disorder_averaged_transmission(8,2.0,seeds=range(20),gamma=2.0)["mean"]
    assert clean>0.999999 and dis<0.65

def test_symmetric_contact_peak_transmission_one():
    assert abs(lab.contact_limited_peak_transmission(1.0,1.0)-1.0)<1e-15

def test_asymmetric_contact_peak_transmission_reference():
    assert abs(lab.contact_limited_peak_transmission(1.0,0.25)-0.64)<1e-15

def test_single_level_resonant_peak():
    assert abs(lab.single_level_transmission(0.0,0.0,1.0,1.0)-1.0)<1e-15

def test_single_level_off_resonance_is_smaller():
    assert lab.single_level_transmission(1.0,0.0,1.0,1.0)<1.0

def test_reference_summary_consistent():
    r=lab.reference_summary()
    assert abs(r["kubo_chern_topological"]+1)<2e-12
    assert abs(r["kubo_chern_trivial"])<2e-12
    assert abs(r["bott_clean"]+1)<2e-10
    assert r["bott_disorder_W2"]["topological_fraction"]==1.0
    assert r["ssh_reflection_invariant_trivial"]==1
    assert r["ssh_reflection_invariant_topological"]==-1
    assert r["clean_chain_transmission"]>0.999999
    assert r["disordered_chain_W2"]["mean"]<0.65
    assert abs(r["asymmetric_contact_peak_T"]-0.64)<1e-15

@pytest.mark.parametrize("gamma_left,gamma_right",[(0.0,1.0),(1.0,-0.5)])
def test_invalid_lead_broadening_rejected(gamma_left,gamma_right):
    H=lab.uniform_chain(4)
    with pytest.raises(ValueError):
        lab.wideband_scattering_matrix(H,gamma_left=gamma_left,gamma_right=gamma_right)
