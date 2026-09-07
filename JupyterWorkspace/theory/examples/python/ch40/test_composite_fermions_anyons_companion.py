import math
import numpy as np
import pytest
from composite_fermions_anyons_companion import *

def test_01_jain_13(): assert np.isclose(jain_fraction(1,1,1),1/3)
def test_02_jain_25(): assert np.isclose(jain_fraction(2,1,1),2/5)
def test_03_reverse_23(): assert np.isclose(jain_fraction(2,1,-1),2/3)
def test_04_effective_field_13(): assert np.isclose(effective_field_ratio(1/3),1/3)
def test_05_half_filling_zero_field(): assert np.isclose(effective_field_ratio(.5),0)
def test_06_effective_filling_25(): assert np.isclose(effective_filling(2/5),2)
def test_07_half_effective_filling_infinite(): assert math.isinf(effective_filling(.5))
def test_08_finite_flux(): assert finite_effective_flux(8,21,1)==7
def test_09_jain_shift(): assert positive_jain_shift(2,1)==4
def test_10_kf_value(): assert np.isclose(cf_fermi_wavevector(1/(4*math.pi)),1)
def test_11_kf_sqrt_scaling(): assert np.isclose(cf_fermi_wavevector(2)/cf_fermi_wavevector(1),math.sqrt(2))
def test_12_parton_111(): assert np.isclose(parton_filling([1,1,1]),1/3)
def test_13_parton_211(): assert np.isclose(parton_filling([2,1,1]),2/5)
def test_14_parton_reverse(): assert np.isclose(parton_filling([-2,1,1]),2/3)
def test_15_parton_charges_sum(): assert np.isclose(np.sum(parton_charges([2,1,1])),-1)
def test_16_laughlin_k_filling(): assert np.isclose(kmatrix_filling([[3]],[1]),1/3)
def test_17_jain_k_25(): assert np.isclose(kmatrix_filling(jain_kmatrix(2,1),[1,1]),2/5)
def test_18_jain_det_5(): assert torus_degeneracy(jain_kmatrix(2,1))==5
def test_19_jain_minimal_charge(): assert np.isclose(anyon_charge(jain_kmatrix(2,1),[1,1],[1,0]),1/5)
def test_20_laughlin_exchange(): assert np.isclose(anyon_exchange_angle([[3]],[1]),math.pi/3)
def test_21_laughlin_mutual(): assert np.isclose(anyon_mutual_phase([[3]],[1],[1]),2*math.pi/3)
def test_22_local_shift(): assert np.array_equal(local_particle_shift([1],[[3]],[1]),[4])
def test_23_laughlin_torus_5(): assert torus_degeneracy([[5]])==5
def test_24_ising_four_sigma(): assert ising_fusion_space_dimension(4)==2
def test_25_ising_six_sigma(): assert ising_fusion_space_dimension(6)==4
def test_26_mr_charge(): assert np.isclose(moore_read_fundamental_charge(),.25)
def test_27_rr_moore_read(): assert np.isclose(read_rezayi_filling(2,1),.5)
def test_28_rr_k3(): assert np.isclose(read_rezayi_filling(3,1),3/5)
def test_29_braids_noncommute(): assert braid_commutator_norm()>1e-8
def test_30_braids_unitary():
    a,b=ising_braid_generators(); I=np.eye(2); assert np.allclose(a.conj().T@a,I) and np.allclose(b.conj().T@b,I)
