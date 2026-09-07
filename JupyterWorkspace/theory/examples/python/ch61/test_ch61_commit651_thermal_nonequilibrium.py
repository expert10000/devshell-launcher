import numpy as np
from thermal_nonequilibrium import *
def test_thermal_probs_normalized(): assert np.isclose(thermal_probabilities([0,1,2],2).sum(),1)
def test_low_temp_ground_dominates(): assert thermal_probabilities([0,1,2],20)[0]>.999
def test_energy_shift_invariance():
 p=thermal_probabilities([0,1,2],1.3); q=thermal_probabilities([5,6,7],1.3); assert np.allclose(p,q)
def test_heat_capacity_nonnegative(): assert heat_capacity([0,1,2],1.0)>=0
def test_survival_starts_one(): assert np.isclose(survival_probability([0,1],[.4,.6],[0])[0],1)
def test_entanglement_saturates(): assert entanglement_growth([100])[0]==4
def test_light_cone_bounded(): 
 x=light_cone(np.array([0,5]),np.array([0,0])); assert np.all((x>=0)&(x<=1))
def test_spectral_positive(): assert np.all(lorentzian_spectrum(np.linspace(-2,2,30),[0],[1])>=0)
def test_spacing_ratio_range():
 r=spacing_ratios([0,.3,1.1,2.0,3.5]); assert np.all((r>=0)&(r<=1))
def test_correlation_length_decreases():
 x=thermal_correlation_length(np.array([.1,1,3])); assert np.all(np.diff(x)<0)
