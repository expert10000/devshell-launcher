"""Computational companion for Volume VIII, Chapter 51.

Dimensionless defaults use hbar=m=1.  The routines are deliberately small and
transparent so analytic matching, transfer matrices, and finite-difference
Hamiltonians can cross-check one another.
"""
from __future__ import annotations

from typing import Iterable
import numpy as np


def finite_well_state_count(z0: float) -> int:
    """Number of normalizable bound states for a symmetric well of half-width a.

    z0=a*sqrt(2mV0)/hbar.  At exact zero-energy thresholds the threshold state
    is not counted as square-integrable, which is captured by ceil(2 z0/pi).
    """
    if z0 <= 0:
        raise ValueError("z0 must be positive")
    return int(np.ceil(2.0 * z0 / np.pi - 1e-14))


def _bisect(func, lo: float, hi: float, *, tol: float = 1e-13, max_iter: int = 200) -> float:
    flo, fhi = func(lo), func(hi)
    if not np.isfinite(flo) or not np.isfinite(fhi) or flo * fhi > 0:
        raise ValueError("root is not bracketed")
    for _ in range(max_iter):
        mid = 0.5 * (lo + hi)
        fm = func(mid)
        if abs(fm) < tol or hi - lo < tol:
            return mid
        if flo * fm <= 0:
            hi, fhi = mid, fm
        else:
            lo, flo = mid, fm
    return 0.5 * (lo + hi)


def finite_well_dimensionless_roots(z0: float) -> np.ndarray:
    """Return z=ka roots ordered from deepest to shallowest bound state."""
    nstates = finite_well_state_count(z0)
    roots = []
    tiny = 1e-10
    for j in range(nstates):
        left = j * np.pi / 2.0
        right_branch = (j + 1) * np.pi / 2.0
        lo = left + tiny
        hi = min(right_branch - tiny, z0 - tiny)
        if not lo < hi:
            continue
        if j % 2 == 0:  # even parity interval
            def f(z):
                return z * np.tan(z) - np.sqrt(max(z0 * z0 - z * z, 0.0))
        else:  # odd parity interval
            def f(z):
                return -z / np.tan(z) - np.sqrt(max(z0 * z0 - z * z, 0.0))
        roots.append(_bisect(f, lo, hi))
    return np.asarray(roots)


def finite_well_energy_ratios(z0: float) -> np.ndarray:
    """Return E/V0 in (-1,0) for the finite-well bound states."""
    z = finite_well_dimensionless_roots(z0)
    return z * z / (z0 * z0) - 1.0


def rectangular_barrier_transmission(E: np.ndarray | float, V0: float, width: float,
                                     *, mass: float = 1.0, hbar: float = 1.0) -> np.ndarray:
    """Exact transmission through a single rectangular barrier."""
    e = np.asarray(E, dtype=float)
    if V0 <= 0 or width < 0 or mass <= 0 or hbar <= 0:
        raise ValueError("require V0,mass,hbar>0 and width>=0")
    if np.any(e <= 0):
        raise ValueError("E must be positive")
    out = np.empty_like(e)
    below = e < V0
    above = e > V0
    equal = ~(below | above)
    if np.any(below):
        eb = e[below]
        kappa = np.sqrt(2.0 * mass * (V0 - eb)) / hbar
        denom = 1.0 + V0 * V0 * np.sinh(kappa * width) ** 2 / (4.0 * eb * (V0 - eb))
        out[below] = 1.0 / denom
    if np.any(above):
        ea = e[above]
        q = np.sqrt(2.0 * mass * (ea - V0)) / hbar
        denom = 1.0 + V0 * V0 * np.sin(q * width) ** 2 / (4.0 * ea * (ea - V0))
        out[above] = 1.0 / denom
    if np.any(equal):
        # continuous E -> V0 limit: sinh(kappa d)/kappa -> d
        out[equal] = 1.0 / (1.0 + mass * V0 * width * width / (2.0 * hbar * hbar))
    return out


def wkb_rectangular_transmission(E: np.ndarray | float, V0: float, width: float,
                                 *, mass: float = 1.0, hbar: float = 1.0) -> np.ndarray:
    e = np.asarray(E, dtype=float)
    if np.any((e <= 0) | (e >= V0)):
        raise ValueError("WKB barrier helper requires 0<E<V0")
    kappa = np.sqrt(2.0 * mass * (V0 - e)) / hbar
    return np.exp(-2.0 * kappa * width)


