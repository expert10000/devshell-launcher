import numpy as np
import pytest
import exchange_chain_lab as lab


def test_xyz_dimer_hermitian():
    H=lab.xyz_dimer_hamiltonian(1.1,0.8,1.4,Dz=0.3,h=0.2)
    assert np.allclose(H,H.conj().T)

@pytest.mark.parametrize('n',[2,3,4,5])
def test_chain_dimensions(n):
    assert lab.chain_hamiltonian(n).shape==(2**n,2**n)

@pytest.mark.parametrize('n',[2,3,4])
def test_chain_hermitian_xyz_dm(n):
    H=lab.chain_hamiltonian(n,Jx=1.0,Jy=0.8,Jz=1.2,Dz=0.27,h=0.13,periodic=(n>2))
    assert np.allclose(H,H.conj().T)


def test_isotropic_dimer_spectrum():
    e=np.linalg.eigvalsh(lab.xyz_dimer_hamiltonian(1,1,1))
    assert np.allclose(e,[-0.75,0.25,0.25,0.25])


def test_reference_xxz_dimer_spectrum():
    e=np.linalg.eigvalsh(lab.xyz_dimer_hamiltonian(1,1,1.5))
    assert np.allclose(e,[-0.875,0.125,0.375,0.375])


def test_dm_dimer_reference_spectrum():
    e=np.linalg.eigvalsh(lab.xyz_dimer_hamiltonian(1,1,1,Dz=0.4))
    assert np.allclose(e,[-0.7885164807134504,0.25,0.25,0.28851648071345065])


def test_dm_zero_restores_heisenberg():
    assert np.allclose(lab.xyz_dimer_hamiltonian(1,1,1,Dz=0),lab.xyz_dimer_hamiltonian(1,1,1))


def test_dm_spectrum_even_in_D():
    ep=np.linalg.eigvalsh(lab.xyz_dimer_hamiltonian(1,1,1,Dz=0.4))
    em=np.linalg.eigvalsh(lab.xyz_dimer_hamiltonian(1,1,1,Dz=-0.4))
    assert np.allclose(ep,em)


def test_dm_chirality_changes_sign_with_D():
    _,pp=lab.ground_state(lab.xyz_dimer_hamiltonian(1,1,1,Dz=0.4))
    _,pm=lab.ground_state(lab.xyz_dimer_hamiltonian(1,1,1,Dz=-0.4))
    cp=lab.dm_chirality_z(pp,0,1,2); cm=lab.dm_chirality_z(pm,0,1,2)
    assert np.isclose(cp,-cm,atol=1e-12)


def test_dm_reference_chirality():
    _,p=lab.ground_state(lab.xyz_dimer_hamiltonian(1,1,1,Dz=0.4))
    assert np.isclose(lab.dm_chirality_z(p,0,1,2),-0.1856953381770518)

@pytest.mark.parametrize('n',[2,3,4])
def test_total_sz_hermitian(n):
    M=lab.total_sz_operator(n); assert np.allclose(M,M.conj().T)


def test_xxz_conserves_total_sz():
    H=lab.chain_hamiltonian(5,Jx=1,Jy=1,Jz=1.3,Dz=0.0,h=0.2)
    M=lab.total_sz_operator(5)
    assert np.linalg.norm(H@M-M@H)<1e-12


def test_z_dm_conserves_total_sz():
    H=lab.chain_hamiltonian(5,Jx=1,Jy=1,Jz=1.3,Dz=0.4,h=0.2)
    M=lab.total_sz_operator(5)
    assert np.linalg.norm(H@M-M@H)<1e-12


def test_xyz_breaks_total_sz_when_jx_ne_jy():
    H=lab.chain_hamiltonian(4,Jx=1.2,Jy=0.7,Jz=1.0)
    M=lab.total_sz_operator(4)
    assert np.linalg.norm(H@M-M@H)>1e-3


def test_open_n6_heisenberg_ground_energy():
    e,_=lab.ground_state(lab.chain_hamiltonian(6))
    assert np.isclose(e,-2.4935771338879253,atol=1e-12)


def test_open_n6_heisenberg_gap():
    assert np.isclose(lab.spectral_gap(lab.chain_hamiltonian(6)),0.4915817769893871,atol=1e-12)

@pytest.mark.parametrize('n',[4,6,8])
def test_even_open_af_ground_magnetization_zero(n):
    _,p=lab.ground_state(lab.chain_hamiltonian(n))
    assert abs(lab.magnetization_z(p,n,per_site=False))<1e-10


def test_middle_bond_antiferromagnetic():
    _,p=lab.ground_state(lab.chain_hamiltonian(6))
    assert lab.spin_correlation(p,2,3,6,'dot') < -0.5


def test_reference_middle_bond():
    _,p=lab.ground_state(lab.chain_hamiltonian(6))
    assert np.isclose(lab.spin_correlation(p,2,3,6,'dot'),-0.6075724137490668,atol=1e-12)

