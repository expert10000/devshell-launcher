"""Quantitative model-comparison companion for Volume VIII, Chapter 50.

The module deliberately uses only small dense matrices and analytic spectra.
Its purpose is not high-performance simulation; it is to make the Chapter 50
Hamiltonian Laboratory executable and auditable.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np


@dataclass(frozen=True)
class SweepResult:
    parameter: np.ndarray
    eigenvalues: np.ndarray


def _as_hermitian_matrix(matrix: np.ndarray, *, atol: float = 1e-12) -> np.ndarray:
    h = np.asarray(matrix, dtype=complex)
    if h.ndim != 2 or h.shape[0] != h.shape[1]:
        raise ValueError("Hamiltonian must be a square matrix")
    if not np.all(np.isfinite(h)):
        raise ValueError("Hamiltonian contains non-finite entries")
    if not np.allclose(h, h.conj().T, atol=atol, rtol=0.0):
        raise ValueError("Hamiltonian must be Hermitian")
    return h


def hermitian_eigensystem(matrix: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return ascending eigenvalues and orthonormal eigenvectors."""
    h = _as_hermitian_matrix(matrix)
    values, vectors = np.linalg.eigh(h)
    return values.real, vectors


def two_level_hamiltonian(detuning: float, coupling: float) -> np.ndarray:
    """H = (detuning sigma_z + coupling sigma_x)/2 in dimensionless units."""
    return 0.5 * np.array(
        [[detuning, coupling], [coupling, -detuning]], dtype=float
    )


def two_level_energies(detuning: np.ndarray | float, coupling: float) -> np.ndarray:
    d = np.asarray(detuning, dtype=float)
    radius = np.sqrt(d * d + coupling * coupling)
    return np.stack((-0.5 * radius, 0.5 * radius), axis=-1)


def two_level_ground_character(detuning: np.ndarray | float, coupling: float) -> np.ndarray:
    """Ground-state expectation value <sigma_z>."""
    d = np.asarray(detuning, dtype=float)
    radius = np.sqrt(d * d + coupling * coupling)
    if np.any(radius == 0.0):
        raise ValueError("detuning and coupling cannot both vanish")
    return -d / radius


def two_level_sweep(detunings: Iterable[float], coupling: float) -> SweepResult:
    grid = np.asarray(list(detunings), dtype=float)
    return SweepResult(grid, two_level_energies(grid, coupling))


def ladder_operators(dimension: int) -> tuple[np.ndarray, np.ndarray]:
    if dimension < 2:
        raise ValueError("dimension must be at least 2")
    a = np.zeros((dimension, dimension), dtype=float)
    for n in range(1, dimension):
        a[n - 1, n] = np.sqrt(n)
    return a, a.T


def anharmonic_oscillator_hamiltonian(dimension: int, quartic_strength: float) -> np.ndarray:
    """Dimensionless H/(hbar omega) = N + 1/2 + lambda xbar^4.

    xbar=(a+a^dagger)/sqrt(2), so lambda is dimensionless.
    Positive lambda gives a stable quartic stiffening of the oscillator.
    """
    if quartic_strength < 0:
        raise ValueError("quartic_strength must be non-negative in this companion")
    a, adag = ladder_operators(dimension)
    number = adag @ a
    xbar = (a + adag) / np.sqrt(2.0)
    h = number + 0.5 * np.eye(dimension) + quartic_strength * np.linalg.matrix_power(xbar, 4)
    return 0.5 * (h + h.T)


def anharmonic_spectrum(dimension: int, quartic_strength: float, levels: int = 4) -> np.ndarray:
    if levels < 1 or levels > dimension:
        raise ValueError("levels must satisfy 1 <= levels <= dimension")
    values, _ = hermitian_eigensystem(
        anharmonic_oscillator_hamiltonian(dimension, quartic_strength)
    )
    return values[:levels]


def anharmonic_convergence(
    dimensions: Iterable[int], quartic_strength: float, *, levels: int = 4, reference_dimension: int = 80
) -> tuple[np.ndarray, np.ndarray]:
    dims = np.asarray(list(dimensions), dtype=int)
    if np.any(dims < levels):
        raise ValueError("all dimensions must be at least the number of requested levels")
    reference = anharmonic_spectrum(reference_dimension, quartic_strength, levels)
    errors = []
    for n in dims:
        values = anharmonic_spectrum(int(n), quartic_strength, levels)
        errors.append(float(np.max(np.abs(values - reference))))
    return dims, np.asarray(errors)


def flux_ring_energies(
    reduced_flux: np.ndarray | float, quantum_numbers: Iterable[int]
) -> np.ndarray:
    """E_n/E0=(n-phi)^2 for a particle on a ring threaded by flux phi=Phi/Phi0."""
    phi = np.asarray(reduced_flux, dtype=float)
    n = np.asarray(list(quantum_numbers), dtype=float)
    return (phi[..., None] - n[None, ...] if phi.ndim else phi - n) ** 2


def flux_ring_ground_state_energy(reduced_flux: np.ndarray | float, nmax: int = 8) -> np.ndarray:
    if nmax < 1:
        raise ValueError("nmax must be positive")
    n = np.arange(-nmax, nmax + 1)
    energies = flux_ring_energies(reduced_flux, n)
    return np.min(energies, axis=-1)


def flux_ring_ground_state_current(reduced_flux: np.ndarray | float, nmax: int = 8) -> np.ndarray:
    """Dimensionless persistent current -d(E/E0)/dphi for the selected branch."""
    phi = np.asarray(reduced_flux, dtype=float)
    n = np.arange(-nmax, nmax + 1)
    energies = flux_ring_energies(phi, n)
    index = np.argmin(energies, axis=-1)
    selected_n = n[index]
    return 2.0 * (selected_n - phi)


def three_level_hamiltonian(
    high_energy_gap: float,
    *,
    low_coupling: float = 0.15,
    low_detuning: float = 0.20,
    v1: float = 0.40,
    v2: float = 0.30,
) -> np.ndarray:
    if high_energy_gap <= 0:
        raise ValueError("high_energy_gap must be positive")
    return np.array(
        [
            [0.0, low_coupling, v1],
            [low_coupling, low_detuning, v2],
            [v1, v2, high_energy_gap],
        ],
        dtype=float,
    )


def effective_two_level_hamiltonian(
    high_energy_gap: float,
    *,
    low_coupling: float = 0.15,
    low_detuning: float = 0.20,
    v1: float = 0.40,
    v2: float = 0.30,
) -> np.ndarray:
    """Leading down-folded low-energy Hamiltonian A - B B^T/Delta."""
    if high_energy_gap <= 0:
        raise ValueError("high_energy_gap must be positive")
    a = np.array([[0.0, low_coupling], [low_coupling, low_detuning]], dtype=float)
    b = np.array([[v1], [v2]], dtype=float)
    return a - (b @ b.T) / high_energy_gap


def effective_model_error(high_energy_gap: float, **kwargs: float) -> float:
    exact, _ = hermitian_eigensystem(three_level_hamiltonian(high_energy_gap, **kwargs))
    effective, _ = hermitian_eigensystem(effective_two_level_hamiltonian(high_energy_gap, **kwargs))
    return float(np.max(np.abs(exact[:2] - effective)))


def effective_error_sweep(gaps: Iterable[float], **kwargs: float) -> tuple[np.ndarray, np.ndarray]:
    delta = np.asarray(list(gaps), dtype=float)
    if np.any(delta <= 0):
        raise ValueError("all gaps must be positive")
    errors = np.asarray([effective_model_error(float(d), **kwargs) for d in delta])
    return delta, errors
