import numpy as np
import pytest
import frequency_localization_scaling_lab as lab

def test_dynamic_hall_dc_matches_static():
    z=lab.dynamic_hall_chern_units(-1.0,0.0,1e-3,31)
    assert abs(z.real+1.0)<2e-5
    assert abs(z.imag)<1e-12

def test_dynamic_hall_trivial_dc_small():
    z=lab.dynamic_hall_chern_units(3.0,0.0,1e-3,31)
    assert abs(z.real)<2e-5

@pytest.mark.parametrize("w",[0.0,0.5,1.0,2.0,3.0])
def test_dynamic_hall_finite(w):
    z=lab.dynamic_hall_chern_units(-1.0,w,0.08,25)
    assert np.isfinite(z.real) and np.isfinite(z.imag)

def test_optical_nonnegative():
    assert lab.optical_sigma_xx_e2_over_hbar(-1.0,2.0,0.08,31)>=0

def test_optical_gap_suppression():
    low=lab.optical_sigma_xx_e2_over_hbar(-1.0,0.5,0.08,31)
    edge=lab.optical_sigma_xx_e2_over_hbar(-1.0,2.0,0.08,31)
    assert edge>20*low

def test_optical_spectrum_shape():
    o=np.linspace(0,4,9)
    s=lab.optical_spectrum(-1.0,o,0.08,25)
    assert s.shape==(9,) and np.all(s>=0)

def test_optical_bad_eta():
    with pytest.raises(ValueError): lab.optical_sigma_xx_e2_over_hbar(-1,1,-0.1,21)

def test_open_qwz_hermitian():
    H=lab.qwz_open_hamiltonian(5,-1,1.0,2)
    assert np.allclose(H,H.conj().T)

def test_open_qwz_dimension():
    assert lab.qwz_open_hamiltonian(4,-1).shape==(32,32)

def test_clean_local_marker_bulk_topological():
    C=lab.local_chern_marker(8,-1)
    assert lab.bulk_marker_average(C,2)<-0.98

def test_clean_local_marker_trivial_small():
    C=lab.local_chern_marker(8,3)
    assert abs(lab.bulk_marker_average(C,2))<0.08

def test_local_marker_shape():
    assert lab.local_chern_marker(6,-1).shape==(6,6)

def test_local_marker_finite():
    assert np.all(np.isfinite(lab.local_chern_marker(6,-1,2,0)))

def test_marker_disorder_weak_robust():
    e=lab.disorder_bulk_marker_ensemble(8,-1,2,range(3),2)
    assert e["mean"]<-0.95

def test_marker_strong_disorder_reduced():
    e=lab.disorder_bulk_marker_ensemble(8,-1,6,range(3),2)
    assert abs(e["mean"])<0.4

def test_marker_boundary_compensation():
    C=lab.local_chern_marker(8,-1)
    bulk=lab.bulk_marker_average(C,2)
    edge=(C.sum()-C[2:-2,2:-2].sum())/(C.size-C[2:-2,2:-2].size)
    assert bulk<0 and edge>0

@pytest.mark.parametrize("E,eps,t",[(0,0,1),(1,0.2,1),(0.5,-0.4,2)])
def test_transfer_matrix_determinant_one(E,eps,t):
    T=lab.transfer_matrix_1d(E,eps,t)
    assert abs(np.linalg.det(T)-1)<1e-14

def test_transfer_matrix_bad_t():
    with pytest.raises(ValueError): lab.transfer_matrix_1d(0,0,0)

def test_clean_inside_band_lyapunov_small():
    assert lab.lyapunov_exponent_1d(0,1,0,10000,0)<2e-5

@pytest.mark.parametrize("E",[2.1,2.5,3.0])
def test_clean_outside_band_matches_analytic(E):
    g=lab.lyapunov_exponent_1d(E,1,0,15000,0)
    assert abs(g-lab.clean_evanescent_lyapunov(E,1))<8e-5

@pytest.mark.parametrize("W",[0.5,1.0,2.0,4.0])
def test_disorder_positive_lyapunov(W):
    assert lab.lyapunov_exponent_1d(0,1,W,12000,1)>0

def test_localization_length_decreases_with_disorder():
    x1=lab.averaged_localization_length(0,1,0.8,10000,range(3))
    x2=lab.averaged_localization_length(0,1,2.0,10000,range(3))
    assert x1>x2

def test_xi_W1_reasonable():
    xi=lab.averaged_localization_length(0,1,1,14000,range(4))
    assert 80<xi<130

def test_weak_disorder_exponent_near_minus_two():
    f=lab.weak_disorder_scaling_fit(length=10000,seeds=range(3))
    assert -2.3<f["slope"]<-1.7

def test_scaling_fit_lengths_positive():
    f=lab.weak_disorder_scaling_fit(length=7000,seeds=range(2))
    assert all(x>0 for x in f["localization_lengths"])

@pytest.mark.parametrize("L,xi",[(0,10),(1,10),(5,10),(10,10),(20,10)])
def test_typical_transmission_bounds(L,xi):
    T=lab.typical_transmission_from_xi(L,xi)
    assert 0<=T<=1

def test_typical_transmission_exponential():
    T1=lab.typical_transmission_from_xi(5,20)
    T2=lab.typical_transmission_from_xi(10,20)
    assert abs(T2-T1*T1)<1e-14

def test_marker_curve_monotone_over_reference():
    c=lab.marker_disorder_curve(8,-1,(0,2,4,5,6),range(3),2)
    vals=np.abs(c["mean_markers"])
    assert np.all(np.diff(vals)<0)

def test_critical_proxy_bracket():
    c=lab.marker_disorder_curve(8,-1,(4,5,6),range(3),2)
    wc=lab.critical_disorder_proxy(c,0.5)
    assert 4.5<wc<5.5

def test_critical_proxy_unbracketed_rejected():
    c={"disorders":[0.,1.],"mean_markers":[-1.,-0.9]}
    with pytest.raises(ValueError): lab.critical_disorder_proxy(c,0.5)

@pytest.mark.parametrize("seed",[0,1,2])
def test_marker_W2_each_seed_topological(seed):
    C=lab.local_chern_marker(8,-1,2,seed)
    assert lab.bulk_marker_average(C,2)<-0.95

@pytest.mark.parametrize("seed",[0,1,2])
def test_marker_W6_each_seed_degraded(seed):
    C=lab.local_chern_marker(8,-1,6,seed)
    assert lab.bulk_marker_average(C,2)>-0.55

def test_reference_summary_consistent():
    r=lab.reference_summary()
    assert abs(r["dynamic_hall_dc_real"]+1)<2e-5
    assert r["optical_near_gap"]>20*r["optical_low"]
    assert r["bulk_marker_clean_L8"]<-0.98
    assert 80<r["xi_W1"]<130
    assert -2.3<r["weak_disorder_slope"]<-1.7
    assert 4.5<r["marker_half_proxy_W"]<5.5