@pytest.mark.parametrize('component',['xx','yy','zz','dot'])
def test_correlation_is_real(component):
    _,p=lab.ground_state(lab.chain_hamiltonian(4,Jx=1,Jy=.9,Jz=1.1,Dz=.2))
    x=lab.spin_correlation(p,0,1,4,component); assert np.isfinite(x)


def test_isotropic_ground_correlations_component_equal():
    _,p=lab.ground_state(lab.chain_hamiltonian(6))
    vals=[lab.spin_correlation(p,2,3,6,c) for c in ['xx','yy','zz']]
    assert max(vals)-min(vals)<1e-11


def test_structure_factor_pi_reference():
    _,p=lab.ground_state(lab.chain_hamiltonian(6))
    assert np.isclose(lab.structure_factor_zz(p,6,np.pi),0.7052153237226128,atol=1e-12)


def test_structure_factor_pi_exceeds_zero_for_af_chain():
    _,p=lab.ground_state(lab.chain_hamiltonian(6))
    assert lab.structure_factor_zz(p,6,np.pi)>lab.structure_factor_zz(p,6,0.0)


def test_connected_correlator_matches_definition():
    _,p=lab.ground_state(lab.chain_hamiltonian(4,h=.3))
    mz=lab.local_magnetizations_z(p,4)
    expected=lab.spin_correlation(p,0,1,4,'zz')-mz[0]*mz[1]
    assert np.isclose(lab.connected_zz_correlation(p,0,1,4),expected)


def test_bond_correlations_length_open():
    _,p=lab.ground_state(lab.chain_hamiltonian(6))
    assert len(lab.bond_correlations(p,6,periodic=False))==5


def test_bond_correlations_length_periodic():
    _,p=lab.ground_state(lab.chain_hamiltonian(6,periodic=True))
    assert len(lab.bond_correlations(p,6,periodic=True))==6


def test_periodic_chain_translation_uniform_bonds():
    _,p=lab.ground_state(lab.chain_hamiltonian(6,periodic=True))
    b=lab.bond_correlations(p,6,periodic=True)
    assert np.max(b)-np.min(b)<1e-10


def test_magnetization_curve_reference():
    fields=np.array([0,.5,1,1.5,2,2.5])
    m=lab.magnetization_curve(6,fields,Jx=1,Jy=1,Jz=1,periodic=False)
    assert np.allclose(m,[0,1/6,1/6,1/3,1/2,1/2],atol=1e-10)


def test_magnetization_nondecreasing_with_field():
    fields=np.linspace(0,3,13)
    m=lab.magnetization_curve(6,fields,Jx=1,Jy=1,Jz=1,periodic=False)
    assert np.all(np.diff(m)>=-1e-10)


def test_high_field_saturates():
    _,p=lab.ground_state(lab.chain_hamiltonian(6,h=4.0))
    assert np.isclose(lab.magnetization_z(p,6),0.5,atol=1e-12)


def test_zero_field_spin_flip_symmetry_gives_zero_local_mz_even_chain():
    _,p=lab.ground_state(lab.chain_hamiltonian(6))
    assert np.max(np.abs(lab.local_magnetizations_z(p,6)))<1e-10


def test_anisotropy_changes_gap():
    g1=lab.spectral_gap(lab.chain_hamiltonian(6,Jx=1,Jy=1,Jz=1))
    g2=lab.spectral_gap(lab.chain_hamiltonian(6,Jx=1,Jy=1,Jz=1.8))
    assert abs(g1-g2)>1e-2


def test_dm_changes_open_chain_ground_energy():
    e0,_=lab.ground_state(lab.chain_hamiltonian(5,Dz=0))
    ed,_=lab.ground_state(lab.chain_hamiltonian(5,Dz=.4))
    assert ed < e0-1e-2


def test_ground_state_normalized():
    _,p=lab.ground_state(lab.chain_hamiltonian(7))
    assert np.isclose(np.vdot(p,p),1.0)


def test_spectral_gap_positive_even_open_chain():
    assert lab.spectral_gap(lab.chain_hamiltonian(8))>0


def test_invalid_chain_size_rejected():
    with pytest.raises(ValueError): lab.chain_hamiltonian(1)


def test_invalid_site_rejected():
    with pytest.raises(ValueError): lab.op_on_site(lab.SZ,4,4)


def test_same_site_two_site_operator_rejected():
    with pytest.raises(ValueError): lab.two_site_op(lab.SX,1,lab.SY,1,4)


def test_invalid_correlation_component_rejected():
    _,p=lab.ground_state(lab.chain_hamiltonian(4))
    with pytest.raises(ValueError): lab.spin_correlation(p,0,1,4,'bad')


def test_reference_summary_keys_and_values():
    r=lab.reference_summary()
    assert np.isclose(r['heisenberg_n6_gap'],0.4915817769893871)
    assert np.isclose(r['dm_dimer_chirality_z'],-0.1856953381770518)
    assert len(r['magnetization_per_site'])==6
