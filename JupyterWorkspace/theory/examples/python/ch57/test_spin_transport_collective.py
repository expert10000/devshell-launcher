import importlib.util
from pathlib import Path
import numpy as np

MODULE = Path(__file__).with_name("spin_transport_collective.py")
spec = importlib.util.spec_from_file_location("spin_transport_collective", MODULE)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def test_spin_diffusion_length():
    assert abs(m.spin_diffusion_length(4.0, 9.0) - 6.0) < 1e-15


def test_diffusion_packet_initial_center():
    x = np.array([0.0])
    assert abs(m.diffusion_packet(x, 0.0, 1.0, 2.0, sigma0=0.5)[0] - 1.0) < 1e-15


def test_diffusion_variance_linear():
    assert abs(m.diffusion_variance(3.0, 0.7, 0.4) - (0.16 + 4.2)) < 1e-15


def test_diffusion_amplitude_decays():
    x = np.array([0.0])
    assert m.diffusion_packet(x, 2.0, 0.5, 3.0)[0] < m.diffusion_packet(x, 0.0, 0.5, 3.0)[0]


def test_magnon_dispersion_zero_at_k0_without_gap():
    assert abs(m.magnon_dispersion([0.0])[0]) < 1e-15


def test_magnon_dispersion_even():
    k = 0.83
    assert abs(m.magnon_dispersion([k])[0] - m.magnon_dispersion([-k])[0]) < 1e-15


def test_magnon_group_velocity_odd():
    k = 0.71
    assert abs(m.magnon_group_velocity([k])[0] + m.magnon_group_velocity([-k])[0]) < 1e-15


def test_dipolar_magic_angle_zero():
    assert abs(m.dipolar_angular_factor([m.magic_angle()])[0]) < 1e-14


def test_magic_angle_value():
    assert abs(m.magic_angle()*180/np.pi - 54.735610317245346) < 1e-12


def test_lorentzian_center_height():
    assert abs(m.lorentzian([0.0], gamma=2.0)[0] - 1/(2*np.pi)) < 1e-15


def test_motional_narrowing_faster_fluctuation_smaller_rate():
    assert m.motional_narrowing_rate(2.0, 0.1) < m.motional_narrowing_rate(2.0, 0.5)


def test_dicke_strength_top_state_is_N():
    for N in (1, 2, 5, 10):
        J = N/2
        assert abs(m.dicke_lowering_strength(N, J) - N) < 1e-15


def test_dicke_strength_middle_enhanced():
    N = 10
    assert m.dicke_lowering_strength(N, 0.0) > N


def test_superradiant_peak_scales_faster_than_independent():
    t = np.linspace(0, 2, 2000)
    p6 = m.superradiant_sech2(t, 6).max()
    p12 = m.superradiant_sech2(t, 12).max()
    assert p12/p6 > 3.5


def test_independent_initial_intensity_linear_N():
    assert m.independent_emission([0.0], 12)[0] == 2*m.independent_emission([0.0], 6)[0]


def test_ou_spectrum_is_even():
    w = np.array([-2.2, 2.2])
    s = m.ornstein_uhlenbeck_spectrum(w, tau_c=0.7)
    assert np.allclose(s[0], s[1])


def test_ou_spectrum_peaks_at_zero():
    assert m.ornstein_uhlenbeck_spectrum([0.0])[0] > m.ornstein_uhlenbeck_spectrum([3.0])[0]


def test_echo_filter_zero_frequency_cancelled():
    F = m.toggling_filter(np.array([0.0]), 1.0, [0.5])
    assert abs(F[0]) < 1e-15


def test_ramsey_filter_nonzero_at_zero():
    F = m.toggling_filter(np.array([0.0]), 1.0, [])
    assert abs(F[0] - 1.0) < 1e-15


def test_cpmg_times_inside_interval():
    pts = m.cpmg_pulse_times(1.0, 6)
    assert len(pts) == 6
    assert all(0 < p < 1 for p in pts)


def test_two_spin_bright_dark_orthogonal():
    b, d = m.bright_dark_two_spin()
    assert abs(np.vdot(b, d)) < 1e-15


def test_two_spin_dark_annihilated_by_collective_lowering():
    _, d = m.bright_dark_two_spin()
    Jm = m.collective_lowering_two_spin()
    assert np.linalg.norm(Jm @ d) < 1e-15


def test_two_spin_bright_not_dark():
    b, _ = m.bright_dark_two_spin()
    Jm = m.collective_lowering_two_spin()
    assert np.linalg.norm(Jm @ b) > 1.0
