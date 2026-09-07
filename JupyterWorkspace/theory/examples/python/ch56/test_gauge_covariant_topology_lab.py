import numpy as np
import pytest

import gauge_covariant_topology_lab as lab
from spin_orbit_lattice_lab import kane_mele_bloch_hamiltonian, z2_spin_conserving


TOP = dict(lambda_so=0.06, lambda_r=0.04, delta=0.0)
TRIV = dict(lambda_so=0.06, lambda_r=0.04, delta=0.40)


def test_reciprocal_k_shape():
    assert lab.reciprocal_k(0.2, 0.3).shape == (2,)


def test_reciprocal_periodicity_b1():
    k = lab.reciprocal_k(0.21, 0.37)
    kp = lab.reciprocal_k(1.21, 0.37)
    assert np.max(np.abs(kane_mele_bloch_hamiltonian(*k, **TOP) - kane_mele_bloch_hamiltonian(*kp, **TOP))) < 2e-12


def test_occupied_frame_shape():
    assert lab.occupied_frame_fractional(0.2, 0.3, **TOP).shape == (4, 2)


def test_occupied_frame_orthonormal():
    u = lab.occupied_frame_fractional(0.2, 0.3, **TOP)
    assert np.linalg.norm(u.conj().T @ u - np.eye(2)) < 2e-12


def test_projector_hermitian():
    assert lab.projector_residuals(0.2, 0.3, **TOP)["hermiticity"] < 2e-12


def test_projector_idempotent():
    assert lab.projector_residuals(0.2, 0.3, **TOP)["idempotency"] < 2e-12


def test_projector_trace_rank_two():
    assert lab.projector_residuals(0.2, 0.3, **TOP)["trace_error"] < 2e-12


def test_projector_periodic_u():
    p = lab.occupied_projector_fractional(0.17, 0.33, **TOP)
    q = lab.occupied_projector_fractional(1.17, 0.33, **TOP)
    assert np.linalg.norm(p - q) < 3e-12


def test_projector_periodic_v():
    p = lab.occupied_projector_fractional(0.17, 0.33, **TOP)
    q = lab.occupied_projector_fractional(0.17, 1.33, **TOP)
    assert np.linalg.norm(p - q) < 3e-12


def test_projector_invariant_under_local_u2_rotation():
    f = lab.occupied_frame_fractional(0.17, 0.33, **TOP)
    g = np.array([[1, 1j], [1j, 1]], dtype=complex) / np.sqrt(2.0)
    assert np.linalg.norm(f @ f.conj().T - (f @ g) @ (f @ g).conj().T) < 2e-12


def test_unitary_part_is_unitary():
    m = np.array([[1.0, 0.2j], [0.1, 0.9]], dtype=complex)
    u = lab.unitary_part(m)
    assert np.linalg.norm(u.conj().T @ u - np.eye(2)) < 2e-12


def test_unitary_part_rejects_singular_overlap():
    with pytest.raises(RuntimeError):
        lab.unitary_part(np.array([[1.0, 0.0], [0.0, 0.0]], dtype=complex))


def test_wilson_loop_unitary():
    w = lab.wilson_loop_matrix(0.37, loop_points=48, **TOP)
    assert np.linalg.norm(w.conj().T @ w - np.eye(2)) < 2e-12


def test_wilson_eigenvalues_on_unit_circle():
    e = np.linalg.eigvals(lab.wilson_loop_matrix(0.37, loop_points=48, **TOP))
    assert np.max(np.abs(np.abs(e) - 1.0)) < 2e-12


def test_wilson_centers_are_reduced_mod_one():
    x = lab.wilson_loop_centers(0.37, loop_points=48, **TOP)
    assert np.all((x >= 0.0) & (x < 1.0))


def test_kramers_wilson_pair_at_v_zero():
    x = lab.wilson_loop_centers(0.0, loop_points=56, **TOP)
    d = min(abs(x[1] - x[0]), 1.0 - abs(x[1] - x[0]))
    assert d < 1e-10


def test_kramers_wilson_pair_at_v_half():
    x = lab.wilson_loop_centers(0.5, loop_points=56, **TOP)
    d = min(abs(x[1] - x[0]), 1.0 - abs(x[1] - x[0]))
    assert d < 1e-10


def test_topological_wilson_z2_is_one():
    assert lab.z2_wilson_loop(transverse_points=31, loop_points=56, **TOP) == 1


def test_topological_relative_winding_is_odd():
    f = lab.wilson_loop_flow(transverse_points=31, loop_points=56, **TOP)
    assert abs(f.relative_winding) % 2 == 1


def test_trivial_wilson_z2_is_zero():
    assert lab.z2_wilson_loop(transverse_points=31, loop_points=56, **TRIV) == 0


def test_trivial_relative_winding_is_zero():
    f = lab.wilson_loop_flow(transverse_points=31, loop_points=56, **TRIV)
    assert f.relative_winding == 0


