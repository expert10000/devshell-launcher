"""Commit 614 tight-binding/Wannier laboratory for Volume VIII Chapter 56.

The conventions are deliberately explicit:

* q = k a is the dimensionless crystal momentum in [-pi, pi].
* A scalar real hopping amplitude t_r > 0 enters the real-space Hamiltonian
  as <n|H|n+r> = -t_r, so E(q)=eps0-2 sum_r t_r cos(r q).
* For matrix-valued models, T_r denotes the actual hopping matrix from cell
  0 to cell +r, and H(q)=H0+sum_r[T_r exp(i r q)+T_r^dag exp(-i r q)].
* The dimerized two-sublattice model uses negative scalar hopping amplitudes
  -t_intra and -t_inter in the off-diagonal blocks.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

import numpy as np


@dataclass(frozen=True)
class HoppingFit:
    onsite: float
    hoppings: tuple[float, ...]
    rms_residual: float


def _positive_ncells(ncells: int) -> int:
    if not isinstance(ncells, (int, np.integer)) or isinstance(ncells, bool):
        raise ValueError("ncells must be an integer")
    n = int(ncells)
    if n < 2:
        raise ValueError("ncells must be at least 2")
    return n


def _real_hoppings(hoppings: Mapping[int, float]) -> dict[int, float]:
    out: dict[int, float] = {}
    for r, t in hoppings.items():
        if not isinstance(r, (int, np.integer)) or isinstance(r, bool) or int(r) < 1:
            raise ValueError("hopping ranges must be positive integers")
        rr = int(r)
        tt = float(t)
        if not np.isfinite(tt):
            raise ValueError("hopping amplitudes must be finite")
        out[rr] = tt
    return dict(sorted(out.items()))


def scalar_bloch_band(
    q: Iterable[float] | float,
    onsite: float = 0.0,
    hoppings: Mapping[int, float] | None = None,
) -> np.ndarray:
    """Return E(q)=eps0-2 sum_r t_r cos(r q)."""
    hs = _real_hoppings({1: 1.0} if hoppings is None else hoppings)
    qq = np.asarray(q, dtype=float)
    e = np.full_like(qq, float(onsite), dtype=float)
    for r, t in hs.items():
        e -= 2.0 * t * np.cos(r * qq)
    return e


def scalar_chain_hamiltonian(
    ncells: int,
    onsite: float = 0.0,
    hoppings: Mapping[int, float] | None = None,
    periodic: bool = False,
) -> np.ndarray:
    """Real-space scalar tight-binding Hamiltonian for open or periodic cells."""
    n = _positive_ncells(ncells)
    hs = _real_hoppings({1: 1.0} if hoppings is None else hoppings)
    if hs and max(hs) >= n:
        raise ValueError("every hopping range must be smaller than ncells")
    h = np.eye(n, dtype=float) * float(onsite)
    for r, t in hs.items():
        if periodic:
            # For the intended regime n > 2r, each bond is inserted once.
            if n <= 2 * r:
                raise ValueError("periodic scalar chain requires ncells > 2*max_range")
            for i in range(n):
                j = (i + r) % n
                h[i, j] += -t
                h[j, i] += -t
        else:
            for i in range(n - r):
                j = i + r
                h[i, j] += -t
                h[j, i] += -t
    return h


def sampled_periodic_momenta(ncells: int) -> np.ndarray:
    """Return q_m=2 pi m/N in FFT order."""
    n = _positive_ncells(ncells)
    return 2.0 * np.pi * np.arange(n, dtype=float) / n


def periodic_scalar_bloch_spectrum(
    ncells: int,
    onsite: float = 0.0,
    hoppings: Mapping[int, float] | None = None,
) -> np.ndarray:
    q = sampled_periodic_momenta(ncells)
    return np.sort(scalar_bloch_band(q, onsite=onsite, hoppings=hoppings))


def open_nn_analytic_spectrum(ncells: int, onsite: float, hopping: float) -> np.ndarray:
    """Exact open-chain nearest-neighbor levels."""
    n = _positive_ncells(ncells)
    j = np.arange(1, n + 1, dtype=float)
    return np.sort(float(onsite) - 2.0 * float(hopping) * np.cos(np.pi * j / (n + 1)))


def hopping_truncation_error_bound(
    hoppings: Mapping[int, float], retained_range: int
) -> float:
    """Uniform bound 2 sum_{r>R}|t_r| for a scalar cosine band."""
    hs = _real_hoppings(hoppings)
    if not isinstance(retained_range, (int, np.integer)) or int(retained_range) < 0:
        raise ValueError("retained_range must be a nonnegative integer")
    R = int(retained_range)
    return 2.0 * sum(abs(t) for r, t in hs.items() if r > R)


def hopping_truncation_error(
    hoppings: Mapping[int, float], retained_range: int, grid_points: int = 2001
) -> float:
    """Numerically evaluate max_q |E_full(q)-E_R(q)| on [-pi,pi]."""
    if grid_points < 9:
        raise ValueError("grid_points must be at least 9")
    hs = _real_hoppings(hoppings)
    R = int(retained_range)
    qs = np.linspace(-np.pi, np.pi, int(grid_points))
    full = scalar_bloch_band(qs, 0.0, hs)
    trunc = scalar_bloch_band(qs, 0.0, {r: t for r, t in hs.items() if r <= R})
    return float(np.max(np.abs(full - trunc)))


def fit_scalar_hopping_range(
    q: Iterable[float], energies: Iterable[float], max_range: int
) -> HoppingFit:
    """Fit E(q)=eps0-2 sum_{r=1}^R t_r cos(rq) by least squares."""
    qq = np.asarray(list(q), dtype=float)
    ee = np.asarray(list(energies), dtype=float)
    if qq.ndim != 1 or ee.ndim != 1 or qq.size != ee.size:
        raise ValueError("q and energies must be equally sized one-dimensional arrays")
    if not isinstance(max_range, (int, np.integer)) or int(max_range) < 0:
        raise ValueError("max_range must be a nonnegative integer")
    R = int(max_range)
    if qq.size < 2 * R + 3:
        raise ValueError("not enough samples for the requested hopping range")
    cols = [np.ones_like(qq)]
    cols.extend(-2.0 * np.cos(r * qq) for r in range(1, R + 1))
    design = np.column_stack(cols)
    coeff, *_ = np.linalg.lstsq(design, ee, rcond=None)
    residual = ee - design @ coeff
    return HoppingFit(
        onsite=float(coeff[0]),
        hoppings=tuple(float(x) for x in coeff[1:]),
        rms_residual=float(np.sqrt(np.mean(residual * residual))),
    )


def hopping_coefficients_from_sampled_band(energies: Iterable[float]) -> np.ndarray:
    """Inverse discrete Fourier coefficients h_r for E(q)=sum_r h_r exp(i q r).

    Energies are assumed to be sampled at q_m=2 pi m/N.  The result is in
    periodic range-index order r=0,...,N-1.  For a nearest-neighbor band
    eps0-2t cos(q), h_0=eps0 and h_1=h_{N-1}=-t.
    """
    e = np.asarray(list(energies), dtype=complex)
    if e.ndim != 1 or e.size < 2:
        raise ValueError("energies must be a one-dimensional array of length >=2")
    return np.fft.fft(e) / e.size


def reconstruct_sampled_band_from_hoppings(coefficients: Iterable[complex]) -> np.ndarray:
    """Reconstruct sampled energies from periodic hopping coefficients."""
    h = np.asarray(list(coefficients), dtype=complex)
    if h.ndim != 1 or h.size < 2:
        raise ValueError("coefficients must be a one-dimensional array of length >=2")
    return np.fft.ifft(h * h.size)


def wannier_coefficients_from_gauge(phases: Iterable[float], cell: int = 0) -> np.ndarray:
    """Site-basis coefficients of a discrete one-band Wannier state.

    The Bloch states obey |psi_q> = N^{-1/2} sum_j exp(i q j)|j> and the
    chosen gauge multiplies them by exp(i phi_q).  The returned coefficients
    are for |w_cell> = N^{-1/2} sum_q exp(-i q cell) exp(i phi_q)|psi_q>.
    """
    phi = np.asarray(list(phases), dtype=float)
    if phi.ndim != 1 or phi.size < 2:
        raise ValueError("phases must be a one-dimensional array of length >=2")
    n = phi.size
    if not isinstance(cell, (int, np.integer)):
        raise ValueError("cell must be an integer")
    q = sampled_periodic_momenta(n)
    j = np.arange(n, dtype=float)
    # c_j=(1/N) sum_q exp[i q(j-cell)] exp[i phi_q]
    phase_matrix = np.exp(1j * np.outer(q, j - int(cell)))
    c = np.sum(np.exp(1j * phi)[:, None] * phase_matrix, axis=0) / n
    return c


def wannier_ipr(coefficients: Iterable[complex]) -> float:
    c = np.asarray(list(coefficients), dtype=complex)
    norm = float(np.sum(np.abs(c) ** 2))
    if norm <= 0.0:
        raise ValueError("Wannier coefficients have zero norm")
    p = np.abs(c) ** 2 / norm
    return float(np.sum(p * p))


def wannier_peak_cell(coefficients: Iterable[complex]) -> int:
    c = np.asarray(list(coefficients), dtype=complex)
    if c.ndim != 1 or c.size == 0:
        raise ValueError("coefficients must be a non-empty one-dimensional array")
    return int(np.argmax(np.abs(c) ** 2))


def bloch_matrix(
    q: float,
    onsite_matrix: np.ndarray,
    hopping_matrices: Mapping[int, np.ndarray] | None = None,
) -> np.ndarray:
    """General orthonormal multi-orbital H(q)=H0+sum(T_r e^{irq}+h.c.)."""
    h0 = np.asarray(onsite_matrix, dtype=complex)
    if h0.ndim != 2 or h0.shape[0] != h0.shape[1] or h0.shape[0] == 0:
        raise ValueError("onsite_matrix must be a non-empty square matrix")
    if not np.allclose(h0, h0.conj().T, atol=1e-12):
        raise ValueError("onsite_matrix must be Hermitian")
    h = h0.copy()
    for r, mat in sorted((hopping_matrices or {}).items()):
        if not isinstance(r, (int, np.integer)) or int(r) < 1:
            raise ValueError("matrix hopping ranges must be positive integers")
        t = np.asarray(mat, dtype=complex)
        if t.shape != h0.shape:
            raise ValueError("every hopping matrix must match onsite_matrix shape")
        phase = np.exp(1j * int(r) * float(q))
        h += t * phase + t.conj().T * phase.conjugate()
    return h


def dimerized_bloch_hamiltonian(
    q: float,
    t_intra: float,
    t_inter: float,
    delta: float = 0.0,
    mean_onsite: float = 0.0,
) -> np.ndarray:
    """Two-sublattice Bloch Hamiltonian for a dimerized chain."""
    off = -(float(t_intra) + float(t_inter) * np.exp(-1j * float(q)))
    return np.array(
        [
            [float(mean_onsite) + float(delta), off],
            [off.conjugate(), float(mean_onsite) - float(delta)],
        ],
        dtype=complex,
    )


def dimerized_bands(
    q: Iterable[float] | float,
    t_intra: float,
    t_inter: float,
    delta: float = 0.0,
    mean_onsite: float = 0.0,
) -> np.ndarray:
    qq = np.asarray(q, dtype=float)
    flat = qq.reshape(-1)
    vals = np.vstack(
        [
            np.linalg.eigvalsh(
                dimerized_bloch_hamiltonian(x, t_intra, t_inter, delta, mean_onsite)
            )
            for x in flat
        ]
    )
    return vals.reshape(qq.shape + (2,))


def dimerized_direct_gap(t_intra: float, t_inter: float, delta: float = 0.0) -> float:
    """Direct gap at q=pi: 2 sqrt(delta^2+(t_intra-t_inter)^2)."""
    return 2.0 * float(np.sqrt(float(delta) ** 2 + (float(t_intra) - float(t_inter)) ** 2))


def dimerized_chain_hamiltonian(
    ncells: int,
    t_intra: float,
    t_inter: float,
    delta: float = 0.0,
    mean_onsite: float = 0.0,
    periodic: bool = False,
) -> np.ndarray:
    """Finite real-space two-sublattice chain in basis A0,B0,A1,B1,..."""
    n = _positive_ncells(ncells)
    h = np.zeros((2 * n, 2 * n), dtype=float)
    for cell in range(n):
        a = 2 * cell
        b = a + 1
        h[a, a] = float(mean_onsite) + float(delta)
        h[b, b] = float(mean_onsite) - float(delta)
        h[a, b] = h[b, a] = -float(t_intra)
        if cell < n - 1:
            anext = 2 * (cell + 1)
            h[b, anext] = h[anext, b] = -float(t_inter)
    if periodic:
        b_last = 2 * (n - 1) + 1
        h[b_last, 0] = h[0, b_last] = -float(t_inter)
    return h


def periodic_dimerized_bloch_spectrum(
    ncells: int,
    t_intra: float,
    t_inter: float,
    delta: float = 0.0,
    mean_onsite: float = 0.0,
) -> np.ndarray:
    q = sampled_periodic_momenta(ncells)
    return np.sort(
        dimerized_bands(q, t_intra, t_inter, delta, mean_onsite).reshape(-1)
    )
