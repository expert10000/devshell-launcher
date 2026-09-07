"""Quantitative one-dimensional periodic-Hamiltonian laboratory for Chapter 56.

The plane-wave model uses the first-Brillouin-zone coordinate

    kappa = k / (pi/a),   -1 <= kappa <= 1,

and the recoil/zone-edge energy

    E_R = hbar^2 (pi/a)^2 / (2m).

For V(x) = 2 V1 cos(2 pi x/a) + 2 V2 cos(4 pi x/a), the dimensionless
plane-wave Hamiltonian in |k+nG> with G=2pi/a is

    H_nm/E_R = (kappa + 2n)^2 delta_nm
               + v1 delta_|n-m|,1 + v2 delta_|n-m|,2,

where vj = Vj/E_R.

The module deliberately keeps the model compact and deterministic so that the
textbook can use it both as an executable example and as a regression oracle.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np


@dataclass(frozen=True)
class CutoffDiagnostic:
    cutoff: int
    next_cutoff: int
    max_band_error: float
    gap: float
    next_gap: float
    gap_error: float


@dataclass(frozen=True)
class TightBindingFit:
    onsite: float
    hopping: float
    rms_residual: float


def _validate_cutoff(cutoff: int) -> int:
    if isinstance(cutoff, bool) or int(cutoff) != cutoff or cutoff < 0:
        raise ValueError("cutoff must be a non-negative integer")
    return int(cutoff)


def _validate_band_count(num_bands: int | None, dimension: int) -> int:
    if num_bands is None:
        return dimension
    if isinstance(num_bands, bool) or int(num_bands) != num_bands:
        raise ValueError("num_bands must be an integer")
    num_bands = int(num_bands)
    if not 1 <= num_bands <= dimension:
        raise ValueError("num_bands must lie between 1 and the basis dimension")
    return num_bands


def plane_wave_indices(cutoff: int) -> np.ndarray:
    """Return reciprocal indices n=-N,...,+N for a symmetric cutoff N."""
    cutoff = _validate_cutoff(cutoff)
    return np.arange(-cutoff, cutoff + 1, dtype=int)


def cosine_plane_wave_hamiltonian(
    kappa: float,
    v1: float,
    cutoff: int,
    v2: float = 0.0,
) -> np.ndarray:
    """Build H(k)/E_R for a one-dimensional cosine lattice.

    Parameters
    ----------
    kappa:
        Dimensionless Bloch wavevector k/(pi/a).
    v1:
        First Fourier amplitude V_G/E_R for G=2pi/a.
    cutoff:
        Reciprocal index cutoff N.  The basis dimension is 2N+1.
    v2:
        Optional second harmonic V_2G/E_R.
    """
    n = plane_wave_indices(cutoff)
    dim = n.size
    h = np.diag((float(kappa) + 2.0 * n) ** 2).astype(float)

    if v1 != 0.0:
        for i in range(dim - 1):
            h[i, i + 1] = float(v1)
            h[i + 1, i] = float(v1)
    if v2 != 0.0:
        for i in range(dim - 2):
            h[i, i + 2] = float(v2)
            h[i + 2, i] = float(v2)
    return h


def plane_wave_eigenvalues(
    kappa: float,
    v1: float,
    cutoff: int,
    num_bands: int | None = None,
    v2: float = 0.0,
) -> np.ndarray:
    """Return sorted plane-wave eigenvalues in units of E_R."""
    h = cosine_plane_wave_hamiltonian(kappa, v1, cutoff, v2=v2)
    count = _validate_band_count(num_bands, h.shape[0])
    return np.linalg.eigvalsh(h)[:count]


def plane_wave_bands(
    kappas: Iterable[float],
    v1: float,
    cutoff: int,
    num_bands: int,
    v2: float = 0.0,
) -> np.ndarray:
    """Evaluate the lowest bands on a kappa grid.

    Returns an array of shape (len(kappas), num_bands).
    """
    ks = np.asarray(list(kappas), dtype=float)
    if ks.ndim != 1 or ks.size == 0:
        raise ValueError("kappas must be a non-empty one-dimensional sequence")
    dim = 2 * _validate_cutoff(cutoff) + 1
    count = _validate_band_count(num_bands, dim)
    return np.vstack(
        [plane_wave_eigenvalues(k, v1, cutoff, count, v2=v2) for k in ks]
    )


def first_zone_gap(v1: float, cutoff: int, v2: float = 0.0) -> float:
    """Return the first band gap at kappa=+1 in units of E_R."""
    ev = plane_wave_eigenvalues(1.0, v1, cutoff, num_bands=2, v2=v2)
    return float(ev[1] - ev[0])


def cutoff_diagnostic(
    v1: float,
    cutoff: int,
    num_bands: int = 3,
    grid_points: int = 81,
    v2: float = 0.0,
) -> CutoffDiagnostic:
    """Compare cutoff N with N+1 over the first Brillouin zone."""
    cutoff = _validate_cutoff(cutoff)
    if grid_points < 3:
        raise ValueError("grid_points must be at least 3")
    dim = 2 * cutoff + 1
    _validate_band_count(num_bands, dim)
    ks = np.linspace(-1.0, 1.0, int(grid_points))
    a = plane_wave_bands(ks, v1, cutoff, num_bands, v2=v2)
    b = plane_wave_bands(ks, v1, cutoff + 1, num_bands, v2=v2)
    gap_a = first_zone_gap(v1, cutoff, v2=v2)
    gap_b = first_zone_gap(v1, cutoff + 1, v2=v2)
    return CutoffDiagnostic(
        cutoff=cutoff,
        next_cutoff=cutoff + 1,
        max_band_error=float(np.max(np.abs(a - b))),
        gap=gap_a,
        next_gap=gap_b,
        gap_error=abs(gap_a - gap_b),
    )


def effective_mass_ratio_from_band(
    v1: float,
    cutoff: int,
    dkappa: float = 1.0e-3,
    v2: float = 0.0,
) -> float:
    """Estimate m*/m at the bottom of the first band.

    In the chosen units d^2 E/dk^2 = (hbar^2/2m) f''(kappa), hence
    m*/m = 2/f'' for E/E_R=f(kappa).
    """
    if not 0.0 < dkappa < 0.25:
        raise ValueError("dkappa must lie between 0 and 0.25")
    em = plane_wave_eigenvalues(-dkappa, v1, cutoff, 1, v2=v2)[0]
    e0 = plane_wave_eigenvalues(0.0, v1, cutoff, 1, v2=v2)[0]
    ep = plane_wave_eigenvalues(+dkappa, v1, cutoff, 1, v2=v2)[0]
    curvature = float((ep - 2.0 * e0 + em) / (dkappa * dkappa))
    if abs(curvature) < 1.0e-14:
        return float("inf")
    return 2.0 / curvature


def tight_binding_band(
    kappa: Iterable[float] | float,
    hopping: float,
    onsite: float = 0.0,
) -> np.ndarray:
    """Nearest-neighbour one-orbital chain, E=eps0-2t cos(ka).

    Since ka = pi*kappa in the Chapter 56 convention, the first zone is
    kappa in [-1,1].
    """
    k = np.asarray(kappa, dtype=float)
    return float(onsite) - 2.0 * float(hopping) * np.cos(np.pi * k)


def tight_binding_bandwidth(hopping: float) -> float:
    """Return the nearest-neighbour one-band width 4|t|."""
    return 4.0 * abs(float(hopping))


def tight_binding_effective_mass_scale(hopping: float) -> float:
    """Return m*/m_ref for a reference free mass with E_R units.

    If the same lattice spacing a and reference mass m define
    E_R=hbar^2 pi^2/(2ma^2), then for E/E_R=eps-2 tau cos(pi*kappa),
    with tau=t/E_R, the band-bottom curvature gives m*/m=1/(pi^2 tau).
    """
    t = float(hopping)
    if t <= 0.0:
        raise ValueError("hopping must be positive for a minimum at kappa=0")
    return 1.0 / (np.pi * np.pi * t)


def fit_nearest_neighbour_tight_binding(
    kappas: Iterable[float], energies: Iterable[float]
) -> TightBindingFit:
    """Least-squares fit E(k)=eps0-2t cos(pi*kappa)."""
    k = np.asarray(list(kappas), dtype=float)
    e = np.asarray(list(energies), dtype=float)
    if k.ndim != 1 or e.ndim != 1 or k.size != e.size or k.size < 3:
        raise ValueError("kappas and energies must be equally sized 1D arrays with >=3 points")
    design = np.column_stack([np.ones_like(k), np.cos(np.pi * k)])
    coeff, *_ = np.linalg.lstsq(design, e, rcond=None)
    onsite = float(coeff[0])
    hopping = float(-0.5 * coeff[1])
    residual = e - design @ coeff
    rms = float(np.sqrt(np.mean(residual * residual)))
    return TightBindingFit(onsite=onsite, hopping=hopping, rms_residual=rms)


def fit_first_plane_wave_band_to_tight_binding(
    v1: float,
    cutoff: int,
    grid_points: int = 101,
    v2: float = 0.0,
) -> TightBindingFit:
    """Fit the lowest plane-wave band over the full first Brillouin zone."""
    if grid_points < 5:
        raise ValueError("grid_points must be at least 5")
    ks = np.linspace(-1.0, 1.0, int(grid_points))
    e1 = plane_wave_bands(ks, v1, cutoff, 1, v2=v2)[:, 0]
    return fit_nearest_neighbour_tight_binding(ks, e1)
