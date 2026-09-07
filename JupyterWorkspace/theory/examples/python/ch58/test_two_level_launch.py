import importlib.util
from pathlib import Path
import numpy as np

MODULE = Path(__file__).with_name("two_level_launch.py")
spec = importlib.util.spec_from_file_location("two_level_launch", MODULE)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def test_avoided_levels_symmetric():
    em, ep = m.avoided_energies(np.array([-2.0,0.0,2.0]), 0.7)
    assert np.allclose(em, -ep)


def test_minimum_gap():
    assert abs(m.avoided_minimum_gap(1.3) - 2.6) < 1e-15


def test_avoided_crossing_at_zero():
    em, ep = m.avoided_energies(np.array([0.0]), 0.8)
    assert abs((ep-em)[0] - 1.6) < 1e-15


def test_rabi_probability_starts_zero():
    assert m.rabi_probability([0.0], 1.0, 0.0)[0] == 0.0


def test_resonant_rabi_reaches_one():
    t = np.pi
    assert abs(m.rabi_probability([t], 1.0, 0.0)[0] - 1.0) < 1e-15


def test_detuning_reduces_maximum_transfer():
    t = np.linspace(0, 30, 5000)
    assert m.rabi_probability(t, 1.0, 1.0).max() < 0.51


def test_landau_zener_probability_bounds():
    p = m.landau_zener_diabatic_probability(0.5, 1.0)
    assert 0.0 < p < 1.0


def test_landau_zener_slow_sweep_more_adiabatic():
    pslow = m.landau_zener_diabatic_probability(0.5, 0.2)
    pfast = m.landau_zener_diabatic_probability(0.5, 3.0)
    assert pslow < pfast


def test_pauli_decomposition_identity_shift():
    H = np.array([[3.0, 0.0],[0.0, 3.0]], complex)
    h0, v = m.pauli_decomposition(H)
    assert abs(h0-3.0) < 1e-15
    assert np.allclose(v, 0)


def test_pauli_decomposition_sigma_z():
    H = np.array([[2.0,0.0],[0.0,-2.0]], complex)
    h0, v = m.pauli_decomposition(H)
    assert abs(h0) < 1e-15
    assert np.allclose(v, [0,0,2])
