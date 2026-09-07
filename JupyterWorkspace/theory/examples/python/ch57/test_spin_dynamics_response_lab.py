import numpy as np
import spin_dynamics_response_lab as lab

# 1
def test_pauli_x_hermitian(): assert np.allclose(lab.SX, lab.SX.conj().T)
# 2
def test_pauli_y_hermitian(): assert np.allclose(lab.SY, lab.SY.conj().T)
# 3
def test_pauli_z_hermitian(): assert np.allclose(lab.SZ, lab.SZ.conj().T)
# 4
def test_pauli_x_square(): assert np.allclose(lab.SX @ lab.SX, lab.I2)
# 5
def test_pauli_y_square(): assert np.allclose(lab.SY @ lab.SY, lab.I2)
# 6
def test_pauli_z_square(): assert np.allclose(lab.SZ @ lab.SZ, lab.I2)
# 7
def test_plus_x_bloch(): assert np.allclose(lab.bloch_vector(lab.PLUS_X), [1,0,0], atol=1e-13)
# 8
def test_up_bloch(): assert np.allclose(lab.bloch_vector(lab.UP), [0,0,1], atol=1e-13)
# 9
def test_down_bloch(): assert np.allclose(lab.bloch_vector(lab.DOWN), [0,0,-1], atol=1e-13)
# 10
def test_static_hamiltonian_hermitian():
    H=lab.static_spin_hamiltonian([1.2,-0.3,0.8]); assert np.allclose(H,H.conj().T)
# 11
def test_zero_vector_unitary_identity(): assert np.allclose(lab.unitary_from_omega_vector([0,0,0],3),lab.I2)
# 12
def test_static_unitary_is_unitary():
    U=lab.unitary_from_omega_vector([1,.2,-.7],2.3); assert np.allclose(U.conj().T@U,lab.I2,atol=1e-13)
# 13
def test_static_evolution_preserves_norm():
    p=lab.evolve_static(lab.PLUS_X,[0,0,2],1.3); assert np.isclose(np.vdot(p,p),1,atol=1e-13)
# 14
def test_z_precession_pi_maps_plus_x_to_minus_x():
    p=lab.evolve_static(lab.PLUS_X,[0,0,1],np.pi); assert lab.state_fidelity(p,lab.MINUS_X)>1-1e-12
# 15
def test_bloch_length_preserved():
    p=lab.evolve_static(lab.PLUS_X,[.4,.7,1.2],4.1); assert abs(np.linalg.norm(lab.bloch_vector(p))-1)<1e-12
# 16
def test_rwa_hamiltonian_hermitian():
    H=lab.rwa_hamiltonian(.3,1.2); assert np.allclose(H,H.conj().T)
# 17
def test_generalized_rabi_on_resonance(): assert lab.generalized_rabi_frequency(0,2.5)==2.5
# 18
def test_generalized_rabi_pythagorean(): assert np.isclose(lab.generalized_rabi_frequency(3,4),5)
# 19
def test_rabi_zero_drive_zero_probability(): assert lab.rabi_excitation_probability(1,0,7)==0
# 20
def test_rabi_pi_pulse_probability_one():
    o=2.; assert abs(lab.rabi_excitation_probability(0,o,lab.pi_pulse_time(o))-1)<1e-12
# 21
def test_rabi_half_pi_probability_half():
    o=2.; assert abs(lab.rabi_excitation_probability(0,o,lab.half_pi_pulse_time(o))-.5)<1e-12
# 22
def test_detuned_max_probability_reference(): assert abs(lab.max_rabi_excitation(1,2)-.8)<1e-12
# 23
def test_large_detuning_reduces_contrast(): assert lab.max_rabi_excitation(10,1)<.02
# 24
def test_pi_pulse_time_reference(): assert np.isclose(lab.pi_pulse_time(2),np.pi/2)
# 25
def test_half_pi_pulse_time_reference(): assert np.isclose(lab.half_pi_pulse_time(2),np.pi/4)
# 26
def test_pi_x_maps_down_to_up():
    p=lab.pulse_unitary_x(np.pi)@lab.DOWN; assert lab.state_fidelity(p,lab.UP)>1-1e-12
# 27
def test_half_pi_x_creates_equal_z_populations():
    p=lab.pulse_unitary_x(np.pi/2)@lab.DOWN; assert abs(abs(p[0])**2-.5)<1e-12 and abs(abs(p[1])**2-.5)<1e-12
# 28
def test_free_detuning_unitary():
    U=lab.free_detuning_unitary(1.7,2.1); assert np.allclose(U.conj().T@U,lab.I2,atol=1e-13)
