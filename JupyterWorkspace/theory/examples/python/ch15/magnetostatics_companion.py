"""Executable magnetostatics companion for Chapter 15.

The functions are intentionally small and auditable.  SI units are used unless
an argument explicitly represents a normalized coordinate.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Callable

import numpy as np

MU0 = 4.0e-7 * math.pi


def loop_axis_field(z: np.ndarray | float, radius: float, current: float = 1.0) -> np.ndarray:
    """Axial B field of one circular loop centered at z=0."""
    z_arr = np.asarray(z, dtype=float)
    if radius <= 0:
        raise ValueError("radius must be positive")
    return MU0 * current * radius**2 / (2.0 * (radius**2 + z_arr**2) ** 1.5)


def dipole_axis_field(z: np.ndarray | float, moment: float) -> np.ndarray:
    """Axial field of a point magnetic dipole for nonzero z."""
    z_arr = np.asarray(z, dtype=float)
    if np.any(z_arr == 0):
        raise ValueError("dipole field is singular at z=0")
    return MU0 * moment / (2.0 * math.pi * z_arr**3)


def solenoid_axis_field(
    z: np.ndarray | float,
    radius: float,
    length: float,
    turns: int,
    current: float = 1.0,
) -> np.ndarray:
    """Finite-solenoid axial field from the exact sheet-current expression."""
    if radius <= 0 or length <= 0 or turns <= 0:
        raise ValueError("radius, length, and turns must be positive")
    z_arr = np.asarray(z, dtype=float)
    n = turns / length
    zp = z_arr + 0.5 * length
    zm = z_arr - 0.5 * length
    return 0.5 * MU0 * n * current * (
        zp / np.sqrt(radius**2 + zp**2)
        - zm / np.sqrt(radius**2 + zm**2)
    )


def symmetric_gauge(x: np.ndarray, y: np.ndarray, field: float) -> tuple[np.ndarray, np.ndarray]:
    """A=(-By/2, Bx/2, 0) for uniform B along +z."""
    return -0.5 * field * y, 0.5 * field * x


def landau_gauge(x: np.ndarray, y: np.ndarray, field: float) -> tuple[np.ndarray, np.ndarray]:
    """A=(0, Bx, 0) for uniform B along +z."""
    return np.zeros_like(x, dtype=float), field * x


def curl_z(ax: np.ndarray, ay: np.ndarray, spacing: float) -> np.ndarray:
    """Centered numerical z-curl dAy/dx-dAx/dy on a uniform square grid."""
    day_dx = np.gradient(ay, spacing, axis=1, edge_order=2)
    dax_dy = np.gradient(ax, spacing, axis=0, edge_order=2)
    return day_dx - dax_dy


def apparent_susceptibility(chi_intrinsic: np.ndarray | float, demag_factor: float) -> np.ndarray:
    """Ellipsoidal apparent susceptibility chi/(1+N chi)."""
    chi = np.asarray(chi_intrinsic, dtype=float)
    if not 0.0 <= demag_factor <= 1.0:
        raise ValueError("demagnetizing factor must lie in [0,1]")
    return chi / (1.0 + demag_factor * chi)


def hysteresis_branches(
    field: np.ndarray,
    saturation: float = 1.2,
    coercive: float = 80.0,
    scale: float = 55.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Simple saturating branch surrogate B_up(H), B_down(H).

    This is a numerical teaching model, not a universal material law.
    """
    h = np.asarray(field, dtype=float)
    b_up = saturation * np.tanh((h - coercive) / scale) + MU0 * h
    b_down = saturation * np.tanh((h + coercive) / scale) + MU0 * h
    return b_up, b_down


def hysteresis_loop_area(field_max: float = 500.0, points: int = 4001) -> float:
    """Return positive area integral |oint H dB| for the surrogate loop."""
    h_up = np.linspace(-field_max, field_max, points)
    h_down = np.linspace(field_max, -field_max, points)
    b_up, _ = hysteresis_branches(h_up)
    _, b_down = hysteresis_branches(h_down)
    h = np.concatenate([h_up, h_down[1:]])
    b = np.concatenate([b_up, b_down[1:]])
    return float(abs(np.trapezoid(h, b)))


def gapped_core_flux_density(
    current: np.ndarray | float,
    turns: int,
    core_length: float,
    relative_permeability: float,
    gap: np.ndarray | float,
) -> np.ndarray:
    """Uniform-flux magnetic-circuit approximation for a gapped core."""
    if turns <= 0 or core_length <= 0 or relative_permeability <= 0:
        raise ValueError("turns, core length, and permeability must be positive")
    i = np.asarray(current, dtype=float)
    g = np.asarray(gap, dtype=float)
    if np.any(g < 0):
        raise ValueError("gap cannot be negative")
    return MU0 * turns * i / (g + core_length / relative_permeability)


@dataclass(frozen=True)
class SORResult:
    potential: np.ndarray
    residual_history: np.ndarray
    iterations: int
    spacing: float


def poisson_residual(u: np.ndarray, source: np.ndarray, spacing: float) -> np.ndarray:
    """Interior residual of laplacian(u)-source=0."""
    r = np.zeros_like(u)
    r[1:-1, 1:-1] = (
        u[2:, 1:-1] + u[:-2, 1:-1] + u[1:-1, 2:] + u[1:-1, :-2]
        - 4.0 * u[1:-1, 1:-1]
    ) / spacing**2 - source[1:-1, 1:-1]
    return r


def solve_poisson_dirichlet(
    source: np.ndarray,
    boundary: np.ndarray | None = None,
    omega: float = 1.85,
    tolerance: float = 2e-8,
    max_iterations: int = 30000,
) -> SORResult:
    """Red-black SOR for laplacian(u)=source on the unit square."""
    if source.ndim != 2 or source.shape[0] != source.shape[1] or source.shape[0] < 5:
        raise ValueError("source must be a square array of size at least 5")
    n = source.shape[0]
    h = 1.0 / (n - 1)
    u = np.zeros_like(source, dtype=float)
    if boundary is not None:
        if boundary.shape != source.shape:
            raise ValueError("boundary and source shapes must agree")
        u[0, :] = boundary[0, :]
        u[-1, :] = boundary[-1, :]
        u[:, 0] = boundary[:, 0]
        u[:, -1] = boundary[:, -1]
    history: list[float] = []
    h2 = h * h
    ii, jj = np.indices((n - 2, n - 2))
    for it in range(1, max_iterations + 1):
        for parity in (0, 1):
            old = u[1:-1, 1:-1]
            candidate = 0.25 * (
                u[2:, 1:-1] + u[:-2, 1:-1] + u[1:-1, 2:] + u[1:-1, :-2]
                - h2 * source[1:-1, 1:-1]
            )
            mask = ((ii + jj) & 1) == parity
            old[mask] = (1.0 - omega) * old[mask] + omega * candidate[mask]
        if it == 1 or it % 20 == 0:
            residual = poisson_residual(u, source, h)
            norm = float(np.max(np.abs(residual[1:-1, 1:-1])))
            history.append(norm)
            if norm < tolerance:
                return SORResult(u, np.asarray(history), it, h)
    return SORResult(u, np.asarray(history), max_iterations, h)


def manufactured_solution(n: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Exact u=sin(pi x)sin(pi y) and source laplacian(u)."""
    x = np.linspace(0.0, 1.0, n)
    xx, yy = np.meshgrid(x, x)
    exact = np.sin(math.pi * xx) * np.sin(math.pi * yy)
    source = -2.0 * math.pi**2 * exact
    return exact, source, x


def max_error(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.max(np.abs(np.asarray(a) - np.asarray(b))))