def propagation_matrix(E: float, V: float, width: float, *, mass: float = 1.0,
                       hbar: float = 1.0) -> np.ndarray:
    """Map [psi,psi'] across one constant-potential segment."""
    if E <= 0 or width < 0 or mass <= 0 or hbar <= 0:
        raise ValueError("invalid propagation parameters")
    k = np.sqrt(2.0 * mass * complex(E - V)) / hbar
    kd = k * width
    c, s = np.cos(kd), np.sin(kd)
    return np.array([[c, s / k], [-k * s, c]], dtype=complex)


def multilayer_transfer_matrix(E: float, segments: Iterable[tuple[float, float]],
                               *, mass: float = 1.0, hbar: float = 1.0) -> np.ndarray:
    total = np.eye(2, dtype=complex)
    for V, width in segments:
        total = propagation_matrix(E, V, width, mass=mass, hbar=hbar) @ total
    return total


def multilayer_transmission(E: float, segments: Iterable[tuple[float, float]],
                            *, lead_potential: float = 0.0, mass: float = 1.0,
                            hbar: float = 1.0) -> float:
    if E <= lead_potential:
        raise ValueError("lead channel must be propagating")
    k = np.sqrt(2.0 * mass * (E - lead_potential)) / hbar
    M = multilayer_transfer_matrix(E, segments, mass=mass, hbar=hbar)
    incoming = M @ np.array([1.0, 1j * k], dtype=complex)
    reflected = M @ np.array([1.0, -1j * k], dtype=complex)
    outgoing = np.array([1.0, 1j * k], dtype=complex)
    # incoming + r*reflected = t*outgoing
    A = np.column_stack((reflected, -outgoing))
    r, t = np.linalg.solve(A, -incoming)
    T = float(abs(t) ** 2)
    return min(max(T, 0.0), 1.0 + 1e-10)


def finite_difference_hamiltonian(x: np.ndarray, potential: np.ndarray,
                                  *, mass: float = 1.0, hbar: float = 1.0) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    v = np.asarray(potential, dtype=float)
    if x.ndim != 1 or v.shape != x.shape or x.size < 4:
        raise ValueError("x and potential must be equal one-dimensional arrays")
    dx = np.diff(x)
    if not np.allclose(dx, dx[0], rtol=1e-10, atol=1e-12):
        raise ValueError("grid must be uniform")
    if mass <= 0 or hbar <= 0:
        raise ValueError("mass and hbar must be positive")
    # Interior points implement Dirichlet boundaries at the two end points.
    vi = v[1:-1]
    n = vi.size
    t = hbar * hbar / (2.0 * mass * dx[0] ** 2)
    H = np.diag(2.0 * t + vi)
    H += np.diag(np.full(n - 1, -t), 1) + np.diag(np.full(n - 1, -t), -1)
    return H


def finite_difference_spectrum(x: np.ndarray, potential: np.ndarray, *, levels: int = 6,
                               mass: float = 1.0, hbar: float = 1.0) -> np.ndarray:
    H = finite_difference_hamiltonian(x, potential, mass=mass, hbar=hbar)
    values = np.linalg.eigvalsh(H)
    return values[:levels]


def symmetric_square_well_potential(x: np.ndarray, depth: float, half_width: float) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    if depth <= 0 or half_width <= 0:
        raise ValueError("depth and half_width must be positive")
    return np.where(np.abs(x) < half_width, -depth, 0.0)



def density_of_states_shape(energy: np.ndarray | float, edge: float, dimension: int,
                            *, broadening: float = 0.03) -> np.ndarray:
    """Dimensionless DOS edge shape for D=0,1,2,3.

    D=0 uses a normalized Gaussian only for visualization of a discrete line.
    D=1..3 return the power-law shape above the edge with a small regulator for
    the ideal 1D singularity.
    """
    e = np.asarray(energy, dtype=float)
    if dimension not in (0, 1, 2, 3):
        raise ValueError("dimension must be 0,1,2,3")
    if dimension == 0:
        if broadening <= 0:
            raise ValueError("broadening must be positive")
        return np.exp(-0.5 * ((e - edge) / broadening) ** 2) / (broadening * np.sqrt(2*np.pi))
    x = e - edge
    out = np.zeros_like(e)
    mask = x > 0
    if dimension == 1:
        out[mask] = 1.0 / np.sqrt(np.maximum(x[mask], 1e-12))
    elif dimension == 2:
        out[mask] = 1.0
    else:
        out[mask] = np.sqrt(x[mask])
    return out


