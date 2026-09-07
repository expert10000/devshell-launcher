"""Deterministic bounded-electrostatics companion for Chapter 14.

All routines use SI-independent normalized units unless explicit permittivities
are supplied.  They are intentionally compact enough to audit line by line.
"""
from __future__ import annotations
import numpy as np


def nodal_capacitance(pair_caps: np.ndarray, ground_caps: np.ndarray) -> np.ndarray:
    """Return the symmetric nodal capacitance matrix of a capacitor network."""
    p = np.asarray(pair_caps, dtype=float)
    g = np.asarray(ground_caps, dtype=float)
    if p.ndim != 2 or p.shape[0] != p.shape[1] or p.shape[0] != g.size:
        raise ValueError("incompatible capacitance arrays")
    if not np.allclose(p, p.T) or np.any(p < 0) or np.any(g < 0):
        raise ValueError("pair capacitances must be symmetric and nonnegative")
    c = -p.copy()
    np.fill_diagonal(c, g + np.sum(p, axis=1) - np.diag(p))
    return c


def solve_floating(cmat: np.ndarray, charges: np.ndarray,
                   fixed_indices: np.ndarray, fixed_voltages: np.ndarray) -> np.ndarray:
    """Solve Q=C V with selected voltages prescribed and remaining charges known."""
    c = np.asarray(cmat, float)
    q = np.asarray(charges, float)
    fixed = np.asarray(fixed_indices, int)
    vf = np.asarray(fixed_voltages, float)
    n = c.shape[0]
    if c.shape != (n, n) or q.shape != (n,) or fixed.shape != vf.shape:
        raise ValueError("incompatible floating-node system")
    free = np.array([i for i in range(n) if i not in set(fixed.tolist())], dtype=int)
    v = np.zeros(n)
    v[fixed] = vf
    if free.size:
        rhs = q[free] - c[np.ix_(free, fixed)] @ vf
        v[free] = np.linalg.solve(c[np.ix_(free, free)], rhs)
    return v


def coax_two_layer_capacitance(a, b, c, eps1=1.0, eps2=1.0):
    return 2 * np.pi / (np.log(b / a) / eps1 + np.log(c / b) / eps2)


def spherical_two_layer_capacitance(a, b, c, eps1=1.0, eps2=1.0):
    inv = ((1 / a - 1 / b) / eps1 + (1 / b - 1 / c) / eps2) / (4 * np.pi)
    return 1 / inv


def layered_parallel_plate_capacitance(area, thicknesses, epsilons):
    t = np.asarray(thicknesses, float)
    e = np.asarray(epsilons, float)
    return area / np.sum(t / e)


def layered_potential(z, thicknesses, epsilons, voltage=1.0):
    """Piecewise-linear potential for dielectric layers normal to the plates."""
    t = np.asarray(thicknesses, float)
    e = np.asarray(epsilons, float)
    z = np.asarray(z, float)
    dflux = voltage / np.sum(t / e)
    bounds = np.r_[0.0, np.cumsum(t)]
    out = np.zeros_like(z)
    for k, zk in np.ndenumerate(z):
        drop = 0.0
        for i in range(t.size):
            length = np.clip(zk - bounds[i], 0.0, t[i])
            drop += dflux * length / e[i]
        out[k] = voltage - drop
    return out


def image_plane_potential(x, z, q=1.0, height=1.0):
    x = np.asarray(x, float); z = np.asarray(z, float)
    r1 = np.sqrt(x*x + (z-height)**2)
    r2 = np.sqrt(x*x + (z+height)**2)
    return q / r1 - q / r2


def image_sphere_parameters(q, a, d):
    if d <= a:
        raise ValueError("real charge must lie outside the sphere")
    return -q * a / d, a*a / d


def image_sphere_potential(r, theta, q=1.0, a=1.0, d=2.0):
    qp, rp = image_sphere_parameters(q, a, d)
    r = np.asarray(r, float); theta = np.asarray(theta, float)
    r_real = np.sqrt(r*r + d*d - 2*r*d*np.cos(theta))
    r_img = np.sqrt(r*r + rp*rp - 2*r*rp*np.cos(theta))
    return q/r_real + qp/r_img


def rectangle_laplace(x, y, a=1.0, b=1.0, coefficients=None):
    """Laplace solution with grounded side/bottom walls and sine top data."""
    x = np.asarray(x, float); y = np.asarray(y, float)
    coeff = {1: 1.0} if coefficients is None else coefficients
    out = np.zeros(np.broadcast(x, y).shape, dtype=float)
    for n, an in coeff.items():
        k = n*np.pi/a
        out += an*np.sin(k*x)*np.sinh(k*y)/np.sinh(k*b)
    return out


def laplacian5(v, h):
    v = np.asarray(v, float)
    return (v[2:,1:-1]+v[:-2,1:-1]+v[1:-1,2:]+v[1:-1,:-2]-4*v[1:-1,1:-1])/h**2


def solve_laplace_dirichlet(boundary, h, omega=1.85, tol=1e-8, max_iter=30000):
    """Red-black SOR for a square Dirichlet Laplace problem."""
    v = np.asarray(boundary, float).copy()
    fixed = np.isfinite(v)
    v[~fixed] = 0.0
    hist = []
    for it in range(max_iter):
        for parity in (0, 1):
            for i in range(1, v.shape[0]-1):
                js = np.arange(1, v.shape[1]-1)
                js = js[((i+js) % 2 == parity) & (~fixed[i, js])]
                if js.size:
                    new = .25*(v[i+1,js]+v[i-1,js]+v[i,js+1]+v[i,js-1])
                    v[i,js] = (1-omega)*v[i,js] + omega*new
        if it % 10 == 0:
            residual = np.max(np.abs(laplacian5(v, h)))
            hist.append(residual)
            if residual < tol:
                break
    return v, np.asarray(hist)


def pull_in_voltage(k, gap, eps, area):
    return np.sqrt(8*k*gap**3/(27*eps*area))


def electrostatic_energy(cmat, voltages):
    c = np.asarray(cmat, float); v = np.asarray(voltages, float)
    return 0.5 * v @ c @ v