# 29
def test_echo_refocuses_plus_x(): assert lab.echo_refocusing_fidelity(1.7,2.3)>1-1e-12
# 30
def test_echo_refocuses_different_detuning(): assert lab.echo_refocusing_fidelity(-3.2,.7)>1-1e-12
# 31
def test_kubo_response_causal_negative_time(): assert lab.kubo_chi_xx_time(-1,2)==0
# 32
def test_kubo_response_zero_time(): assert abs(lab.kubo_chi_xx_time(0,2))<1e-15
# 33
def test_kubo_response_quarter_period(): assert abs(lab.kubo_chi_xx_time(np.pi/4,2)-.5)<1e-12
# 34
def test_susceptibility_peak_reference(): assert abs(lab.absorptive_susceptibility(3,3,.2)-1.25)<1e-12
# 35
def test_susceptibility_peak_helper(): assert abs(lab.susceptibility_peak_value(.2)-1.25)<1e-12
# 36
def test_susceptibility_positive(): assert lab.absorptive_susceptibility(10,3,.2)>0
# 37
def test_susceptibility_symmetric_about_resonance():
    a=lab.absorptive_susceptibility(2.5,3,.2); b=lab.absorptive_susceptibility(3.5,3,.2); assert abs(a-b)<1e-12
# 38
def test_narrower_line_has_higher_peak(): assert lab.susceptibility_peak_value(.1)>lab.susceptibility_peak_value(.2)
# 39
def test_singlet_normalized():
    s=lab.singlet_state(); assert np.isclose(np.vdot(s,s),1)
# 40
def test_triplet_zero_normalized():
    t=lab.triplet_zero_state(); assert np.isclose(np.vdot(t,t),1)
# 41
def test_exchange_hamiltonian_hermitian():
    H=lab.exchange_hamiltonian(.8); assert np.allclose(H,H.conj().T)
# 42
def test_exchange_spectrum_reference(): assert np.allclose(np.linalg.eigvalsh(lab.exchange_hamiltonian(.8)),[-.6,.2,.2,.2])
# 43
def test_exchange_unitary_unitary():
    U=lab.exchange_unitary(.8,1.3); assert np.allclose(U.conj().T@U,np.eye(4),atol=1e-13)
# 44
def test_swap_operator_unitary(): assert np.allclose(lab.swap_operator().conj().T@lab.swap_operator(),np.eye(4))
# 45
def test_swap_time_reference(): assert np.isclose(lab.swap_time(.8),np.pi/.8)
# 46
def test_sqrt_swap_time_half(): assert np.isclose(lab.sqrt_swap_time(.8),.5*lab.swap_time(.8))
# 47
def test_exchange_swap_global_phase_equivalence():
    U=lab.exchange_unitary(.8,lab.swap_time(.8)); assert lab.global_phase_aligned_error(U,lab.swap_operator())<1e-12
# 48
def test_sqrt_swap_squared_is_swap():
    U=lab.exchange_unitary(.8,lab.sqrt_swap_time(.8)); assert lab.global_phase_aligned_error(U@U,lab.swap_operator())<1e-12
# 49
def test_gradient_operator_hermitian():
    G=lab.gradient_operator(); assert np.allclose(G,G.conj().T)
# 50
def test_st_gradient_matrix_element_one(): assert abs(lab.singlet_triplet_gradient_matrix_element()-1)<1e-12
# 51
def test_st_subspace_diagonal_exchange_split():
    H=lab.st_subspace_hamiltonian(1,0); assert np.allclose(H,np.diag([-.75,.25]),atol=1e-12)
# 52
def test_st_subspace_gradient_offdiagonal():
    H=lab.st_subspace_hamiltonian(1,.3); assert abs(H[0,1]-.3)<1e-12 and abs(H[1,0]-.3)<1e-12
# 53
def test_landau_zener_hamiltonian_hermitian():
    H=lab.landau_zener_hamiltonian(.7,2,1); assert np.allclose(H,H.conj().T)
# 54
def test_landau_zener_formula_reference(): assert abs(lab.landau_zener_diabatic_probability(2,1)-np.exp(-np.pi/4))<1e-12
# 55
def test_landau_zener_slower_is_more_adiabatic(): assert lab.landau_zener_diabatic_probability(.5,1)<lab.landau_zener_diabatic_probability(2,1)
# 56
def test_landau_zener_larger_gap_more_adiabatic(): assert lab.landau_zener_diabatic_probability(2,2)<lab.landau_zener_diabatic_probability(2,1)
# 57
def test_landau_zener_propagation_norm():
    r=lab.propagate_landau_zener(2,1,tmax=8,steps=2000); assert abs(r['norm']-1)<1e-12
# 58
def test_landau_zener_numerical_near_formula():
    r=lab.propagate_landau_zener(2,1,tmax=12,steps=4000); p=lab.landau_zener_diabatic_probability(2,1); assert abs(r['diabatic_survival']-p)<.04
# 59
def test_reference_summary_core_values():
    r=lab.reference_summary(); assert abs(r['rabi_pi_probability']-1)<1e-12 and abs(r['detuned_max_probability']-.8)<1e-12 and r['echo_fidelity']>1-1e-12
# 60
def test_reference_summary_control_and_lz_values():
    r=lab.reference_summary(); assert r['swap_error']<1e-12 and r['sqrt_swap_squared_error']<1e-12 and abs(r['lz_formula_v2_gap1']-np.exp(-np.pi/4))<1e-12 and abs(r['lz_numerical_v2_gap1']-r['lz_formula_v2_gap1'])<.04
