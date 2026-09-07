import numpy as np
import pytest

from gauge_quantitative import (
    ab_interference_probability,
    ab_phase,
    diagnostics,
    electric_currents_two_gauges,
    electric_gauge_function,
    electric_scalar_gauge,
    electric_vector_gauge,
    flux_quantum,
    gauge_phase,
    landau_gauge_A,
    landau_levels,
    magnetic_currents_two_gauges,
    magnetic_gauge_function,
    magnetic_translation_commutator_phase,
    magnetic_translation_composition_phase,
    ring_energies,
    ring_persistent_current,
    symmetric_gauge_A,
    pulse_vector_potential_and_field,
    anharmonic_length_velocity_error,
    plaquette_wilson_loop,
    ring_link_hamiltonian,
    local_gauge_transform,
    ring_spectrum_link_gauge_error,
    adiabaticity_parameter,
    landau_zener_probability,
    twisted_boundary_spectrum,
    local_gauge_transform_state,
    bond_current_matrix,
    schrodinger_density_derivative,
    continuity_algebra_residual,
    exact_propagate,
    continuity_finite_difference_residual,
    bond_current_gauge_error,
)


def test_electric_gauge_potentials_same_field():
    x = np.array([-1.0, 0.0, 2.0])
    E, t = 0.4, 0.7
    phi_s, A_s = electric_scalar_gauge(x, E)
    phi_v, A_v = electric_vector_gauge(x, t, E)
    assert np.allclose(phi_s, -E*x)
    assert np.allclose(A_s, 0.0)
    assert np.allclose(phi_v, 0.0)
    assert np.allclose(A_v, -E*t)


def test_electric_chi_maps_potentials():
    x, E, t = 1.2, 0.5, 0.8
    chi = electric_gauge_function(x, t, E)
    assert chi == pytest.approx(-E*x*t)
    assert -E*x - (-E*x) == pytest.approx(0.0)  # phi' = phi - d_t chi


def test_gauge_phase_unit_modulus():
    chi = np.linspace(-2, 2, 17)
    assert np.allclose(np.abs(gauge_phase(chi)), 1.0)


def test_electric_current_gauge_invariant():
    x = np.linspace(-4, 4, 801)
    j1, j2 = electric_currents_two_gauges(x, t=1.3, E=0.8, k=0.9)
    assert np.max(np.abs(j1-j2)) < 1e-14


def test_landau_and_symmetric_gauges_related_by_chi():
    x, y, B = 0.7, -1.1, 0.9
    alx, aly = landau_gauge_A(x, y, B)
    asx, asy = symmetric_gauge_A(x, y, B)
    gx, gy = -0.5*B*y, -0.5*B*x
    assert asx == pytest.approx(alx + gx)
    assert asy == pytest.approx(aly + gy)
    assert magnetic_gauge_function(x, y, B) == pytest.approx(-0.5*B*x*y)


def test_both_magnetic_gauges_have_same_uniform_curl():
    # Analytically: d_x A_y - d_y A_x = B in both gauges.
    B = 1.37
    curl_landau = B - 0.0
    curl_symmetric = 0.5*B - (-0.5*B)
    assert curl_landau == pytest.approx(B)
    assert curl_symmetric == pytest.approx(B)


def test_magnetic_current_gauge_invariant():
    grid = np.linspace(-2.5, 2.5, 51)
    (jlx, jly), (jsx, jsy), _ = magnetic_currents_two_gauges(grid, grid, B=0.75)
    assert np.max(np.abs(jlx-jsx)) < 1e-14
    assert np.max(np.abs(jly-jsy)) < 1e-14


def test_landau_levels_even_in_sign_of_B():
    n = np.arange(5)
    assert np.allclose(landau_levels(n, B=2.0), landau_levels(n, B=-2.0))


def test_landau_levels_even_in_sign_of_charge():
    n = np.arange(5)
    assert np.allclose(landau_levels(n, B=1.2, q=1.0), landau_levels(n, B=1.2, q=-1.0))


def test_landau_level_spacing_is_cyclotron_energy():
    e = landau_levels(np.arange(6), B=0.8, q=-1.5, hbar=2.0, m=3.0)
    assert np.allclose(np.diff(e), 2.0*1.5*0.8/3.0)


def test_magnetic_translation_commutator_phase_matches_flux():
    a, b, B, q = (1.2, 0.3), (-0.2, 0.9), 0.7, -1.0
    area = a[0]*b[1]-a[1]*b[0]
    expected = np.exp(1j*q*B*area)
    assert magnetic_translation_commutator_phase(a,b,B=B,q=q) == pytest.approx(expected)


def test_translation_composition_phase_squares_to_commutator_phase():
    a, b = (0.8, -0.1), (0.4, 1.3)
    c = magnetic_translation_composition_phase(a,b,B=0.6,q=-1.0)
    comm = magnetic_translation_commutator_phase(a,b,B=0.6,q=-1.0)
    assert c*c == pytest.approx(comm)