def variable_mass_hamiltonian(x: np.ndarray, potential: np.ndarray, mass_profile: np.ndarray,
                              *, hbar: float = 1.0) -> np.ndarray:
    """BenDaniel-Duke flux-form finite-difference Hamiltonian on interior points."""
    x = np.asarray(x, dtype=float)
    v = np.asarray(potential, dtype=float)
    m = np.asarray(mass_profile, dtype=float)
    if x.ndim != 1 or v.shape != x.shape or m.shape != x.shape or x.size < 4:
        raise ValueError("x, potential, mass_profile must be equal 1D arrays")
    dxs = np.diff(x)
    if not np.allclose(dxs, dxs[0], rtol=1e-10, atol=1e-12):
        raise ValueError("grid must be uniform")
    if np.any(m <= 0) or hbar <= 0:
        raise ValueError("masses and hbar must be positive")
    dx = dxs[0]
    invm = 1.0 / m
    link = 0.5 * (invm[:-1] + invm[1:]) * hbar*hbar/(2.0*dx*dx)
    # interior i=1..N-2 uses links i-1/2 and i+1/2
    diag = link[:-1] + link[1:] + v[1:-1]
    off = -link[1:-1]
    H = np.diag(diag)
    H += np.diag(off, 1) + np.diag(off, -1)
    return H


def variable_mass_eigensystem(x: np.ndarray, potential: np.ndarray, mass_profile: np.ndarray,
                              *, levels: int = 4, hbar: float = 1.0) -> tuple[np.ndarray, np.ndarray]:
    H = variable_mass_hamiltonian(x, potential, mass_profile, hbar=hbar)
    values, vectors = np.linalg.eigh(H)
    return values[:levels], vectors[:, :levels]


def exterior_probability(x: np.ndarray, interior_vector: np.ndarray, half_width: float) -> float:
    """Approximate probability outside |x|<half_width for a Dirichlet-grid eigenvector."""
    x = np.asarray(x, dtype=float)
    psi = np.asarray(interior_vector)
    if psi.shape != (x.size - 2,):
        raise ValueError("interior_vector must match x[1:-1]")
    xi = x[1:-1]
    weights = np.abs(psi)**2
    norm = float(np.sum(weights))
    if norm <= 0:
        raise ValueError("zero vector")
    return float(np.sum(weights[np.abs(xi) >= half_width]) / norm)


def symmetric_double_well_potential(x: np.ndarray, *, well_depth: float = 1.0,
                                    center: float = 1.5, well_half_width: float = 0.65,
                                    central_barrier: float = 0.0) -> np.ndarray:
    """Two square wells plus an optional central barrier shift."""
    x = np.asarray(x, dtype=float)
    if well_depth <= 0 or center <= well_half_width or well_half_width <= 0:
        raise ValueError("invalid double-well geometry")
    v = np.zeros_like(x)
    left = np.abs(x + center) < well_half_width
    right = np.abs(x - center) < well_half_width
    v[left | right] = -well_depth
    gap = np.abs(x) < (center - well_half_width)
    v[gap] = central_barrier
    return v


def double_well_splitting(x: np.ndarray, potential: np.ndarray, *, mass: float = 1.0,
                          hbar: float = 1.0) -> float:
    vals = finite_difference_spectrum(x, potential, levels=2, mass=mass, hbar=hbar)
    return float(vals[1] - vals[0])


def tilted_potential(x: np.ndarray, base_potential: np.ndarray, slope: float) -> np.ndarray:
    """Return V(x)+slope*x, where slope=dV/dx is an energy gradient."""
    x = np.asarray(x, dtype=float)
    v = np.asarray(base_potential, dtype=float)
    if x.ndim != 1 or v.shape != x.shape:
        raise ValueError("x and base_potential must be equal one-dimensional arrays")
    return v + float(slope) * x


def position_expectation(x: np.ndarray, interior_vector: np.ndarray) -> float:
    """Grid-normalized <x> for an eigenvector defined on x[1:-1]."""
    x = np.asarray(x, dtype=float)
    psi = np.asarray(interior_vector)
    if psi.shape != (x.size - 2,):
        raise ValueError("interior_vector must match x[1:-1]")
    w = np.abs(psi) ** 2
    norm = float(np.sum(w))
    if norm <= 0:
        raise ValueError("zero vector")
    return float(np.sum(x[1:-1] * w) / norm)


def two_level_energies(detuning: np.ndarray | float, tunnel: float,
                       *, mean_energy: float = 0.0) -> np.ndarray:
    """Eigenenergies of [[delta/2,t],[t,-delta/2]] plus a common offset."""
    d = np.asarray(detuning, dtype=float)
    t = float(tunnel)
    split = np.sqrt((0.5 * d) ** 2 + t * t)
    return np.stack((mean_energy - split, mean_energy + split), axis=-1)


def two_level_polarization(detuning: np.ndarray | float, tunnel: float) -> np.ndarray:
    """Ground-state expectation of sigma_z for H=(delta/2)sigma_z+t sigma_x."""
    d = np.asarray(detuning, dtype=float)
    t = float(tunnel)
    denom = np.sqrt(d * d + 4.0 * t * t)
    if np.any(denom == 0):
        raise ValueError("detuning=tunnel=0 leaves polarization undefined")
    return -d / denom


