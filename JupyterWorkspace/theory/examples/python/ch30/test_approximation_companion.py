import numpy as np
import pytest
from approximation_companion import *

def test_first_order_diagonal(): assert nondegenerate_energy_corrections([0,2],[[3,0],[0,1]],0)[0]==pytest.approx(3)
def test_second_order_sign(): assert nondegenerate_energy_corrections([0,2],[[0,1],[1,0]],0)[1]==pytest.approx(-.5)
def test_degeneracy_rejected():
    with pytest.raises(ValueError): nondegenerate_energy_corrections([0,0],[[0,1],[1,0]],0)
def test_exact_eigenvalues_shape(): assert exact_eigenvalues([0,1],[[0,.2],[.2,0]]).shape==(2,)
def test_exact_zero_coupling(): assert np.allclose(exact_eigenvalues([0,2],[[1,3],[3,4]],0),[0,2])
def test_degenerate_split(): assert np.allclose(degenerate_first_order([[1,2],[2,1]]),[-1,3])
def test_rayleigh_eigenvector(): assert rayleigh_quotient(np.diag([1,3]),[1,0])==pytest.approx(1)
def test_rayleigh_normalization_independent(): assert rayleigh_quotient(np.diag([1,3]),[2,0])==pytest.approx(1)
def test_residual_eigenvector(): assert residual_norm(np.diag([1,3]),[0,1])==pytest.approx(0)
def test_residual_mixed_positive(): assert residual_norm(np.diag([1,3]),[1,1])>0
def test_quartic_positive(): assert gaussian_quartic_energy(1,.1)>0
def test_quartic_vectorized(): assert gaussian_quartic_energy(np.array([.5,1])).shape==(2,)
def test_quartic_invalid():
    with pytest.raises(ValueError): gaussian_quartic_energy(0)
def test_pulse_resonance(): assert rectangular_pulse_probability(0,.1,2)==pytest.approx(.04)
def test_pulse_symmetry(): assert rectangular_pulse_probability(2,.1,3)==pytest.approx(rectangular_pulse_probability(-2,.1,3))
def test_pulse_zero_time(): assert rectangular_pulse_probability(1,.2,0)==0
def test_rabi_on_resonance_pi(): assert rabi_probability(0,2,np.pi/2)==pytest.approx(1)
def test_rabi_detuned_bounded(): assert np.max(rabi_probability(2,1,np.linspace(0,10,100)))<=.2+1e-8
def test_rabi_zero_coupling(): assert np.allclose(rabi_probability(2,0,np.arange(3)),0)
def test_golden_rule_zero(): assert golden_rule_rate(0,3)==0
def test_golden_rule_scaling(): assert golden_rule_rate(2,3)==pytest.approx(4*golden_rule_rate(1,3))
def test_golden_rule_invalid():
    with pytest.raises(ValueError): golden_rule_rate(1,-1)
def test_adiabatic_gap_scaling(): assert adiabatic_parameter(2,1)==pytest.approx(.25)
def test_landau_zener_bounds(): assert 0<landau_zener_diabatic_probability(.5,1)<1
def test_landau_zener_slow_smaller(): assert landau_zener_diabatic_probability(.5,.2)<landau_zener_diabatic_probability(.5,2)
def test_sudden_probabilities_sum(): assert np.sum(sudden_probabilities([1,0],np.eye(2)))==pytest.approx(1)
def test_sudden_rotated_basis():
    b=np.array([[1,1],[1,-1]])/np.sqrt(2); assert np.allclose(sudden_probabilities([1,0],b),[.5,.5])
def test_wkb_width_scaling(): assert wkb_transmission(2,1,2)<wkb_transmission(2,1,1)
def test_wkb_zero_width(): assert wkb_transmission(2,1,0)==pytest.approx(1)
def test_bohr_sommerfeld(): assert bohr_sommerfeld_harmonic(3,2)==pytest.approx(7)