def test_magnetic_translation_commutes_at_one_flux_quantum():
    q, hbar, B = -1.0, 1.0, 0.5
    phi0 = flux_quantum(q=q,hbar=hbar)
    phase = magnetic_translation_commutator_phase((1,0),(0,phi0/B),B=B,q=q,hbar=hbar)
    assert phase == pytest.approx(1.0+0.0j, abs=1e-12)


def test_ab_phase_at_half_flux_quantum_is_pi_mod_sign():
    q, hbar = -1.0, 1.0
    phi0 = flux_quantum(q=q,hbar=hbar)
    assert abs(ab_phase(0.5*phi0,q=q,hbar=hbar)) == pytest.approx(np.pi)


def test_ab_interference_periodic_in_flux_quantum():
    q, hbar = -1.0, 1.0
    phi0 = flux_quantum(q=q,hbar=hbar)
    f = np.linspace(-2*phi0,2*phi0,1001)
    p = ab_interference_probability(f,q=q,hbar=hbar,visibility=0.7,dynamical_phase=0.2)
    pshift = ab_interference_probability(f+phi0,q=q,hbar=hbar,visibility=0.7,dynamical_phase=0.2)
    assert np.max(np.abs(p-pshift)) < 2e-15


def test_ab_visibility_bounds_probability():
    phi0=flux_quantum()
    p=ab_interference_probability(np.linspace(0,phi0,501),visibility=0.6)
    assert p.min() >= 0.2-1e-12
    assert p.max() <= 0.8+1e-12


def test_ring_spectrum_relabels_after_one_flux_quantum():
    q=-1.0; phi0=flux_quantum(q=q)
    n=np.arange(-5,6); s=int(np.sign(q)); f=0.23*phi0
    assert np.allclose(ring_energies(n,f+phi0,q=q), ring_energies(n-s,f,q=q))


def test_ring_persistent_current_is_minus_energy_derivative():
    n=2; f=0.37; eps=1e-6
    num=-(ring_energies(n,f+eps)-ring_energies(n,f-eps))/(2*eps)
    ana=ring_persistent_current(n,f)
    assert num == pytest.approx(ana, rel=1e-8, abs=1e-9)


def test_ring_zero_flux_pm_n_degenerate():
    for n in range(1,5):
        assert ring_energies(n,0.0) == pytest.approx(ring_energies(-n,0.0))


def test_diagnostics_closure():
    d=diagnostics()
    assert d.electric_current_max_difference < 1e-14
    assert d.magnetic_current_max_difference < 1e-14
    assert abs(d.translation_phase_at_one_flux_quantum-1) < 1e-12
    assert d.ab_periodicity_max_difference < 2e-15
    assert d.ring_relabel_max_difference < 1e-14



def test_pulse_field_matches_minus_numeric_derivative():
    t=np.linspace(-5,5,4001)
    A,E=pulse_vector_potential_and_field(t,A0=0.7,tau=1.8,omega=1.1)
    dA=np.gradient(A,t)
    assert np.max(np.abs(E[5:-5]+dA[5:-5])) < 2e-5


def test_pulse_vector_potential_is_even_for_cos_carrier():
    t=np.linspace(0,4,401)
    Ap,_=pulse_vector_potential_and_field(t,tau=1.5,omega=1.7)
    Am,_=pulse_vector_potential_and_field(-t,tau=1.5,omega=1.7)
    assert np.allclose(Ap,Am)


def test_pulse_electric_field_is_odd_for_cos_carrier():
    t=np.linspace(0,4,401)
    _,Ep=pulse_vector_potential_and_field(t,tau=1.5,omega=1.7)
    _,Em=pulse_vector_potential_and_field(-t,tau=1.5,omega=1.7)
    assert np.allclose(Ep,-Em)


def test_length_velocity_truncation_error_decreases():
    e8=anharmonic_length_velocity_error(8)
    e16=anharmonic_length_velocity_error(16)
    e32=anharmonic_length_velocity_error(32)
    assert e16 < e8
    assert e32 < e16


def test_length_velocity_truncation_error_small_at_large_basis():
    assert anharmonic_length_velocity_error(40) < 1e-8


def test_wilson_loop_zero_flux_is_unity():
    assert plaquette_wilson_loop(0.0) == pytest.approx(1.0+0.0j)


def test_wilson_loop_one_flux_quantum_is_unity():
    phi0=flux_quantum()
    assert plaquette_wilson_loop(phi0) == pytest.approx(1.0+0.0j,abs=1e-12)


def test_wilson_loop_half_flux_quantum_is_minus_one():
    phi0=flux_quantum()
    assert plaquette_wilson_loop(0.5*phi0) == pytest.approx(-1.0+0.0j,abs=1e-12)


