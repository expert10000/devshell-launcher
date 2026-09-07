"""Chapter 48 quantum geometry and modern Hall physics computational companion."""
from __future__ import annotations
import math
import numpy as np


def two_level_lower_geometry(kx: float, ky: float, mass: float):
    """Metric and Berry curvature for the lower band of H=(kx,ky,mass).sigma."""
    r2 = float(kx*kx + ky*ky + mass*mass)
    if r2 <= 0:
        raise ValueError("the two-level gap must be nonzero")
    gxx = (ky*ky + mass*mass) / (4.0*r2*r2)
    gyy = (kx*kx + mass*mass) / (4.0*r2*r2)
    gxy = -(kx*ky) / (4.0*r2*r2)
    curvature = -mass / (2.0*r2**1.5)
    return float(gxx), float(gyy), float(gxy), float(curvature)


def metric_determinant(gxx: float, gyy: float, gxy: float) -> float:
    return float(gxx*gyy - gxy*gxy)


def determinant_bound_margin(gxx: float, gyy: float, gxy: float, curvature: float) -> float:
    return float(metric_determinant(gxx, gyy, gxy) - curvature*curvature/4.0)


def trace_bound_margin(gxx: float, gyy: float, curvature: float) -> float:
    return float(gxx + gyy - abs(curvature))


def integrated_metric_lower_bound(chern: int | float) -> float:
    return float(2.0*math.pi*abs(chern))


def laguerre(n: int, x):
    if n < 0:
        raise ValueError("n must be nonnegative")
    x = np.asarray(x, dtype=float)
    if n == 0:
        return np.ones_like(x)
    if n == 1:
        return 1.0 - x
    lm2 = np.ones_like(x)
    lm1 = 1.0 - x
    for k in range(2, n+1):
        lk = ((2*k-1-x)*lm1 - (k-1)*lm2)/k
        lm2, lm1 = lm1, lk
    return lm1


def landau_form_factor(n: int, q, ell_b: float = 1.0):
    if ell_b <= 0:
        raise ValueError("ell_b must be positive")
    q = np.asarray(q, dtype=float)
    x = 0.5*(q*ell_b)**2
    return np.exp(-x/2.0)*laguerre(n, x)


def gmp_coefficient(q, qp, ell_b: float = 1.0) -> float:
    q = np.asarray(q, dtype=float); qp = np.asarray(qp, dtype=float)
    if q.shape != (2,) or qp.shape != (2,) or ell_b <= 0:
        raise ValueError("q and qp must be planar vectors and ell_b positive")
    cross = q[0]*qp[1] - q[1]*qp[0]
    return float(2.0*math.sin(0.5*ell_b*ell_b*cross))


def gmp_linear_coefficient(q, qp, ell_b: float = 1.0) -> float:
    q = np.asarray(q, dtype=float); qp = np.asarray(qp, dtype=float)
    cross = q[0]*qp[1] - q[1]*qp[0]
    return float(ell_b*ell_b*cross)


def normalized_rms_fluctuation(values) -> float:
    a = np.asarray(values, dtype=float)
    if a.size == 0:
        raise ValueError("values must be nonempty")
    mean = float(np.mean(a))
    if abs(mean) < 1e-15:
        raise ValueError("mean is too close to zero for normalized fluctuation")
    return float(np.sqrt(np.mean((a-mean)**2))/abs(mean))


def geometry_quality(curvature, metric_trace):
    return normalized_rms_fluctuation(curvature), normalized_rms_fluctuation(metric_trace)


def fci_projection_hierarchy(width: float, interaction: float, band_gap: float, tolerance: float = 0.2):
    if width < 0 or interaction <= 0 or band_gap <= 0 or tolerance <= 0:
        raise ValueError("invalid positive energy scales")
    r_flat = width/interaction
    r_mix = interaction/band_gap
    return float(r_flat), float(r_mix), bool(r_flat < tolerance and r_mix < tolerance)


def fractional_hall_response(total_many_body_chern: float, ground_state_degeneracy: int) -> float:
    if ground_state_degeneracy <= 0:
        raise ValueError("degeneracy must be positive")
    return float(total_many_body_chern/ground_state_degeneracy)


def mean_orbital_spin(shift: float) -> float:
    return float(shift/2.0)


def hall_viscosity(density: float, shift: float, hbar: float = 1.0) -> float:
    if density < 0 or hbar <= 0:
        raise ValueError("density must be nonnegative and hbar positive")
    return float(hbar*density*shift/4.0)


def sphere_flux(particles: float, filling: float, shift: float) -> float:
    if filling == 0:
        raise ValueError("filling cannot vanish")
    return float(particles/filling - shift)


def wen_zee_particle_number(filling: float, flux: float, shift: float, euler_characteristic: float = 2.0) -> float:
    return float(filling*flux + filling*shift*euler_characteristic/2.0)


def guiding_center_spin(shift: float) -> float:
    return float((1.0-shift)/2.0)


def structure_factor_s4_bound(shift: float) -> float:
    return float(abs(guiding_center_spin(shift))/4.0)


def projected_structure_factor_leading(q, s4: float, ell_b: float = 1.0):
    if s4 < 0 or ell_b <= 0:
        raise ValueError("s4 must be nonnegative and ell_b positive")
    q = np.asarray(q, dtype=float)
    return s4*(q*ell_b)**4
