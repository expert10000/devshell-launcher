"""Numerical companion for Chapter 43: Chern numbers and global invariants.

The functions deliberately separate gauge-dependent representatives from gauge-invariant
objects.  They provide compact diagnostics rather than a model-specific Chapter 44 solver.
"""
from __future__ import annotations
import numpy as np

TWOPI = 2.0 * np.pi


def wrap_phase(phi):
    """Return phases on the principal interval (-pi, pi]."""
    arr = np.asarray(phi, dtype=float)
    out = (arr + np.pi) % TWOPI - np.pi
    return np.where(np.isclose(out, -np.pi), np.pi, out)


def sphere_lower_curvature(theta):
    """Berry curvature F_{theta phi} for the lower state of d-hat=(sinθcosφ,sinθsinφ,cosθ)."""
    return 0.5 * np.sin(np.asarray(theta, dtype=float))


def sphere_chern_numeric(n_theta: int = 2001) -> float:
    theta = np.linspace(0.0, np.pi, int(n_theta))
    f = sphere_lower_curvature(theta)
    return float(np.trapezoid(f, theta))  # phi integral / 2pi cancels


def transition_phase(phi, winding: int = 1):
    return winding * np.asarray(phi, dtype=float)


def winding_from_unwrapped_phase(phi, phase) -> float:
    phi = np.asarray(phi, dtype=float)
    phase = np.unwrap(np.asarray(phase, dtype=float))
    if phi.size < 2:
        raise ValueError("at least two points are required")
    return float((phase[-1] - phase[0]) / TWOPI)


def degree_texture(theta, phi, degree: int = 1):
    theta = np.asarray(theta, dtype=float)
    phi = np.asarray(phi, dtype=float)
    return np.stack((np.sin(theta) * np.cos(degree * phi),
                     np.sin(theta) * np.sin(degree * phi),
                     np.cos(theta)), axis=-1)


def degree_density(theta, degree: int = 1):
    """Normalized degree density after integrating over azimuth: (n/2) sin(theta)."""
    return 0.5 * degree * np.sin(np.asarray(theta, dtype=float))


def degree_numeric(degree: int = 1, n_theta: int = 2001) -> float:
    theta = np.linspace(0.0, np.pi, int(n_theta))
    return float(np.trapezoid(degree_density(theta, degree), theta))


def regularized_dirac_curvature(kx, ky, mass: float, beta: float = 1.0):
    """Lower-band curvature of d=(kx,ky,m-beta*k^2)."""
    kx = np.asarray(kx, dtype=float); ky = np.asarray(ky, dtype=float)
    r2 = kx*kx + ky*ky
    dz = mass - beta*r2
    denom = (r2 + dz*dz)**1.5
    return (mass + beta*r2) / (2.0 * denom)


def regularized_dirac_chern_exact(mass: float, beta: float = 1.0) -> float:
    if mass == 0 or beta == 0:
        raise ValueError("the compactified texture is singular or unregularized")
    return 0.5 * (np.sign(mass) + np.sign(beta))


def regularized_dirac_chern_numeric(mass: float, beta: float = 1.0, kmax: float = 18.0, n: int = 30001) -> float:
    r = np.linspace(0.0, float(kmax), int(n))
    om = regularized_dirac_curvature(r, 0.0, mass, beta)
    return float(np.trapezoid(r * om, r))


def two_level_gap(kx, ky, mass: float, beta: float = 1.0):
    r2 = np.asarray(kx, dtype=float)**2 + np.asarray(ky, dtype=float)**2
    dz = mass - beta*r2
    return 2.0*np.sqrt(r2 + dz*dz)


def projector_from_state(state):
    u = np.asarray(state, dtype=complex)
    u = u / np.linalg.norm(u)
    return np.outer(u, u.conj())


def occupied_projector(frame):
    """Projector from an orthonormal column frame."""
    q, _ = np.linalg.qr(np.asarray(frame, dtype=complex))
    return q @ q.conj().T


def rotate_frame(frame, unitary):
    return np.asarray(frame, dtype=complex) @ np.asarray(unitary, dtype=complex)


def random_unitary(n: int, seed: int = 0):
    rng = np.random.default_rng(seed)
    z = rng.normal(size=(n,n)) + 1j*rng.normal(size=(n,n))
    q, r = np.linalg.qr(z)
    phases = np.diag(r)
    phases = np.where(np.abs(phases) > 0, phases/np.abs(phases), 1.0)
    return q @ np.diag(phases.conj())


def normalized_link(overlap: complex) -> complex:
    if abs(overlap) < 1e-14:
        raise ValueError("singular overlap link")
    return overlap / abs(overlap)


def plaquette_phase(u00, u10, u11, u01) -> float:
    """Gauge-invariant U(1) phase around an oriented plaquette."""
    l1 = normalized_link(np.vdot(u00,u10))
    l2 = normalized_link(np.vdot(u10,u11))
    l3 = normalized_link(np.vdot(u11,u01))
    l4 = normalized_link(np.vdot(u01,u00))
    return float(np.angle(l1*l2*l3*l4))


def gauge_rephase(state, phase):
    return np.exp(1j*phase) * np.asarray(state, dtype=complex)


def hall_sigma_yx(C: float) -> float:
    """Hall conductivity in units of e^2/h using the Chapter 43 yx convention."""
    return float(C)


def hall_sigma_xy(C: float) -> float:
    return -float(C)


def pumped_particle_number(C: float) -> float:
    return float(C)


def cumulative_pump_from_density(t, density):
    t=np.asarray(t,dtype=float); density=np.asarray(density,dtype=float)
    if t.shape != density.shape:
        raise ValueError("t and density must have the same shape")
    dt=np.diff(t)
    return np.concatenate([[0.0], np.cumsum(0.5*(density[1:]+density[:-1])*dt)])