def test_wilson_z2_agrees_with_spin_conserving_reference():
    z_w = lab.z2_wilson_loop(transverse_points=31, loop_points=56, lambda_so=0.06, lambda_r=0.0, delta=0.0)
    z_s = z2_spin_conserving(mesh=30, lambda_so=0.06, delta=0.0)
    assert z_w == z_s == 1


def test_wilson_z2_agrees_with_spin_conserving_trivial_reference():
    z_w = lab.z2_wilson_loop(transverse_points=31, loop_points=56, lambda_so=0.06, lambda_r=0.0, delta=0.40)
    z_s = z2_spin_conserving(mesh=30, lambda_so=0.06, delta=0.40)
    assert z_w == z_s == 0


@pytest.mark.parametrize("seed", [1, 17, 617])
def test_wilson_spectrum_gauge_invariant(seed):
    assert lab.wilson_loop_gauge_invariance_error(0.37, loop_points=40, seed=seed, **TOP) < 2e-12


@pytest.mark.parametrize("points", [40, 56, 72])
def test_wilson_center_loop_discretization_converges(points):
    ref = lab.wilson_loop_centers(0.35, loop_points=96, **TOP)
    got = lab.wilson_loop_centers(0.35, loop_points=points, **TOP)
    assert np.max(np.abs(got - ref)) < 2.5e-3


def test_projector_metric_symmetric():
    q = lab.projector_geometry(0.23, 0.31, **TOP)
    assert np.linalg.norm(q.metric - q.metric.T) < 2e-12


def test_projector_metric_positive_semidefinite():
    q = lab.projector_geometry(0.23, 0.31, **TOP)
    assert np.min(np.linalg.eigvalsh(q.metric)) > -1e-9


def test_projector_curvature_finite():
    q = lab.projector_geometry(0.23, 0.31, lambda_so=0.06, lambda_r=0.04, delta=0.10)
    assert np.isfinite(q.curvature)


def test_projector_curvature_time_reversal_odd():
    q = lab.projector_geometry(0.23, 0.31, lambda_so=0.06, lambda_r=0.04, delta=0.10)
    r = lab.projector_geometry(0.77, 0.69, lambda_so=0.06, lambda_r=0.04, delta=0.10)
    assert abs(q.curvature + r.curvature) < 2e-8


def test_projector_metric_time_reversal_even():
    q = lab.projector_geometry(0.23, 0.31, lambda_so=0.06, lambda_r=0.04, delta=0.10)
    r = lab.projector_geometry(0.77, 0.69, lambda_so=0.06, lambda_r=0.04, delta=0.10)
    assert np.max(np.abs(q.metric - r.metric)) < 2e-8


def test_subspace_chordal_distance_zero_on_same_point():
    assert lab.subspace_chordal_distance(0.2, 0.3, 0.2, 0.3, **TOP) < 2e-12


def test_subspace_chordal_distance_positive_between_points():
    assert lab.subspace_chordal_distance(0.2, 0.3, 0.27, 0.36, **TOP) > 1e-3


def test_principal_overlap_same_subspace_is_one():
    s = lab.principal_overlap_singular_values(0.2, 0.3, 0.2, 0.3, **TOP)
    assert np.max(np.abs(s - 1.0)) < 2e-12


def test_principal_overlap_values_are_bounded():
    s = lab.principal_overlap_singular_values(0.2, 0.3, 0.27, 0.36, **TOP)
    assert np.all((s >= -1e-12) & (s <= 1.0 + 1e-12))



def test_topological_bulk_edge_has_midgap_crossing():
    s = lab.bulk_edge_correspondence_summary(transverse_points=25, loop_points=48, width=12, mesh=24, **TOP)
    assert s.edge_crossing_present


def test_topological_ribbon_crossing_is_near_zero_and_edge_localized():
    s = lab.bulk_edge_correspondence_summary(transverse_points=25, loop_points=48, width=12, mesh=24, **TOP)
    assert s.ribbon_min_abs_energy < 1e-3 and s.ribbon_min_edge_weight > 0.99


def test_trivial_bulk_edge_z2():
    s = lab.bulk_edge_correspondence_summary(transverse_points=25, loop_points=48, width=12, mesh=24, **TRIV)
    assert s.z2 == 0


def test_trivial_bulk_edge_has_no_midgap_crossing():
    s = lab.bulk_edge_correspondence_summary(transverse_points=25, loop_points=48, width=12, mesh=24, **TRIV)
    assert not s.edge_crossing_present


def test_trivial_ribbon_nearest_edge_state_is_outside_bulk_midgap():
    s = lab.bulk_edge_correspondence_summary(transverse_points=25, loop_points=48, width=12, mesh=24, **TRIV)
    assert s.ribbon_min_abs_energy > s.bulk_gap


def test_reference_summary_is_gauge_covariant_and_consistent():
    r = lab.reference_summary()
    assert r["topological_z2"] == 1
    assert r["trivial_z2"] == 0
    assert r["gauge_invariance_error"] < 3e-12