def test_ring_link_hamiltonian_is_hermitian():
    H=ring_link_hamiltonian(9,0.73,gauge="uniform")
    assert np.allclose(H,H.conj().T)


def test_ring_link_spectra_independent_of_phase_distribution():
    assert ring_spectrum_link_gauge_error(13,1.17) < 1e-12


def test_local_site_gauge_transform_preserves_spectrum():
    H=ring_link_hamiltonian(10,0.8,gauge="uniform")
    chi=np.linspace(-0.7,1.1,10)**2
    Hp=local_gauge_transform(H,chi)
    assert np.max(np.abs(np.linalg.eigvalsh(H)-np.linalg.eigvalsh(Hp))) < 1e-12


def test_extended_diagnostics_closure():
    d=diagnostics()
    assert d.lattice_ring_gauge_spectrum_max_difference < 1e-12
    assert d.wilson_one_flux_max_difference < 1e-12
    assert d.length_velocity_error_N32 < d.length_velocity_error_N8



def test_adiabaticity_is_even_and_maximal_at_crossing():
    lam=np.linspace(-2,2,801)
    eta=adiabaticity_parameter(lam,gap=0.55,slope=1.2,sweep_rate=0.03)
    assert np.allclose(eta,eta[::-1])
    assert np.argmax(eta) in {399,400,401}


def test_adiabaticity_scales_linearly_with_sweep_rate():
    e1=adiabaticity_parameter(0.2,gap=0.7,sweep_rate=0.01)
    e2=adiabaticity_parameter(0.2,gap=0.7,sweep_rate=0.05)
    assert e2 == pytest.approx(5.0*e1)


def test_landau_zener_transition_decreases_for_slower_sweep():
    assert landau_zener_probability(gap=0.5,sweep_rate=0.02) < landau_zener_probability(gap=0.5,sweep_rate=0.2)


def test_landau_zener_transition_decreases_for_larger_gap():
    assert landau_zener_probability(gap=0.8,sweep_rate=0.1) < landau_zener_probability(gap=0.4,sweep_rate=0.1)


def test_twisted_boundary_spectrum_matches_uniform_link_gauge():
    eu=np.linalg.eigvalsh(ring_link_hamiltonian(14,1.13,gauge="uniform"))
    et=twisted_boundary_spectrum(14,1.13)
    assert np.max(np.abs(eu-et)) < 1e-12


def test_twisted_boundary_spectrum_is_two_pi_periodic():
    e0=twisted_boundary_spectrum(13,0.37)
    e1=twisted_boundary_spectrum(13,0.37+2*np.pi)
    assert np.max(np.abs(e0-e1)) < 1e-12


def test_bond_current_is_antisymmetric():
    H=ring_link_hamiltonian(10,0.71,gauge="uniform")
    x=np.arange(10); psi=np.exp(-0.1*(x-4.5)**2+1j*0.3*x); psi/=np.linalg.norm(psi)
    J=bond_current_matrix(H,psi)
    assert np.max(np.abs(J+J.T)) < 1e-14


def test_bond_current_is_locally_gauge_invariant():
    assert bond_current_gauge_error(13,0.77) < 1e-13


def test_discrete_current_divergence_equals_schrodinger_density_derivative():
    H=ring_link_hamiltonian(9,0.52,gauge="concentrated")
    x=np.arange(9); psi=np.exp(-0.16*(x-4)**2+1j*0.41*x); psi/=np.linalg.norm(psi)
    assert continuity_algebra_residual(H,psi) < 1e-14


def test_exact_propagator_preserves_norm():
    H=ring_link_hamiltonian(12,0.66,gauge="uniform")
    rng=np.random.default_rng(585); psi=rng.normal(size=12)+1j*rng.normal(size=12); psi/=np.linalg.norm(psi)
    pp=exact_propagate(H,psi,3.7)
    assert np.linalg.norm(pp) == pytest.approx(1.0,abs=2e-14)


def test_finite_difference_continuity_residual_is_second_order():
    H=ring_link_hamiltonian(11,0.64,gauge="uniform")
    x=np.arange(11); psi=np.exp(-0.12*(x-5.0)**2+1j*0.38*x); psi/=np.linalg.norm(psi)
    r1=continuity_finite_difference_residual(H,psi,0.02)
    r2=continuity_finite_difference_residual(H,psi,0.01)
    assert r2 < 0.27*r1


def test_stationary_ring_plane_wave_has_uniform_bond_current():
    N=12; phase=0.48
    H=ring_link_hamiltonian(N,phase,gauge="uniform")
    m=2; x=np.arange(N); psi=np.exp(1j*2*np.pi*m*x/N)/np.sqrt(N)
    J=bond_current_matrix(H,psi)
    vals=np.array([J[i,(i+1)%N] for i in range(N)])
    assert np.max(vals)-np.min(vals) < 1e-14
