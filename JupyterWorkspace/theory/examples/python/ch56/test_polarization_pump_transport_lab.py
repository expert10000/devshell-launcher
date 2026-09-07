import numpy as np
import pytest
import polarization_pump_transport_lab as lab

def test_ssh_hamiltonian_hermitian():
    assert np.allclose(lab.ssh_hamiltonian(0.37,1.2,0.8), lab.ssh_hamiltonian(0.37,1.2,0.8).conj().T)

def test_ssh_spectrum_symmetric():
    e=np.linalg.eigvalsh(lab.ssh_hamiltonian(0.4,0.8,1.2)); assert np.allclose(e[0],-e[1])

@pytest.mark.parametrize("k",[0.0,np.pi,-np.pi])
def test_inversion_momenta_hamiltonian_commutes_with_sigma_x(k):
    H=lab.ssh_hamiltonian(k,1.2,0.8); assert np.allclose(H@lab.SIGMA_X,lab.SIGMA_X@H)

def test_trivial_zak_zero():
    g=lab.zak_phase_ssh(1.2,0.8,801); assert min(abs(g),abs(g-2*np.pi))<2e-6

def test_topological_zak_pi():
    g=lab.zak_phase_ssh(0.8,1.2,801); assert abs(g-np.pi)<2e-6

def test_trivial_polarization_zero():
    g=lab.zak_phase_ssh(1.2,0.8,801); p=lab.polarization_branch_from_zak(g); assert min(abs(p),abs(p-1.0))<2e-6

def test_topological_polarization_half():
    g=lab.zak_phase_ssh(0.8,1.2,801); assert abs(lab.polarization_branch_from_zak(g)-0.5)<2e-6

def test_trivial_parities():
    d=lab.inversion_indicator_ssh(1.2,0.8); assert d["product"]==1 and d["z2"]==0

def test_topological_parities():
    d=lab.inversion_indicator_ssh(0.8,1.2); assert d["product"]==-1 and d["z2"]==1

def test_parity_matches_zak_trivial():
    d=lab.inversion_indicator_ssh(1.2,0.8); g=lab.zak_phase_ssh(1.2,0.8); assert d["product"]==(1 if np.cos(g)>0 else -1)

def test_parity_matches_zak_topological():
    d=lab.inversion_indicator_ssh(0.8,1.2); g=lab.zak_phase_ssh(0.8,1.2); assert d["product"]==(1 if np.cos(g)>0 else -1)

def test_rice_mele_hermitian():
    H=lab.rice_mele_hamiltonian(0.7,1.1); assert np.allclose(H,H.conj().T)

@pytest.mark.parametrize("theta",[0.0,0.5,1.0,2.0,3.0,5.0])
def test_rice_mele_gap_positive_at_sampled_cycle(theta):
    ks=np.linspace(-np.pi,np.pi,161,endpoint=False)
    assert min(lab.direct_gap(lab.rice_mele_hamiltonian(k,theta)) for k in ks)>0.2

def test_reference_pump_min_gap_positive():
    assert lab.minimum_rice_mele_gap(nk=61,ntheta=61)>0.5

@pytest.mark.parametrize("n",[21,31,41,51])
def test_pump_chern_quantized(n):
    assert abs(lab.chern_rice_mele(nk=n,ntheta=n))==1

def test_pump_chern_mesh_stable():
    c1=lab.chern_rice_mele(nk=31,ntheta=31); c2=lab.chern_rice_mele(nk=51,ntheta=51); assert c1==c2

def test_pump_charge_equals_chern():
    assert lab.pump_charge_e_units(nk=41,ntheta=41)==lab.chern_rice_mele(nk=41,ntheta=41)

def test_reverse_pump_orientation_flips_chern():
    c1=lab.chern_rice_mele(delta0=0.6,nk=41,ntheta=41)
    c2=lab.chern_rice_mele(delta0=-0.6,nk=41,ntheta=41)
    assert c1==-c2

@pytest.mark.parametrize("dt",[0.2,0.3,0.35,0.45])
def test_nontrivial_pump_for_reasonable_loop(dt):
    assert abs(lab.chern_rice_mele(delta_t=dt,delta0=0.6,nk=31,ntheta=31))==1

@pytest.mark.parametrize("d0",[0.3,0.5,0.6,0.8])
def test_nontrivial_pump_for_reasonable_stagger(d0):
    assert abs(lab.chern_rice_mele(delta_t=0.35,delta0=d0,nk=31,ntheta=31))==1

def test_zero_delta_t_is_gap_closing_limit():
    assert lab.minimum_rice_mele_gap(delta_t=0.0,delta0=0.6,nk=80,ntheta=80)<1e-10

def test_normalized_overlap_unit_modulus():
    u=lab.occupied_vector(lab.ssh_hamiltonian(0.1,1.2,0.8))
    v=lab.occupied_vector(lab.ssh_hamiltonian(0.2,1.2,0.8))
    assert abs(abs(lab.normalized_overlap(u,v))-1)<1e-14

def test_occupied_vector_normalized():
    u=lab.occupied_vector(lab.ssh_hamiltonian(0.42,0.8,1.2)); assert abs(np.vdot(u,u)-1)<1e-14

def test_direct_gap_positive():
    assert lab.direct_gap(lab.ssh_hamiltonian(0.4,1.2,0.8))>0

def test_qsh_one_pair_conductance():
    assert lab.ideal_qsh_two_terminal_conductance_e2_over_h(1)==2

@pytest.mark.parametrize("n,expected",[(0,0),(1,2),(2,4),(3,6)])
def test_qsh_channel_count(n,expected):
    assert lab.ideal_qsh_two_terminal_conductance_e2_over_h(n)==expected

def test_qsh_negative_pairs_rejected():
    with pytest.raises(ValueError): lab.ideal_qsh_two_terminal_conductance_e2_over_h(-1)

@pytest.mark.parametrize("C",[-3,-1,0,1,2])
def test_chern_hall_conversion(C):
    assert lab.ideal_chern_hall_conductance_e2_over_h(C)==C

def test_reference_summary_consistent():
    r=lab.reference_summary()
    assert abs(r["pump_chern"])==1
    assert r["indicator_trivial"]["z2"]==0
    assert r["indicator_topological"]["z2"]==1
    assert abs(r["zak_topological"]-np.pi)<2e-6
    assert r["qsh_two_terminal_e2_over_h_one_pair"]==2