def lorentzian_transmission(energy: np.ndarray | float, center: float, linewidth: float,
                            *, peak: float = 1.0) -> np.ndarray:
    """Breit-Wigner/Lorentzian resonance with FWHM=linewidth."""
    e = np.asarray(energy, dtype=float)
    if linewidth <= 0 or not (0.0 <= peak <= 1.0):
        raise ValueError("linewidth must be positive and 0<=peak<=1")
    half = 0.5 * linewidth
    return peak * half * half / ((e - center) ** 2 + half * half)


def fermi_function(energy: np.ndarray | float, chemical_potential: float,
                   thermal_energy: float) -> np.ndarray:
    """Fermi function with thermal_energy=k_B T expressed in the energy units used."""
    e = np.asarray(energy, dtype=float)
    if thermal_energy < 0:
        raise ValueError("thermal_energy must be nonnegative")
    if thermal_energy == 0:
        return (e < chemical_potential).astype(float) + 0.5 * (e == chemical_potential)
    arg = np.clip((e - chemical_potential) / thermal_energy, -700.0, 700.0)
    return 1.0 / (np.exp(arg) + 1.0)


def landauer_conductance_dimensionless(energy: np.ndarray, transmission: np.ndarray,
                                       chemical_potential: float, thermal_energy: float,
                                       *, degeneracy: float = 2.0) -> float:
    """Return G/(e^2/h) for one transmission curve, including degeneracy."""
    e = np.asarray(energy, dtype=float)
    T = np.asarray(transmission, dtype=float)
    if e.ndim != 1 or T.shape != e.shape or e.size < 3 or np.any(np.diff(e) <= 0):
        raise ValueError("energy must be a strictly increasing 1D grid matching transmission")
    if np.any((T < -1e-12) | (T > 1.0 + 1e-12)) or degeneracy <= 0:
        raise ValueError("transmission must lie in [0,1] and degeneracy must be positive")
    if thermal_energy < 0:
        raise ValueError("thermal_energy must be nonnegative")
    if thermal_energy == 0:
        return float(degeneracy * np.interp(chemical_potential, e, T))
    f = fermi_function(e, chemical_potential, thermal_energy)
    minus_df = f * (1.0 - f) / thermal_energy
    return float(degeneracy * np.trapezoid(T * minus_df, e))


def landauer_current_dimensionless(energy: np.ndarray, transmission: np.ndarray,
                                   mu_left: float, mu_right: float, thermal_energy: float,
                                   *, degeneracy: float = 2.0) -> float:
    """Return I/(e/h) when all energies use the same units."""
    e = np.asarray(energy, dtype=float)
    T = np.asarray(transmission, dtype=float)
    if e.ndim != 1 or T.shape != e.shape or e.size < 3 or np.any(np.diff(e) <= 0):
        raise ValueError("energy must be a strictly increasing 1D grid matching transmission")
    if np.any((T < -1e-12) | (T > 1.0 + 1e-12)) or degeneracy <= 0:
        raise ValueError("invalid transmission or degeneracy")
    fL = fermi_function(e, mu_left, thermal_energy)
    fR = fermi_function(e, mu_right, thermal_energy)
    return float(degeneracy * np.trapezoid(T * (fL - fR), e))


def poisson_dirichlet_1d(x: np.ndarray, charge_density: np.ndarray, *, permittivity: float = 1.0,
                         left_potential: float = 0.0, right_potential: float = 0.0) -> np.ndarray:
    """Solve phi''=-rho/epsilon on a uniform 1D grid with Dirichlet boundaries."""
    x = np.asarray(x, dtype=float)
    rho = np.asarray(charge_density, dtype=float)
    if x.ndim != 1 or rho.shape != x.shape or x.size < 4:
        raise ValueError("x and charge_density must be equal one-dimensional arrays")
    dx = np.diff(x)
    if not np.allclose(dx, dx[0], rtol=1e-10, atol=1e-12):
        raise ValueError("grid must be uniform")
    if permittivity <= 0:
        raise ValueError("permittivity must be positive")
    n = x.size - 2
    A = np.diag(np.full(n, -2.0))
    A += np.diag(np.ones(n - 1), 1) + np.diag(np.ones(n - 1), -1)
    b = -(dx[0] ** 2 / permittivity) * rho[1:-1]
    b[0] -= left_potential
    b[-1] -= right_potential
    phi = np.empty_like(x)
    phi[0] = left_potential
    phi[-1] = right_potential
    phi[1:-1] = np.linalg.solve(A, b)
    return phi
