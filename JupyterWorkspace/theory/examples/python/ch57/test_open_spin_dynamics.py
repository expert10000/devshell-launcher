import importlib.util
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve()
MODULE = HERE.with_name("open_spin_dynamics.py")
spec = importlib.util.spec_from_file_location("open_spin_dynamics", MODULE)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def test_thermal_zero_temperature_limit():
    assert m.thermal_excited_population(50.0) < 1e-20
    assert m.equilibrium_rz(50.0) >= 1.0 - 1e-14


def test_thermal_infinite_temperature_limit():
    assert abs(m.thermal_excited_population(0.0) - 0.5) < 1e-15
    assert abs(m.equilibrium_rz(0.0)) < 1e-15


def test_t1_rate_sum():
    assert abs(m.t1_from_rates(0.7, 0.3) - 1.0) < 1e-15


def test_t2_relaxation_only_bound_saturated():
    t1 = 3.0
    assert abs(m.t2_from_t1_tphi(t1, np.inf) - 2*t1) < 1e-15


def test_t2_with_pure_dephasing_is_shorter_than_2t1():
    assert m.t2_from_t1_tphi(2.0, 5.0) < 4.0


def test_rz_relaxes_to_equilibrium():
    t = np.array([0.0, 100.0])
    rz = m.relax_rz(t, -1.0, 0.6, 2.0)
    assert abs(rz[0] + 1.0) < 1e-15
    assert abs(rz[-1] - 0.6) < 1e-12


def test_coherence_one_at_zero():
    assert m.coherence_envelope([0.0], 2.0)[0] == 1.0


def test_quasistatic_gaussian_even_in_time():
    assert np.allclose(
        m.quasistatic_gaussian_envelope([-2.0, 2.0], 0.4),
        [np.exp(-0.5*(0.8)**2)]*2,
    )


def test_bloch_trajectory_initial_condition():
    r0 = np.array([0.3, -0.4, 0.2])
    tr = m.bloch_trajectory([0.0], r0, 2.0, 3.0, 1.5, 0.7)
    assert np.allclose(tr[0], r0)


def test_bloch_trajectory_long_time_fixed_point():
    tr = m.bloch_trajectory([100.0], [1.0, 0.0, -1.0], 2.0, 2.0, 1.0, 0.65)
    assert abs(tr[0,0]) < 1e-12
    assert abs(tr[0,1]) < 1e-12
    assert abs(tr[0,2] - 0.65) < 1e-12


def test_driven_zero_drive_recovers_equilibrium():
    rx, ry, rz = m.driven_steady_state(np.array([-1.0, 0.0, 1.0]), 0.0, 2.0, 1.0, 0.7)
    assert np.allclose(rx, 0)
    assert np.allclose(ry, 0)
    assert np.allclose(rz, 0.7)


def test_resonant_drive_saturates_population_difference():
    _, _, weak = m.driven_steady_state(np.array([0.0]), 0.1, 2.0, 1.0, 1.0)
    _, _, strong = m.driven_steady_state(np.array([0.0]), 10.0, 2.0, 1.0, 1.0)
    assert strong[0] < weak[0]
    assert strong[0] < 0.01


def test_amplitude_damping_kraus_completeness():
    ks = m.amplitude_damping_kraus(0.37)
    s = sum(k.conj().T @ k for k in ks)
    assert np.allclose(s, np.eye(2))


def test_amplitude_damping_excited_state_population():
    rho1 = np.array([[0.0, 0.0], [0.0, 1.0]], complex)
    out = m.apply_kraus(rho1, m.amplitude_damping_kraus(0.25))
    assert np.allclose(np.diag(out), [0.25, 0.75])


def test_density_bloch_roundtrip():
    r = np.array([0.2, -0.3, 0.7])
    rho = m.density_from_bloch(r)
    assert np.allclose(m.bloch_from_density(rho), r)


def test_physical_bloch_purity():
    r = np.array([0.2, 0.1, 0.5])
    rho = m.density_from_bloch(r)
    purity = np.trace(rho @ rho).real
    assert abs(purity - (1 + np.dot(r, r))/2) < 1e-15
