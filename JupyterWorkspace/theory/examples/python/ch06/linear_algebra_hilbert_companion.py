"""Chapter 6 computational companion.

Run from the repository root with:
    python examples/python/ch06/linear_algebra_hilbert_companion.py

Requires NumPy; Matplotlib is optional and used only for the Bloch-sphere preview.
"""
from __future__ import annotations

import numpy as np


def null_space(a: np.ndarray, rtol: float = 1e-12) -> np.ndarray:
    """Return an orthonormal basis for the numerical null space of ``a``."""
    _, s, vh = np.linalg.svd(a)
    tol = rtol * (s[0] if s.size else 1.0)
    rank = int(np.sum(s > tol))
    return vh[rank:].conj().T


def modified_gram_schmidt(a: np.ndarray, tol: float = 1e-12) -> tuple[np.ndarray, np.ndarray]:
    """Reduced QR factorization using modified Gram--Schmidt."""
    a = np.asarray(a, dtype=complex)
    m, n = a.shape
    q = np.zeros((m, n), dtype=complex)
    r = np.zeros((n, n), dtype=complex)
    v = a.copy()
    for i in range(n):
        r[i, i] = np.linalg.norm(v[:, i])
        if abs(r[i, i]) < tol:
            raise np.linalg.LinAlgError("Columns are linearly dependent to working precision")
        q[:, i] = v[:, i] / r[i, i]
        for j in range(i + 1, n):
            r[i, j] = np.vdot(q[:, i], v[:, j])
            v[:, j] -= r[i, j] * q[:, i]
    return q, r


def spectral_projectors(a: np.ndarray) -> list[tuple[complex, np.ndarray]]:
    """Return eigenvalues and rank-one projectors for a Hermitian matrix."""
    values, vectors = np.linalg.eigh(a)
    return [(value, np.outer(vectors[:, k], vectors[:, k].conj())) for k, value in enumerate(values)]


def matrix_exponential_hermitian(h: np.ndarray, t: float, hbar: float = 1.0) -> np.ndarray:
    """Compute exp(-i H t / hbar) by Hermitian spectral decomposition."""
    values, vectors = np.linalg.eigh(h)
    phases = np.exp(-1j * values * t / hbar)
    return vectors @ np.diag(phases) @ vectors.conj().T


def bloch_vector(state: np.ndarray) -> np.ndarray:
    """Return the Bloch vector of a normalized two-level pure state."""
    state = np.asarray(state, dtype=complex)
    state = state / np.linalg.norm(state)
    sx = np.array([[0, 1], [1, 0]], dtype=complex)
    sy = np.array([[0, -1j], [1j, 0]], dtype=complex)
    sz = np.array([[1, 0], [0, -1]], dtype=complex)
    return np.array([np.vdot(state, op @ state).real for op in (sx, sy, sz)])


def fourier_reconstruction(samples: np.ndarray, keep: int) -> np.ndarray:
    """Truncate a discrete Fourier expansion to ``keep`` modes on each side."""
    coeff = np.fft.fft(samples)
    shifted = np.fft.fftshift(coeff)
    center = shifted.size // 2
    mask = np.zeros_like(shifted)
    lo = max(0, center - keep)
    hi = min(shifted.size, center + keep + 1)
    mask[lo:hi] = shifted[lo:hi]
    return np.fft.ifft(np.fft.ifftshift(mask)).real


def main() -> None:
    a = np.array([[1.0, 2.0, 3.0], [2.0, 4.0, 6.0]])
    print("rank(A) =", np.linalg.matrix_rank(a))
    print("null-space basis =\n", null_space(a))

    b = np.array([[1.0, 1.0], [1.0, 0.0], [0.0, 1.0]])
    q, r = modified_gram_schmidt(b)
    print("\n||Q*Q-I|| =", np.linalg.norm(q.conj().T @ q - np.eye(2)))
    print("||QR-B|| =", np.linalg.norm(q @ r - b))

    h = np.array([[2.0, 1.0 - 1j], [1.0 + 1j, 3.0]], dtype=complex)
    print("\nHermitian:", np.allclose(h, h.conj().T))
    for value, projector in spectral_projectors(h):
        print("eigenvalue:", value, "projector error:", np.linalg.norm(projector @ projector - projector))

    u = matrix_exponential_hermitian(h, t=0.4)
    print("unitarity error:", np.linalg.norm(u.conj().T @ u - np.eye(2)))

    plus = np.array([1.0, 1.0], dtype=complex) / np.sqrt(2)
    print("Bloch vector of |+>:", bloch_vector(plus))

    x = np.linspace(-np.pi, np.pi, 512, endpoint=False)
    square_wave = np.sign(np.sin(x))
    approximation = fourier_reconstruction(square_wave, keep=12)
    error = np.linalg.norm(square_wave - approximation) / np.sqrt(square_wave.size)
    print("truncated Fourier RMS error:", error)


if __name__ == "__main__":
    main()
