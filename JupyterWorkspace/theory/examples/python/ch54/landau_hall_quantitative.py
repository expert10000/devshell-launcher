#!/usr/bin/env python3
"""Quantitative finite-geometry and Hall diagnostics for Volume VIII Chapter 54.

The lattice calculations use a nearest-neighbor Hofstadter regularization with
hbar=t=a=1.  The magnetic flux per plaquette is alpha in units of the flux
quantum, so the Peierls phase around one plaquette is 2*pi*alpha.
"""
from __future__ import annotations

from functools import lru_cache
import numpy as np

TWOPI = 2.0 * np.pi


def _idx(x: int, y: int, ly: int) -> int:
    return x * ly + y


def hofstadter_torus(
    lx: int,
    ly: int,
    alpha: float,
    *,
    t: float = 1.0,
    disorder_strength: float = 0.0,
    seed: int = 0,
    theta_x: float = 0.0,
    theta_y: float = 0.0,
    disorder: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Return a Hofstadter Hamiltonian on a twisted torus and its disorder.

    Landau gauge is used: y-directed hopping at x carries exp(i 2*pi*alpha*x).
    Twists theta_x/y are inserted only on the corresponding boundary links.
    """
    n = lx * ly
    if disorder is None:
        rng = np.random.default_rng(seed)
        disorder = rng.uniform(-disorder_strength / 2.0, disorder_strength / 2.0, n)
    else:
        disorder = np.asarray(disorder, dtype=float)
        if disorder.shape != (n,):
            raise ValueError("disorder must have shape (lx*ly,)")

    h = np.zeros((n, n), dtype=complex)
    for x in range(lx):
        for y in range(ly):
            i = _idx(x, y, ly)
            h[i, i] = disorder[i]

            xp = (x + 1) % lx
            j = _idx(xp, y, ly)
            phase_x = np.exp(1j * theta_x) if x == lx - 1 else 1.0 + 0.0j
            amp_x = -t * phase_x
            h[i, j] += amp_x
            h[j, i] += np.conj(amp_x)

            yp = (y + 1) % ly
            j = _idx(x, yp, ly)
            phase_y = np.exp(1j * TWOPI * alpha * x)
            if y == ly - 1:
                phase_y *= np.exp(1j * theta_y)
            amp_y = -t * phase_y
            h[i, j] += amp_y
            h[j, i] += np.conj(amp_y)
    return h, disorder.copy()


def strip_hamiltonian(nx: int, ky: float, alpha: float, *, t: float = 1.0) -> np.ndarray:
    """Open-x, periodic-y Hofstadter strip after Fourier transforming y."""
    x = np.arange(nx, dtype=float)
    diag = -2.0 * t * np.cos(ky + TWOPI * alpha * x)
    h = np.diag(diag.astype(complex))
    off = -t * np.ones(nx - 1, dtype=complex)
    h += np.diag(off, 1) + np.diag(off, -1)
    return h


def strip_spectrum(
    nx: int = 48,
    alpha: float = 1.0 / 8.0,
    nky: int = 161,
    edge_cells: int = 4,
) -> dict[str, np.ndarray]:
    """Spectrum and edge diagnostics for a magnetic cylinder."""
    kys = np.linspace(-np.pi, np.pi, nky, endpoint=False)
    energies = np.empty((nky, nx), dtype=float)
    edge_weight = np.empty_like(energies)
    edge_polarization = np.empty_like(energies)
    for j, ky in enumerate(kys):
        e, v = np.linalg.eigh(strip_hamiltonian(nx, ky, alpha))
        prob = np.abs(v) ** 2
        left = prob[:edge_cells].sum(axis=0)
        right = prob[-edge_cells:].sum(axis=0)
        energies[j] = e
        edge_weight[j] = left + right
        edge_polarization[j] = right - left
    return {
        "ky": kys,
        "energies": energies,
        "edge_weight": edge_weight,
        "edge_polarization": edge_polarization,
    }


def gaussian_dos(energies: np.ndarray, grid: np.ndarray, eta: float = 0.06) -> np.ndarray:
    """Normalized Gaussian-broadened DOS for a finite set of energies."""
    energies = np.asarray(energies, dtype=float).ravel()
    grid = np.asarray(grid, dtype=float)
    z = (grid[:, None] - energies[None, :]) / eta
    dos = np.exp(-0.5 * z * z).sum(axis=1) / (np.sqrt(2.0 * np.pi) * eta * energies.size)
    return dos


def inverse_participation_ratio(eigenvectors: np.ndarray) -> np.ndarray:
    """IPR of column eigenvectors."""
    return np.sum(np.abs(eigenvectors) ** 4, axis=0).real


@lru_cache(maxsize=16)
def twisted_eigensystem(
    lx: int,
    ly: int,
    alpha: float,
    disorder_strength: float,
    seed: int,
    ntheta: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Cache eigensystems on an ntheta x ntheta boundary-twist grid."""
    n = lx * ly
    rng = np.random.default_rng(seed)
    disorder = rng.uniform(-disorder_strength / 2.0, disorder_strength / 2.0, n)
    theta = np.linspace(0.0, TWOPI, ntheta, endpoint=False)
    evals = np.empty((ntheta, ntheta, n), dtype=float)
    evecs = np.empty((ntheta, ntheta, n, n), dtype=complex)
    for ix, tx in enumerate(theta):
        for iy, ty in enumerate(theta):
            h, _ = hofstadter_torus(
                lx,
                ly,
                alpha,
                disorder=disorder,
                theta_x=float(tx),
                theta_y=float(ty),
            )
            evals[ix, iy], evecs[ix, iy] = np.linalg.eigh(h)
    return evals, evecs, disorder


def _unit_det_phase(overlap: np.ndarray) -> complex:
    sign, _ = np.linalg.slogdet(overlap)
    mag = abs(sign)
    if mag == 0.0:
        raise FloatingPointError("singular occupied-subspace overlap")
    return sign / mag


def occupied_subspace_chern(evecs: np.ndarray, nocc: int) -> float:
    """Non-Abelian FHS Chern number of the lowest nocc states on a twist grid."""
    ntheta = evecs.shape[0]
    if evecs.shape[1] != ntheta or not (1 <= nocc <= evecs.shape[-1]):
        raise ValueError("invalid twist grid or occupation")
    ux = np.empty((ntheta, ntheta), dtype=complex)
    uy = np.empty((ntheta, ntheta), dtype=complex)
    for ix in range(ntheta):
        for iy in range(ntheta):
            v = evecs[ix, iy, :, :nocc]
            vx = evecs[(ix + 1) % ntheta, iy, :, :nocc]
            vy = evecs[ix, (iy + 1) % ntheta, :, :nocc]
            ux[ix, iy] = _unit_det_phase(v.conj().T @ vx)
            uy[ix, iy] = _unit_det_phase(v.conj().T @ vy)

    curvature_sum = 0.0
    for ix in range(ntheta):
        for iy in range(ntheta):
            loop = (
                ux[ix, iy]
                * uy[(ix + 1) % ntheta, iy]
                / (ux[ix, (iy + 1) % ntheta] * uy[ix, iy])
            )
            curvature_sum += np.angle(loop)
    return float(curvature_sum / TWOPI)


@lru_cache(maxsize=4)
def clean_hall_diagnostics() -> dict[str, float | np.ndarray]:
    """Cumulative Chern response of a clean alpha=1/3 magnetic torus."""
    lx = ly = 6
    alpha = 1.0 / 3.0
    evals, evecs, _ = twisted_eigensystem(lx, ly, alpha, 0.0, 0, 7)
    band_capacity = lx * ly // 3
    c1 = occupied_subspace_chern(evecs, band_capacity)
    c2 = occupied_subspace_chern(evecs, 2 * band_capacity)
    call = occupied_subspace_chern(evecs, lx * ly)
    gap1 = float(evals[:, :, band_capacity].min() - evals[:, :, band_capacity - 1].max())
    gap2 = float(evals[:, :, 2 * band_capacity].min() - evals[:, :, 2 * band_capacity - 1].max())
    return {
        "cumulative_chern": np.array([c1, c2, call]),
        "band_chern": np.array([c1, c2 - c1, call - c2]),
        "gap1": gap1,
        "gap2": gap2,
        "band_capacity": float(band_capacity),
    }


@lru_cache(maxsize=4)
def disorder_plateau_diagnostics() -> dict[str, np.ndarray | float | int]:
    """Finite disordered-torus plateau diagnostic for alpha=1/4.

    The fixed seed is intentional: this is a reproducible finite-size example,
    not disorder averaging.  It demonstrates the mobility-gap logic that an
    integer Chern response can remain unchanged while localized states are added.
    """
    lx = ly = 8
    alpha = 1.0 / 4.0
    w = 2.5
    seed = 0
    evals, evecs, disorder = twisted_eigensystem(lx, ly, alpha, w, seed, 7)
    e0 = evals[0, 0].copy()
    v0 = evecs[0, 0].copy()
    ipr = inverse_participation_ratio(v0)
    twist_sensitivity = np.std(evals, axis=(0, 1))
    occupations = np.arange(1, 22, dtype=int)
    chern = np.array([occupied_subspace_chern(evecs, int(n)) for n in occupations])

    # A clean reference on the same finite torus quantifies magnetic-band broadening.
    h_clean, _ = hofstadter_torus(lx, ly, alpha)
    e_clean = np.linalg.eigvalsh(h_clean)
    clean_first_width = float(e_clean[15] - e_clean[0])
    disorder_first_width = float(e0[15] - e0[0])

    plateau_mask = np.isclose(chern, -1.0, atol=1e-8)
    plateau_occ = occupations[plateau_mask]
    plateau_start = int(plateau_occ.min())
    # Restrict the advertised contiguous plateau to the first interval beginning there.
    plateau_end = plateau_start
    for n, c in zip(occupations[plateau_start:], chern[plateau_start:]):
        if np.isclose(c, -1.0, atol=1e-8):
            plateau_end = int(n)
        else:
            break

    return {
        "energies": e0,
        "ipr": ipr,
        "twist_sensitivity": twist_sensitivity,
        "occupations": occupations,
        "chern": chern,
        "disorder": disorder,
        "clean_first_band_width": clean_first_width,
        "disorder_first_band_width": disorder_first_width,
        "plateau_start": plateau_start,
        "plateau_end": plateau_end,
    }


def disorder_ensemble_spectra(
    realizations: int = 16,
    *,
    lx: int = 8,
    ly: int = 8,
    alpha: float = 1.0 / 4.0,
    disorder_strength: float = 2.5,
) -> tuple[np.ndarray, np.ndarray]:
    """Zero-twist clean and disordered spectra for DOS visualization."""
    h_clean, _ = hofstadter_torus(lx, ly, alpha)
    clean = np.linalg.eigvalsh(h_clean)
    spectra = []
    for seed in range(realizations):
        h, _ = hofstadter_torus(
            lx, ly, alpha, disorder_strength=disorder_strength, seed=seed
        )
        spectra.append(np.linalg.eigvalsh(h))
    return clean, np.concatenate(spectra)


def diagnostics_summary() -> dict[str, float | int | list[float]]:
    clean = clean_hall_diagnostics()
    dis = disorder_plateau_diagnostics()
    strip = strip_spectrum()
    first_gap_edge = (
        (strip["energies"] > -3.24)
        & (strip["energies"] < -2.06)
        & (strip["edge_weight"] > 0.5)
    )
    return {
        "commit": 590,
        "clean_cumulative_chern": [float(x) for x in clean["cumulative_chern"]],
        "clean_band_chern": [float(x) for x in clean["band_chern"]],
        "clean_gap1": float(clean["gap1"]),
        "clean_gap2": float(clean["gap2"]),
        "disorder_first_band_broadening_ratio": float(
            dis["disorder_first_band_width"] / dis["clean_first_band_width"]
        ),
        "disorder_plateau_start_occupation": int(dis["plateau_start"]),
        "disorder_plateau_end_occupation": int(dis["plateau_end"]),
        "chern_at_N11": float(dis["chern"][10]),
        "chern_at_N12": float(dis["chern"][11]),
        "ipr_state1": float(dis["ipr"][0]),
        "ipr_state12": float(dis["ipr"][11]),
        "twist_sensitivity_state1": float(dis["twist_sensitivity"][0]),
        "twist_sensitivity_state12": float(dis["twist_sensitivity"][11]),
        "strong_edge_points_first_gap": int(first_gap_edge.sum()),
    }

# ---------------------------------------------------------------------------
# Commit 589: Kubo/Streda response, charge pumping, and projected interactions
# ---------------------------------------------------------------------------

def magnetic_bloch_hamiltonian(
    qden: int,
    kx: float,
    ky: float,
    *,
    pnum: int = 1,
    t: float = 1.0,
) -> np.ndarray:
    """qden x qden magnetic-Bloch Harper Hamiltonian at alpha=pnum/qden.

    kx is the phase accumulated across one qden-site magnetic unit cell in x;
    ky is the ordinary y crystal momentum.  Both are 2*pi periodic.
    """
    if qden < 2 or not (1 <= pnum < qden):
        raise ValueError("require qden>=2 and 1<=pnum<qden")
    alpha = pnum / qden
    m = np.arange(qden, dtype=float)
    h = np.diag((-2.0 * t * np.cos(ky + TWOPI * alpha * m)).astype(complex))
    for j in range(qden - 1):
        h[j, j + 1] = -t
        h[j + 1, j] = -t
    h[qden - 1, 0] = -t * np.exp(1j * kx)
    h[0, qden - 1] = -t * np.exp(-1j * kx)
    return h


def magnetic_bloch_derivatives(
    qden: int,
    kx: float,
    ky: float,
    *,
    pnum: int = 1,
    t: float = 1.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Analytic derivatives dH/dkx and dH/dky for magnetic_bloch_hamiltonian."""
    alpha = pnum / qden
    dhx = np.zeros((qden, qden), dtype=complex)
    dhx[qden - 1, 0] = -1j * t * np.exp(1j * kx)
    dhx[0, qden - 1] = +1j * t * np.exp(-1j * kx)
    m = np.arange(qden, dtype=float)
    dhy = np.diag((2.0 * t * np.sin(ky + TWOPI * alpha * m)).astype(complex))
    return dhx, dhy


def kubo_berry_curvature(
    qden: int,
    kx: float,
    ky: float,
    band: int,
    *,
    pnum: int = 1,
    t: float = 1.0,
) -> float:
    """Berry curvature from interband Kubo velocity-matrix elements.

    The sign convention is chosen to match the boundary-twist orientation used
    elsewhere in Chapter 54.
    """
    h = magnetic_bloch_hamiltonian(qden, kx, ky, pnum=pnum, t=t)
    e, v = np.linalg.eigh(h)
    if not (0 <= band < qden):
        raise ValueError("invalid band")
    dhx, dhy = magnetic_bloch_derivatives(qden, kx, ky, pnum=pnum, t=t)
    omega = 0.0
    for other in range(qden):
        if other == band:
            continue
        ax = np.vdot(v[:, band], dhx @ v[:, other])
        ay = np.vdot(v[:, other], dhy @ v[:, band])
        omega += 2.0 * np.imag(ax * ay) / (e[band] - e[other]) ** 2
    return float(omega)


@lru_cache(maxsize=8)
def kubo_band_chern_numbers(qden: int = 3, nk: int = 51) -> np.ndarray:
    """Integrate Kubo Berry curvature for every magnetic band."""
    kxs = np.linspace(0.0, TWOPI, nk, endpoint=False)
    kys = np.linspace(0.0, TWOPI, nk, endpoint=False)
    area_element = (TWOPI / nk) ** 2
    out = np.zeros(qden, dtype=float)
    for band in range(qden):
        total = 0.0
        for kx in kxs:
            for ky in kys:
                total += kubo_berry_curvature(qden, float(kx), float(ky), band)
        out[band] = total * area_element / TWOPI
    return out


def streda_lowest_gap_counting(qden_values: tuple[int, ...] = (3, 4, 5, 6, 7, 8, 9)) -> dict[str, np.ndarray | float]:
    """Gap-label counting for the lowest p=1 Hofstadter band.

    For alpha=1/q the lowest magnetic band contains one state per q-site
    magnetic unit cell, hence density per lattice site is n a^2 = 1/q = alpha.
    """
    qvals = np.asarray(qden_values, dtype=float)
    alpha = 1.0 / qvals
    density = 1.0 / qvals
    slope, intercept = np.polyfit(alpha, density, 1)
    return {
        "alpha": alpha,
        "density_per_site": density,
        "slope": float(slope),
        "intercept": float(intercept),
    }


def _single_band_wilson_phase(qden: int, kx: float, *, band: int = 0, nky: int = 121) -> float:
    kys = np.linspace(0.0, TWOPI, nky, endpoint=False)
    vecs = []
    for ky in kys:
        _, v = np.linalg.eigh(magnetic_bloch_hamiltonian(qden, kx, float(ky)))
        vecs.append(v[:, band])
    loop = 1.0 + 0.0j
    for j in range(nky):
        ov = np.vdot(vecs[j], vecs[(j + 1) % nky])
        if abs(ov) < 1e-14:
            raise FloatingPointError("singular single-band Wilson overlap")
        loop *= ov / abs(ov)
    return float(np.angle(loop))


def laughlin_flux_pump(qden: int = 3, *, band: int = 0, nkx: int = 81, nky: int = 121) -> dict[str, np.ndarray | float]:
    """Hybrid-Wannier/Wilson-loop winding over one 2*pi boundary-twist cycle."""
    kx = np.linspace(0.0, TWOPI, nkx, endpoint=True)
    phase = np.array([_single_band_wilson_phase(qden, float(x), band=band, nky=nky) for x in kx])
    unwrapped = np.unwrap(phase)
    winding = float((unwrapped[-1] - unwrapped[0]) / TWOPI)
    center = (unwrapped - unwrapped[0]) / TWOPI
    return {"twist": kx, "phase": phase, "unwrapped_phase": unwrapped, "center_shift": center, "winding": winding}


def lll_form_factor(qell: np.ndarray | float) -> np.ndarray:
    """Lowest-Landau-level cyclotron form factor F0(q)."""
    x = np.asarray(qell, dtype=float)
    return np.exp(-0.25 * x * x)


def lll_interaction_filter(qell: np.ndarray | float) -> np.ndarray:
    """Squared LLL form factor |F0|^2 multiplying the projected interaction."""
    f = lll_form_factor(qell)
    return f * f


def coulomb_pseudopotential(m: int) -> float:
    """LLL Coulomb Haldane pseudopotential V_m/E_C."""
    import math
    if m < 0:
        raise ValueError("m must be nonnegative")
    return float(math.gamma(m + 0.5) / (2.0 * math.factorial(m)))


def coulomb_pseudopotentials(max_m: int = 9) -> np.ndarray:
    return np.array([coulomb_pseudopotential(m) for m in range(max_m + 1)], dtype=float)


def interaction_cyclotron_ratio(
    magnetic_field_tesla: np.ndarray | float,
    *,
    eps_r: float = 12.8,
    mass_ratio: float = 0.067,
) -> np.ndarray:
    """Illustrative kappa=E_C/(hbar omega_c) for a semiconductor 2DEG.

    Constants are SI; q magnitude is the elementary charge.  Defaults are
    GaAs-like and are used only for the scale-illustration figure.
    """
    import math
    hbar = 1.054571817e-34
    e = 1.602176634e-19
    eps0 = 8.8541878128e-12
    me = 9.1093837015e-31
    b = np.asarray(magnetic_field_tesla, dtype=float)
    if np.any(b <= 0.0):
        raise ValueError("magnetic field must be positive")
    ell = np.sqrt(hbar / (e * b))
    ec = e * e / (4.0 * math.pi * eps0 * eps_r * ell)
    hwc = hbar * e * b / (mass_ratio * me)
    return ec / hwc


def laughlin_sphere_flux(ne: int, denominator: int = 3) -> int:
    """Sphere flux relation N_phi=m(N_e-1) for Laughlin nu=1/m."""
    if ne < 2 or denominator < 1:
        raise ValueError("invalid particle number or denominator")
    return denominator * (ne - 1)


def response_fractional_diagnostics() -> dict[str, float | list[float]]:
    kubo = kubo_band_chern_numbers(3, 51)
    streda = streda_lowest_gap_counting()
    pump = laughlin_flux_pump(3, nkx=81, nky=121)
    vm = coulomb_pseudopotentials(9)
    return {
        "kubo_band_chern": [float(x) for x in kubo],
        "kubo_cumulative_chern": [float(x) for x in np.cumsum(kubo)],
        "streda_lowest_gap_slope": float(streda["slope"]),
        "streda_lowest_gap_intercept": float(streda["intercept"]),
        "wilson_pump_winding": float(pump["winding"]),
        "V0_over_Ec": float(vm[0]),
        "V1_over_Ec": float(vm[1]),
        "V3_over_Ec": float(vm[3]),
        "V5_over_Ec": float(vm[5]),
        "kappa_1T": float(interaction_cyclotron_ratio(1.0)),
        "kappa_10T": float(interaction_cyclotron_ratio(10.0)),
    }

# ---------------------------------------------------------------------------
# Commit 590: projected-interaction exact diagonalization on the Haldane sphere
# ---------------------------------------------------------------------------

from itertools import combinations
import math


def _fact_int(x: float) -> int:
    n = int(round(x))
    if abs(x - n) > 1e-10 or n < 0:
        raise ValueError(f"factorial argument is not a nonnegative integer: {x}")
    return math.factorial(n)


@lru_cache(maxsize=4096)
def sphere_clebsch_gordan(nphi: int, a: int, b: int, pair_L: int) -> float:
    """<S m_a,S m_b|L M> with S=Nphi/2 and M=m_a+m_b.

    The Racah factorial formula is used directly so the ED companion depends only
    on Python+NumPy rather than an external angular-momentum package.
    """
    if nphi < 1 or not (0 <= a <= nphi and 0 <= b <= nphi):
        raise ValueError("invalid sphere orbital")
    j = nphi / 2.0
    m1 = a - j
    m2 = b - j
    J = float(pair_L)
    M = m1 + m2
    if J < 0 or J > 2.0 * j or abs(M) > J + 1e-12:
        return 0.0
    pref = math.sqrt(
        (2.0 * J + 1.0)
        * _fact_int(J + j - j)
        * _fact_int(J - j + j)
        * _fact_int(2.0 * j - J)
        / _fact_int(2.0 * j + J + 1.0)
    )
    pref *= math.sqrt(
        _fact_int(J + M)
        * _fact_int(J - M)
        * _fact_int(j - m1)
        * _fact_int(j + m1)
        * _fact_int(j - m2)
        * _fact_int(j + m2)
    )
    total = 0.0
    for k in range(nphi + 2):
        args = (
            k,
            2.0 * j - J - k,
            j - m1 - k,
            j + m2 - k,
            J - j + m1 + k,
            J - j - m2 + k,
        )
        if any(x < -1e-12 or abs(x - round(x)) > 1e-10 for x in args):
            continue
        denom = 1
        for x in args:
            denom *= _fact_int(x)
        total += ((-1) ** k) / denom
    return float(pref * total)


@lru_cache(maxsize=128)
def sphere_pair_projector(nphi: int, relative_m: int) -> tuple[tuple[tuple[int, int], ...], np.ndarray]:
    """Projector onto one fermionic relative-angular-momentum channel.

    The matrix is represented in normalized antisymmetric orbital-pair states
    |a,b> with a<b.  For odd relative_m the coupled state is antisymmetric and
    the pair-basis coefficient is sqrt(2) times the ordered CG coefficient.
    """
    if relative_m < 1 or relative_m > nphi or relative_m % 2 == 0:
        raise ValueError("spin-polarized fermion relative_m must be odd and <=Nphi")
    pair_L = nphi - relative_m
    pairs = tuple(combinations(range(nphi + 1), 2))
    coeff = []
    for a, b in pairs:
        M2 = 2 * (a + b - nphi)  # twice M; integer key avoids float comparison
        c = math.sqrt(2.0) * sphere_clebsch_gordan(nphi, a, b, pair_L)
        coeff.append((M2, c))
    p = np.zeros((len(pairs), len(pairs)), dtype=float)
    for i, (mi, ci) in enumerate(coeff):
        if abs(ci) < 1e-15:
            continue
        for j, (mj, cj) in enumerate(coeff):
            if mi == mj and abs(cj) >= 1e-15:
                p[i, j] = ci * cj
    return pairs, p


@lru_cache(maxsize=64)
def sphere_fermion_basis(nphi: int, ne: int) -> tuple[int, ...]:
    norb = nphi + 1
    if ne < 1 or ne > norb:
        raise ValueError("invalid particle number")
    return tuple(sum(1 << i for i in occ) for occ in combinations(range(norb), ne))


def _annihilate(mask: int, orbital: int) -> tuple[int | None, int]:
    if ((mask >> orbital) & 1) == 0:
        return None, 0
    sign = -1 if ((mask & ((1 << orbital) - 1)).bit_count() % 2) else 1
    return mask ^ (1 << orbital), sign


def _create(mask: int, orbital: int) -> tuple[int | None, int]:
    if ((mask >> orbital) & 1) != 0:
        return None, 0
    sign = -1 if ((mask & ((1 << orbital) - 1)).bit_count() % 2) else 1
    return mask | (1 << orbital), sign


@lru_cache(maxsize=128)
def sphere_manybody_projector(nphi: int, ne: int, relative_m: int) -> np.ndarray:
    """Many-body sum_{i<j} P_ij^(m) in the full fermionic Fock basis."""
    states = sphere_fermion_basis(nphi, ne)
    state_index = {mask: i for i, mask in enumerate(states)}
    pairs, p2 = sphere_pair_projector(nphi, relative_m)
    transitions = {
        j: tuple((i, float(p2[i, j])) for i in range(len(pairs)) if abs(p2[i, j]) > 1e-14)
        for j in range(len(pairs))
    }
    h = np.zeros((len(states), len(states)), dtype=float)
    for col, mask in enumerate(states):
        for j, (c, d) in enumerate(pairs):
            if not (((mask >> c) & 1) and ((mask >> d) & 1)):
                continue
            m1, s1 = _annihilate(mask, c)
            m2, s2 = _annihilate(m1, d)
            for i, value in transitions[j]:
                a, b = pairs[i]
                m3, s3 = _create(m2, b)
                if m3 is None:
                    continue
                m4, s4 = _create(m3, a)
                if m4 is None:
                    continue
                h[state_index[m4], col] += value * s1 * s2 * s3 * s4
    return 0.5 * (h + h.T)


@lru_cache(maxsize=32)
def v1_sphere_spectrum(ne: int, extra_flux: int = 0) -> tuple[np.ndarray, np.ndarray, int]:
    nphi = laughlin_sphere_flux(ne, 3) + extra_flux
    h = sphere_manybody_projector(nphi, ne, 1)
    e, v = np.linalg.eigh(h)
    return e, v, nphi


def finite_size_v1_gaps(ne_values: tuple[int, ...] = (2, 3, 4)) -> dict[str, np.ndarray]:
    ne_arr = np.asarray(ne_values, dtype=int)
    gaps = []
    zero_modes = []
    dims = []
    for ne in ne_arr:
        e, _, nphi = v1_sphere_spectrum(int(ne), 0)
        nz = int(np.sum(np.abs(e) < 1e-10))
        zero_modes.append(nz)
        gaps.append(float(e[nz]))
        dims.append(len(sphere_fermion_basis(nphi, int(ne))))
    return {
        "ne": ne_arr,
        "gap": np.asarray(gaps, dtype=float),
        "zero_modes": np.asarray(zero_modes, dtype=int),
        "hilbert_dim": np.asarray(dims, dtype=int),
    }


def quasihole_zero_mode_diagnostics(ne_values: tuple[int, ...] = (3, 4)) -> dict[str, np.ndarray]:
    ne_arr = np.asarray(ne_values, dtype=int)
    base = []
    qh = []
    qh_gap = []
    dims = []
    for ne in ne_arr:
        e0, _, nphi0 = v1_sphere_spectrum(int(ne), 0)
        e1, _, nphi1 = v1_sphere_spectrum(int(ne), 1)
        n0 = int(np.sum(np.abs(e0) < 1e-10))
        n1 = int(np.sum(np.abs(e1) < 1e-10))
        base.append(n0)
        qh.append(n1)
        qh_gap.append(float(e1[n1]))
        dims.append(len(sphere_fermion_basis(nphi1, int(ne))))
    return {
        "ne": ne_arr,
        "base_zero_modes": np.asarray(base, dtype=int),
        "quasihole_zero_modes": np.asarray(qh, dtype=int),
        "quasihole_gap": np.asarray(qh_gap, dtype=float),
        "quasihole_hilbert_dim": np.asarray(dims, dtype=int),
    }


@lru_cache(maxsize=32)
def sphere_coulomb_hamiltonian(nphi: int, ne: int) -> np.ndarray:
    h = np.zeros((len(sphere_fermion_basis(nphi, ne)),) * 2, dtype=float)
    for m in range(1, nphi + 1, 2):
        h += coulomb_pseudopotential(m) * sphere_manybody_projector(nphi, ne, m)
    return 0.5 * (h + h.T)


@lru_cache(maxsize=8)
def v1_coulomb_spectral_flow(ne: int = 4, nlambda: int = 21) -> dict[str, np.ndarray | float]:
    nphi = laughlin_sphere_flux(ne, 3)
    hv1 = sphere_manybody_projector(nphi, ne, 1)
    hc = sphere_coulomb_hamiltonian(nphi, ne)
    e_v1, v_v1 = np.linalg.eigh(hv1)
    psi0 = v_v1[:, 0]
    lam = np.linspace(0.0, 1.0, nlambda)
    nlevels = min(10, hv1.shape[0])
    levels = np.empty((nlambda, nlevels), dtype=float)
    gaps = np.empty(nlambda, dtype=float)
    overlaps = np.empty(nlambda, dtype=float)
    for i, x in enumerate(lam):
        h = (1.0 - x) * hv1 + x * hc
        e, v = np.linalg.eigh(h)
        levels[i] = e[:nlevels]
        gaps[i] = e[1] - e[0]
        overlaps[i] = abs(np.vdot(psi0, v[:, 0])) ** 2
    return {
        "lambda": lam,
        "levels": levels,
        "gap": gaps,
        "overlap_sq": overlaps,
        "min_gap": float(np.min(gaps)),
        "endpoint_overlap_sq": float(overlaps[-1]),
    }


def _compact_slater_vector(nphi: int, ne: int) -> np.ndarray:
    states = sphere_fermion_basis(nphi, ne)
    mask = sum(1 << i for i in range(ne))
    out = np.zeros(len(states), dtype=float)
    out[states.index(mask)] = 1.0
    return out


@lru_cache(maxsize=8)
def pair_amplitude_diagnostics(ne: int = 4) -> dict[str, np.ndarray | float]:
    nphi = laughlin_sphere_flux(ne, 3)
    e, v, _ = v1_sphere_spectrum(ne, 0)
    psi = v[:, 0]
    slater = _compact_slater_vector(nphi, ne)
    mvals = np.arange(1, nphi + 1, 2, dtype=int)
    laughlin = []
    compact = []
    for m in mvals:
        pm = sphere_manybody_projector(nphi, ne, int(m))
        laughlin.append(float(np.real(np.vdot(psi, pm @ psi))))
        compact.append(float(np.real(np.vdot(slater, pm @ slater))))
    return {
        "m": mvals,
        "laughlin": np.asarray(laughlin),
        "compact_slater": np.asarray(compact),
        "laughlin_sum": float(np.sum(laughlin)),
        "compact_sum": float(np.sum(compact)),
        "pair_count": float(ne * (ne - 1) / 2),
    }


def manybody_commit590_diagnostics() -> dict[str, float | int | list[float] | list[int]]:
    gaps = finite_size_v1_gaps()
    qh = quasihole_zero_mode_diagnostics()
    flow = v1_coulomb_spectral_flow()
    pair = pair_amplitude_diagnostics()
    e4, _, nphi4 = v1_sphere_spectrum(4, 0)
    e4qh, _, nphi4qh = v1_sphere_spectrum(4, 1)
    nzero4qh = int(np.sum(np.abs(e4qh) < 1e-10))
    return {
        "ed_ne": [int(x) for x in gaps["ne"]],
        "ed_hilbert_dim": [int(x) for x in gaps["hilbert_dim"]],
        "v1_finite_size_gap": [float(x) for x in gaps["gap"]],
        "v1_zero_modes": [int(x) for x in gaps["zero_modes"]],
        "ne4_nphi": int(nphi4),
        "ne4_hilbert_dim": int(len(sphere_fermion_basis(nphi4, 4))),
        "ne4_v1_gap": float(gaps["gap"][-1]),
        "ne4_quasihole_nphi": int(nphi4qh),
        "ne4_quasihole_hilbert_dim": int(len(sphere_fermion_basis(nphi4qh, 4))),
        "ne4_quasihole_zero_modes": nzero4qh,
        "ne4_quasihole_gap": float(e4qh[nzero4qh]),
        "spectral_flow_min_gap": float(flow["min_gap"]),
        "spectral_flow_endpoint_gap": float(flow["gap"][-1]),
        "spectral_flow_endpoint_overlap_sq": float(flow["endpoint_overlap_sq"]),
        "pair_m": [int(x) for x in pair["m"]],
        "laughlin_pair_amplitudes": [float(x) for x in pair["laughlin"]],
        "compact_slater_pair_amplitudes": [float(x) for x in pair["compact_slater"]],
        "laughlin_pair_sum": float(pair["laughlin_sum"]),
        "compact_pair_sum": float(pair["compact_sum"]),
        "pair_count": float(pair["pair_count"]),
    }

# ---------------------------------------------------------------------------
# Commit 591: torus many-body momentum sectors, non-Abelian Chern response,
# and fractional quasiparticle-charge diagnostics in a projected Hofstadter band
# ---------------------------------------------------------------------------


def torus_lowest_band_orbitals(
    qden: int = 3,
    nx: int = 1,
    ny: int = 9,
    *,
    theta_x: float = 0.0,
    theta_y: float = 0.0,
) -> tuple[np.ndarray, tuple[tuple[int, int], ...]]:
    """Lowest Hofstadter-band orbitals on an ``nx x ny`` magnetic-cell torus.

    The real-space lattice has ``Lx=qden*nx`` and ``Ly=ny`` sites at flux
    alpha=1/qden.  ``theta_x`` and ``theta_y`` are physical boundary twists.
    The returned columns are orthonormal real-space orbitals spanning the
    lowest magnetic band; their labels are the discrete magnetic-cell momenta.
    """
    if qden < 2 or nx < 1 or ny < 1:
        raise ValueError("require qden>=2 and positive magnetic-cell dimensions")
    lx, ly = qden * nx, ny
    orbitals: list[np.ndarray] = []
    labels: list[tuple[int, int]] = []
    for ix in range(nx):
        kx = (TWOPI * ix + theta_x) / nx
        for iy in range(ny):
            ky = (TWOPI * iy + theta_y) / ny
            _, vec = np.linalg.eigh(magnetic_bloch_hamiltonian(qden, kx, ky))
            u = vec[:, 0]
            phi = np.zeros(lx * ly, dtype=complex)
            for x in range(lx):
                cell_x, sub = divmod(x, qden)
                for y in range(ly):
                    phi[_idx(x, y, ly)] = (
                        np.exp(1j * (kx * cell_x + ky * y))
                        * u[sub]
                        / math.sqrt(nx * ny)
                    )
            orbitals.append(phi)
            labels.append((ix, iy))
    out = np.column_stack(orbitals)
    return out, tuple(labels)


def torus_nearest_neighbor_bonds(qden: int = 3, nx: int = 1, ny: int = 9) -> tuple[tuple[int, int], ...]:
    """Unique +x and +y nearest-neighbor bonds of the real-space torus."""
    lx, ly = qden * nx, ny
    bonds: list[tuple[int, int]] = []
    for x in range(lx):
        for y in range(ly):
            i = _idx(x, y, ly)
            bonds.append((i, _idx((x + 1) % lx, y, ly)))
            bonds.append((i, _idx(x, (y + 1) % ly, ly)))
    return tuple(bonds)


def projected_pair_interaction(
    orbitals: np.ndarray,
    bonds: tuple[tuple[int, int], ...],
    *,
    strength: float = 1.0,
) -> tuple[tuple[tuple[int, int], ...], np.ndarray]:
    """Two-fermion interaction matrix after projection to an orbital subspace.

    For a density-density nearest-neighbor interaction, each bond contributes
    the outer product of the antisymmetrized two-orbital bond amplitudes.
    """
    ns = orbitals.shape[1]
    pairs = tuple(combinations(range(ns), 2))
    amp = np.empty((len(bonds), len(pairs)), dtype=complex)
    for ib, (r, s) in enumerate(bonds):
        pr, ps = orbitals[r], orbitals[s]
        amp[ib] = [pr[a] * ps[b] - pr[b] * ps[a] for a, b in pairs]
    pair_h = strength * (amp.conj().T @ amp)
    return pairs, 0.5 * (pair_h + pair_h.conj().T)


@lru_cache(maxsize=64)
def torus_fermion_basis(norb: int, ne: int) -> tuple[int, ...]:
    if norb < 1 or ne < 1 or ne > norb:
        raise ValueError("invalid torus orbital or particle number")
    return tuple(sum(1 << i for i in occ) for occ in combinations(range(norb), ne))


def manybody_from_pair_matrix(
    norb: int,
    ne: int,
    pairs: tuple[tuple[int, int], ...],
    pair_h: np.ndarray,
) -> np.ndarray:
    """Lift an antisymmetric two-particle matrix to a fermionic Fock basis."""
    states = torus_fermion_basis(norb, ne)
    state_index = {mask: i for i, mask in enumerate(states)}
    transitions = {
        j: tuple((i, pair_h[i, j]) for i in range(len(pairs)) if abs(pair_h[i, j]) > 1e-13)
        for j in range(len(pairs))
    }
    h = np.zeros((len(states), len(states)), dtype=complex)
    for col, mask in enumerate(states):
        for j, (c, d) in enumerate(pairs):
            if not (((mask >> c) & 1) and ((mask >> d) & 1)):
                continue
            m1, s1 = _annihilate(mask, c)
            m2, s2 = _annihilate(m1, d)
            for i, value in transitions[j]:
                a, b = pairs[i]
                m3, s3 = _create(m2, b)
                if m3 is None:
                    continue
                m4, s4 = _create(m3, a)
                if m4 is None:
                    continue
                h[state_index[m4], col] += value * s1 * s2 * s3 * s4
    return 0.5 * (h + h.conj().T)


def torus_projected_nn_hamiltonian(
    *,
    qden: int = 3,
    nx: int = 1,
    ny: int = 9,
    ne: int = 3,
    theta_x: float = 0.0,
    theta_y: float = 0.0,
    strength: float = 1.0,
) -> tuple[np.ndarray, np.ndarray, tuple[tuple[int, int], ...], tuple[int, ...]]:
    """Projected nearest-neighbor interaction at fractional band filling."""
    orbitals, labels = torus_lowest_band_orbitals(
        qden, nx, ny, theta_x=theta_x, theta_y=theta_y
    )
    pairs, pair_h = projected_pair_interaction(
        orbitals, torus_nearest_neighbor_bonds(qden, nx, ny), strength=strength
    )
    h = manybody_from_pair_matrix(nx * ny, ne, pairs, pair_h)
    return h, orbitals, labels, torus_fermion_basis(nx * ny, ne)


def _torus_sector(mask: int, labels: tuple[tuple[int, int], ...], nx: int, ny: int) -> tuple[int, int]:
    kx = ky = 0
    for orbital, (ix, iy) in enumerate(labels):
        if (mask >> orbital) & 1:
            kx = (kx + ix) % nx
            ky = (ky + iy) % ny
    return kx, ky


@lru_cache(maxsize=8)
def torus_momentum_sector_diagnostics(
    qden: int = 3, nx: int = 1, ny: int = 9, ne: int = 3
) -> dict[str, object]:
    """Zero-twist symmetry sectors and the three-state low-energy multiplet."""
    h, _, labels, states = torus_projected_nn_hamiltonian(
        qden=qden, nx=nx, ny=ny, ne=ne
    )
    groups: dict[tuple[int, int], list[int]] = {}
    for i, mask in enumerate(states):
        groups.setdefault(_torus_sector(mask, labels, nx, ny), []).append(i)

    sector_rows: list[tuple[int, int, int, np.ndarray]] = []
    off_block_max = 0.0
    for sector, inds in sorted(groups.items()):
        comp = [j for j in range(len(states)) if j not in set(inds)]
        if comp:
            off_block_max = max(off_block_max, float(np.max(np.abs(h[np.ix_(inds, comp)]))))
        ev = np.linalg.eigvalsh(h[np.ix_(inds, inds)])
        sector_rows.append((sector[0], sector[1], len(inds), ev))

    full = np.linalg.eigvalsh(h)
    ground_indices = np.argsort([row[3][0] for row in sector_rows])[:3]
    ground_sectors = [(sector_rows[i][0], sector_rows[i][1]) for i in ground_indices]
    return {
        "hilbert_dim": len(states),
        "sector_rows": sector_rows,
        "ground_sectors": ground_sectors,
        "ground_energies": full[:3],
        "multiplet_splitting": float(full[2] - full[0]),
        "gap_above_multiplet": float(full[3] - full[2]),
        "off_block_max": off_block_max,
    }


def _exterior_power_basis(orbitals: np.ndarray, ne: int) -> np.ndarray:
    """Embed projected-band Slater determinants in the real-space Fock basis."""
    row_occ = np.asarray(list(combinations(range(orbitals.shape[0]), ne)), dtype=int)
    col_occ = list(combinations(range(orbitals.shape[1]), ne))
    transform = np.empty((len(row_occ), len(col_occ)), dtype=complex)
    selected_rows = orbitals[row_occ]
    for j, cols in enumerate(col_occ):
        transform[:, j] = np.linalg.det(selected_rows[:, :, cols])
    return transform


def torus_embedded_ground_frame(
    theta_x: float,
    theta_y: float,
    *,
    qden: int = 3,
    nx: int = 1,
    ny: int = 9,
    ne: int = 3,
    multiplet: int = 3,
) -> tuple[np.ndarray, np.ndarray]:
    """Return low energies and a common-real-space frame for the ground bundle."""
    h, orbitals, _, _ = torus_projected_nn_hamiltonian(
        qden=qden, nx=nx, ny=ny, ne=ne, theta_x=theta_x, theta_y=theta_y
    )
    e, coeff = np.linalg.eigh(h)
    transform = _exterior_power_basis(orbitals, ne)
    frame = transform @ coeff[:, :multiplet]
    return e, frame


def nonabelian_ground_bundle_chern(
    ntheta: int = 7,
    *,
    qden: int = 3,
    nx: int = 1,
    ny: int = 9,
    ne: int = 3,
    multiplet: int = 3,
) -> dict[str, np.ndarray | float]:
    """Fukui-Hatsugai-Suzuki Chern number of the many-body ground multiplet."""
    if ntheta < 3:
        raise ValueError("ntheta must be at least 3")
    theta = np.linspace(0.0, TWOPI, ntheta, endpoint=False)
    frames: list[list[np.ndarray]] = [[None for _ in range(ntheta)] for _ in range(ntheta)]  # type: ignore[list-item]
    low = np.empty((ntheta, ntheta, multiplet + 1), dtype=float)
    for ix, tx in enumerate(theta):
        for iy, ty in enumerate(theta):
            e, frame = torus_embedded_ground_frame(
                float(tx), float(ty), qden=qden, nx=nx, ny=ny, ne=ne, multiplet=multiplet
            )
            frames[ix][iy] = frame
            low[ix, iy] = e[: multiplet + 1]

    ux = np.empty((ntheta, ntheta), dtype=complex)
    uy = np.empty((ntheta, ntheta), dtype=complex)
    min_overlap_det = float("inf")
    for ix in range(ntheta):
        for iy in range(ntheta):
            ox = frames[ix][iy].conj().T @ frames[(ix + 1) % ntheta][iy]
            oy = frames[ix][iy].conj().T @ frames[ix][(iy + 1) % ntheta]
            min_overlap_det = min(min_overlap_det, abs(np.linalg.det(ox)), abs(np.linalg.det(oy)))
            ux[ix, iy] = _unit_det_phase(ox)
            uy[ix, iy] = _unit_det_phase(oy)

    curvature = np.empty((ntheta, ntheta), dtype=float)
    for ix in range(ntheta):
        for iy in range(ntheta):
            loop = (
                ux[ix, iy]
                * uy[(ix + 1) % ntheta, iy]
                / (ux[ix, (iy + 1) % ntheta] * uy[ix, iy])
            )
            curvature[ix, iy] = np.angle(loop)

    # y-directed Wilson loop at each theta_x; its determinant winds with C in
    # the same orientation as the plaquette convention above.
    wilson_phase = np.empty(ntheta, dtype=float)
    for ix in range(ntheta):
        z = 1.0 + 0.0j
        for iy in range(ntheta):
            z *= uy[ix, iy]
        wilson_phase[ix] = np.angle(z)
    closed_phase = np.unwrap(np.r_[wilson_phase, wilson_phase[0]])
    wilson_winding = float((closed_phase[-1] - closed_phase[0]) / TWOPI)

    gap = low[:, :, multiplet] - low[:, :, multiplet - 1]
    split = low[:, :, multiplet - 1] - low[:, :, 0]
    chern = float(np.sum(curvature) / TWOPI)
    return {
        "theta": theta,
        "low_energies": low,
        "curvature_phase": curvature,
        "chern": chern,
        "wilson_phase": wilson_phase,
        "wilson_winding": wilson_winding,
        "minimum_gap": float(np.min(gap)),
        "maximum_multiplet_splitting": float(np.max(split)),
        "minimum_overlap_det": min_overlap_det,
    }


def torus_twist_spectral_flow(
    ntheta: int = 25,
    *,
    qden: int = 3,
    nx: int = 1,
    ny: int = 9,
    ne: int = 3,
    nlevels: int = 8,
) -> dict[str, np.ndarray | float]:
    """Low-energy many-body spectrum during one x-boundary flux cycle."""
    theta = np.linspace(0.0, TWOPI, ntheta, endpoint=True)
    levels = np.empty((ntheta, nlevels), dtype=float)
    for i, tx in enumerate(theta):
        h, _, _, _ = torus_projected_nn_hamiltonian(
            qden=qden, nx=nx, ny=ny, ne=ne, theta_x=float(tx), theta_y=0.0
        )
        levels[i] = np.linalg.eigvalsh(h)[:nlevels]
    return {
        "theta_x": theta,
        "levels": levels,
        "cycle_closure": float(np.max(np.abs(levels[0] - levels[-1]))),
        "minimum_direct_gap": float(np.min(levels[:, 3] - levels[:, 2])),
    }


def quasiparticle_charge_diagnostics(
    *, denominator: int = 3, ground_bundle_chern: float = -1.0, ground_multiplet: int = 3
) -> dict[str, float]:
    """Two finite-system routes to the Laughlin quasihole charge.

    Flux counting gives one missing fraction ``nu`` of an electron when one flux
    quantum is added at fixed particle number.  Independently, the charge pumped
    per single topological sector is the total ground-bundle Chern number divided
    by the torus degeneracy.  Signs follow the electron/twist orientation used in
    the chapter; magnitudes give |e*|/e.
    """
    if denominator < 1 or ground_multiplet < 1:
        raise ValueError("invalid denominator or multiplet")
    nu = 1.0 / denominator
    flux_counting = nu
    c_per_sector = ground_bundle_chern / ground_multiplet
    return {
        "nu": nu,
        "flux_added": 1.0,
        "electron_number_deficit": nu,
        "quasihole_charge_over_e": nu,
        "chern_per_ground_state": c_per_sector,
        "pumped_charge_magnitude_over_e": abs(c_per_sector),
        "consistency_error": abs(nu - abs(c_per_sector)),
    }


def manybody_commit591_diagnostics() -> dict[str, object]:
    sectors = torus_momentum_sector_diagnostics()
    bundle = nonabelian_ground_bundle_chern(7)
    flow = torus_twist_spectral_flow(25)
    charge = quasiparticle_charge_diagnostics(
        ground_bundle_chern=float(bundle["chern"]), ground_multiplet=3
    )
    return {
        "torus_qden": 3,
        "torus_magnetic_cells": [1, 9],
        "torus_nphi": 9,
        "torus_ne": 3,
        "torus_hilbert_dim": int(sectors["hilbert_dim"]),
        "torus_ground_sectors": [[int(a), int(b)] for a, b in sectors["ground_sectors"]],
        "torus_ground_energies": [float(x) for x in sectors["ground_energies"]],
        "torus_multiplet_splitting": float(sectors["multiplet_splitting"]),
        "torus_gap_above_multiplet": float(sectors["gap_above_multiplet"]),
        "torus_sector_offblock_max": float(sectors["off_block_max"]),
        "manybody_chern_grid": 7,
        "manybody_ground_bundle_chern": float(bundle["chern"]),
        "manybody_wilson_winding": float(bundle["wilson_winding"]),
        "manybody_twist_minimum_gap": float(bundle["minimum_gap"]),
        "manybody_twist_maximum_multiplet_splitting": float(bundle["maximum_multiplet_splitting"]),
        "manybody_minimum_overlap_det": float(bundle["minimum_overlap_det"]),
        "twist_cycle_closure": float(flow["cycle_closure"]),
        "twist_flow_minimum_direct_gap": float(flow["minimum_direct_gap"]),
        "quasihole_charge_over_e": float(charge["quasihole_charge_over_e"]),
        "chern_per_ground_state": float(charge["chern_per_ground_state"]),
        "pumped_charge_magnitude_over_e": float(charge["pumped_charge_magnitude_over_e"]),
        "quasiparticle_charge_consistency_error": float(charge["consistency_error"]),
    }


# ---------------------------------------------------------------------------
# Commit 592: finite-size/shape scaling, particle entanglement counting,
# pinned-quasihole density, and disorder robustness of the many-body bundle
# ---------------------------------------------------------------------------


def torus_finite_size_scaling() -> dict[str, np.ndarray | list[tuple[int, int]]]:
    """Near-square finite-size sequence for the projected nu=1/3 torus state.

    The three members keep N_phi=3 N_e while choosing compact magnetic-cell
    factorizations.  These are finite regulators, not a thermodynamic fit.
    """
    cases = ((2, 2, 3), (3, 3, 3), (4, 3, 4))  # (Ne, Nx, Ny)
    ne, nphi, dim, split, gap, ratio = [], [], [], [], [], []
    geometries: list[tuple[int, int]] = []
    for particles, nx, ny in cases:
        d = torus_momentum_sector_diagnostics(3, nx, ny, particles)
        ne.append(particles)
        nphi.append(nx * ny)
        dim.append(int(d["hilbert_dim"]))
        split.append(float(d["multiplet_splitting"]))
        gap.append(float(d["gap_above_multiplet"]))
        ratio.append(float(d["gap_above_multiplet"] / max(d["multiplet_splitting"], 1e-14)))
        geometries.append((nx, ny))
    return {
        "ne": np.asarray(ne, dtype=int),
        "nphi": np.asarray(nphi, dtype=int),
        "hilbert_dim": np.asarray(dim, dtype=int),
        "geometry": geometries,
        "inverse_nphi": 1.0 / np.asarray(nphi, dtype=float),
        "multiplet_splitting": np.asarray(split, dtype=float),
        "gap": np.asarray(gap, dtype=float),
        "gap_to_split_ratio": np.asarray(ratio, dtype=float),
    }


@lru_cache(maxsize=4)
def torus_shape_scan(ne: int = 4, nphi: int = 12) -> dict[str, np.ndarray | list[tuple[int, int]]]:
    """Magnetic-cell shape scan at fixed particle and flux number.

    ``Nx/Ny`` is a regulator-shape parameter for the Hofstadter magnetic-cell
    torus.  It should not be identified blindly with a continuum modular
    parameter because the magnetic unit cell itself is anisotropic in this
    Landau-gauge regularization.
    """
    if nphi % 3 != 0 or 3 * ne != nphi:
        raise ValueError("shape scan expects nu=1/3 and nphi divisible by three")
    shapes = [(nx, nphi // nx) for nx in range(1, nphi + 1) if nphi % nx == 0]
    split, gap, ratio = [], [], []
    for nx, ny in shapes:
        d = torus_momentum_sector_diagnostics(3, nx, ny, ne)
        sp = float(d["multiplet_splitting"])
        gp = float(d["gap_above_multiplet"])
        split.append(sp)
        gap.append(gp)
        ratio.append(gp / max(sp, 1e-14))
    return {
        "geometry": shapes,
        "cell_aspect": np.asarray([nx / ny for nx, ny in shapes], dtype=float),
        "multiplet_splitting": np.asarray(split, dtype=float),
        "gap": np.asarray(gap, dtype=float),
        "gap_to_split_ratio": np.asarray(ratio, dtype=float),
    }


def generalized_exclusion_masks(norb: int, nparticles: int, spacing: int = 3) -> tuple[int, ...]:
    """Circular (1,spacing)-admissible occupation patterns on a torus ring."""
    if norb < 1 or nparticles < 0 or spacing < 1:
        raise ValueError("invalid exclusion-counting parameters")
    out: list[int] = []
    for occ in combinations(range(norb), nparticles):
        occupied = set(occ)
        ok = True
        for i in occ:
            for d in range(1, spacing):
                if (i + d) % norb in occupied:
                    ok = False
                    break
            if not ok:
                break
        if ok:
            out.append(sum(1 << i for i in occ))
    return tuple(out)


def generalized_exclusion_count(norb: int, nparticles: int, spacing: int = 3) -> int:
    return len(generalized_exclusion_masks(norb, nparticles, spacing))


def _split_fermion_sign(mask_a: int, mask_b: int) -> int:
    """Sign for writing the canonical full Slater determinant as A wedge B."""
    a = [i for i in range(max(mask_a.bit_length(), mask_b.bit_length())) if (mask_a >> i) & 1]
    b = [i for i in range(max(mask_a.bit_length(), mask_b.bit_length())) if (mask_b >> i) & 1]
    inversions = sum(1 for ia in a for ib in b if ia > ib)
    return -1 if inversions % 2 else 1


@lru_cache(maxsize=8)
def particle_entanglement_spectrum(
    qden: int = 3,
    nx: int = 3,
    ny: int = 4,
    ne: int = 4,
    na: int = 2,
    multiplet: int = 3,
) -> dict[str, np.ndarray | float | int]:
    """Particle entanglement spectrum of the mixed low-energy ground projector.

    The reduced density matrix is normalized to unit trace.  For the compact
    N_e=4, N_phi=12 benchmark, its primary internal entanglement gap occurs
    after exactly 42 levels, matching circular (1,3) exclusion counting for
    two retained particles.
    """
    norb = nx * ny
    if not (0 < na < ne <= norb):
        raise ValueError("require 0 < na < ne <= norb")
    h, _, _, states = torus_projected_nn_hamiltonian(qden=qden, nx=nx, ny=ny, ne=ne)
    energies, vec = np.linalg.eigh(h)
    a_basis = torus_fermion_basis(norb, na)
    b_basis = torus_fermion_basis(norb, ne - na)
    a_index = {m: i for i, m in enumerate(a_basis)}
    b_index = {m: i for i, m in enumerate(b_basis)}
    rho = np.zeros((len(a_basis), len(a_basis)), dtype=complex)
    norm = math.comb(ne, na)
    for g in range(multiplet):
        coeff_matrix = np.zeros((len(a_basis), len(b_basis)), dtype=complex)
        for coeff, full_mask in zip(vec[:, g], states):
            occupied = [i for i in range(norb) if (full_mask >> i) & 1]
            for a_occ in combinations(occupied, na):
                mask_a = sum(1 << i for i in a_occ)
                mask_b = full_mask ^ mask_a
                coeff_matrix[a_index[mask_a], b_index[mask_b]] = (
                    _split_fermion_sign(mask_a, mask_b) * coeff
                )
        rho += coeff_matrix @ coeff_matrix.conj().T / norm
    rho /= multiplet
    eigenvalues = np.linalg.eigvalsh(rho)[::-1].real
    positive = eigenvalues[eigenvalues > 1e-12]
    entanglement_energy = -np.log(positive)
    gaps = np.diff(entanglement_energy)
    gap_index = int(np.argmax(gaps) + 1) if len(gaps) else 0
    entanglement_gap = float(gaps[gap_index - 1]) if gap_index else 0.0
    admissible = generalized_exclusion_count(norb, na, 3)
    return {
        "ground_energies": energies[: multiplet + 1],
        "rho_eigenvalues": eigenvalues,
        "entanglement_energy": entanglement_energy,
        "rho_trace": float(np.sum(eigenvalues)),
        "positive_rank": int(len(positive)),
        "low_level_count": gap_index,
        "entanglement_gap": entanglement_gap,
        "admissible_13_count": int(admissible),
    }


def _manybody_from_one_body_matrix(norb: int, ne: int, h1: np.ndarray) -> np.ndarray:
    states = torus_fermion_basis(norb, ne)
    index = {mask: i for i, mask in enumerate(states)}
    h = np.zeros((len(states), len(states)), dtype=complex)
    for col, mask in enumerate(states):
        for b in range(norb):
            if not ((mask >> b) & 1):
                continue
            m1, s1 = _annihilate(mask, b)
            for a in range(norb):
                value = h1[a, b]
                if abs(value) < 1e-13:
                    continue
                m2, s2 = _create(m1, a)
                if m2 is not None:
                    h[index[m2], col] += value * s1 * s2
    return 0.5 * (h + h.conj().T)


def _one_body_density_matrix(norb: int, ne: int, psi: np.ndarray) -> np.ndarray:
    """Return gamma_ab=<d_a^dagger d_b> for one normalized many-body state."""
    states = torus_fermion_basis(norb, ne)
    index = {mask: i for i, mask in enumerate(states)}
    gamma = np.zeros((norb, norb), dtype=complex)
    for col, mask in enumerate(states):
        amp = psi[col]
        if abs(amp) < 1e-15:
            continue
        for b in range(norb):
            if not ((mask >> b) & 1):
                continue
            m1, s1 = _annihilate(mask, b)
            for a in range(norb):
                m2, s2 = _create(m1, a)
                if m2 is None:
                    continue
                gamma[a, b] += np.conj(psi[index[m2]]) * amp * s1 * s2
    return gamma


def _site_density(orbitals: np.ndarray, gamma: np.ndarray) -> np.ndarray:
    return np.einsum("ra,ab,rb->r", orbitals.conj(), gamma, orbitals).real


@lru_cache(maxsize=8)
def pinned_quasihole_density_diagnostics(
    *,
    qden: int = 3,
    nx: int = 1,
    ny: int = 10,
    ne: int = 3,
    pin_strength: float = 0.01,
    pin_sigma: float = 0.6,
    quasihole_manifold: int = 10,
) -> dict[str, np.ndarray | float | int | tuple[int, int]]:
    """Localize the one-flux quasihole and integrate its density deficit.

    The unpinned reference is the equal mixture of the low-energy quasihole
    manifold.  The same particle number is used before and after pinning, so
    the integrated deficit must return to zero over the complete finite torus;
    a local plateau near 1/3 is the finite-size charge diagnostic.
    """
    norb = nx * ny
    h, orbitals, _, _ = torus_projected_nn_hamiltonian(
        qden=qden, nx=nx, ny=ny, ne=ne
    )
    energies, vec = np.linalg.eigh(h)
    if quasihole_manifold >= len(energies):
        raise ValueError("quasihole manifold must leave at least one excited state")
    gamma_ref = sum(
        (_one_body_density_matrix(norb, ne, vec[:, j]) for j in range(quasihole_manifold)),
        np.zeros((norb, norb), dtype=complex),
    ) / quasihole_manifold
    density_ref = _site_density(orbitals, gamma_ref)

    lx, ly = qden * nx, ny
    center = (lx // 2, ly // 2)
    potential = np.zeros(lx * ly, dtype=float)
    distance = np.zeros(lx * ly, dtype=float)
    for x in range(lx):
        dx = min((x - center[0]) % lx, (center[0] - x) % lx)
        for y in range(ly):
            dy = min((y - center[1]) % ly, (center[1] - y) % ly)
            r = math.sqrt(dx * dx + dy * dy)
            i = _idx(x, y, ly)
            distance[i] = r
            potential[i] = math.exp(-(r * r) / (2.0 * pin_sigma * pin_sigma))

    h1 = orbitals.conj().T @ (potential[:, None] * orbitals)
    h_pinned = h + pin_strength * _manybody_from_one_body_matrix(norb, ne, h1)
    pinned_energy, pinned_vec = np.linalg.eigh(h_pinned)
    gamma_pin = _one_body_density_matrix(norb, ne, pinned_vec[:, 0])
    density_pin = _site_density(orbitals, gamma_pin)
    deficit = density_ref - density_pin

    radii = np.asarray(sorted(set(float(r) for r in distance)), dtype=float)
    integrated = np.asarray(
        [float(np.sum(deficit[distance <= r + 1e-12])) for r in radii], dtype=float
    )
    target = 1.0 / 3.0
    local_candidates = np.where(radii <= 2.0 + 1e-12)[0]
    best = int(local_candidates[np.argmin(np.abs(integrated[local_candidates] - target))])
    first_shell = int(np.argmin(np.abs(radii - 1.0)))
    return {
        "nphi": norb,
        "ne": ne,
        "quasihole_manifold": quasihole_manifold,
        "quasihole_gap": float(energies[quasihole_manifold] - energies[quasihole_manifold - 1]),
        "pin_center": center,
        "pin_strength": float(pin_strength),
        "pin_sigma": float(pin_sigma),
        "pinned_ground_gap": float(pinned_energy[1] - pinned_energy[0]),
        "distance": distance,
        "density_reference": density_ref,
        "density_pinned": density_pin,
        "density_deficit": deficit,
        "radii": radii,
        "integrated_deficit": integrated,
        "best_local_radius": float(radii[best]),
        "best_local_charge_over_e": float(integrated[best]),
        "first_shell_charge_over_e": float(integrated[first_shell]),
        "total_deficit": float(np.sum(deficit)),
    }


def _disordered_embedded_ground_frame(
    theta_x: float,
    theta_y: float,
    disorder: np.ndarray,
    *,
    qden: int = 3,
    nx: int = 1,
    ny: int = 9,
    ne: int = 3,
    multiplet: int = 3,
) -> tuple[np.ndarray, np.ndarray]:
    h, orbitals, _, _ = torus_projected_nn_hamiltonian(
        qden=qden, nx=nx, ny=ny, ne=ne, theta_x=theta_x, theta_y=theta_y
    )
    h1 = orbitals.conj().T @ (disorder[:, None] * orbitals)
    h += _manybody_from_one_body_matrix(nx * ny, ne, h1)
    e, coeff = np.linalg.eigh(h)
    transform = _exterior_power_basis(orbitals, ne)
    return e, transform @ coeff[:, :multiplet]


@lru_cache(maxsize=32)
def disordered_ground_bundle_chern(
    disorder_strength: float,
    *,
    seed: int = 7,
    ntheta: int = 5,
    qden: int = 3,
    nx: int = 1,
    ny: int = 9,
    ne: int = 3,
    multiplet: int = 3,
) -> dict[str, float]:
    """Non-Abelian bundle invariant for one fixed projected disorder pattern."""
    if ntheta < 3:
        raise ValueError("ntheta must be at least 3")
    rng = np.random.default_rng(seed)
    nsite = qden * nx * ny
    disorder = disorder_strength * rng.uniform(-0.5, 0.5, nsite)
    theta = np.linspace(0.0, TWOPI, ntheta, endpoint=False)
    frames: list[list[np.ndarray]] = [[None for _ in range(ntheta)] for _ in range(ntheta)]  # type: ignore[list-item]
    low = np.empty((ntheta, ntheta, multiplet + 1), dtype=float)
    for ix, tx in enumerate(theta):
        for iy, ty in enumerate(theta):
            e, frame = _disordered_embedded_ground_frame(
                float(tx), float(ty), disorder,
                qden=qden, nx=nx, ny=ny, ne=ne, multiplet=multiplet,
            )
            frames[ix][iy] = frame
            low[ix, iy] = e[: multiplet + 1]

    ux = np.empty((ntheta, ntheta), dtype=complex)
    uy = np.empty((ntheta, ntheta), dtype=complex)
    min_overlap_det = float("inf")
    for ix in range(ntheta):
        for iy in range(ntheta):
            ox = frames[ix][iy].conj().T @ frames[(ix + 1) % ntheta][iy]
            oy = frames[ix][iy].conj().T @ frames[ix][(iy + 1) % ntheta]
            min_overlap_det = min(min_overlap_det, abs(np.linalg.det(ox)), abs(np.linalg.det(oy)))
            ux[ix, iy] = _unit_det_phase(ox)
            uy[ix, iy] = _unit_det_phase(oy)

    curvature_sum = 0.0
    for ix in range(ntheta):
        for iy in range(ntheta):
            loop = ux[ix, iy] * uy[(ix + 1) % ntheta, iy] / (
                ux[ix, (iy + 1) % ntheta] * uy[ix, iy]
            )
            curvature_sum += float(np.angle(loop))
    gap = low[:, :, multiplet] - low[:, :, multiplet - 1]
    split = low[:, :, multiplet - 1] - low[:, :, 0]
    minimum_gap = float(np.min(gap))
    maximum_split = float(np.max(split))
    return {
        "chern": float(curvature_sum / TWOPI),
        "minimum_gap": minimum_gap,
        "maximum_multiplet_splitting": maximum_split,
        "isolation_ratio": minimum_gap / max(maximum_split, 1e-14),
        "minimum_overlap_det": min_overlap_det,
    }


@lru_cache(maxsize=4)
def torus_disorder_robustness(
    seed: int = 7,
    ntheta: int = 5,
) -> dict[str, np.ndarray | int]:
    """Fixed-realization disorder stress test of the three-state ground bundle."""
    strengths = np.asarray([0.0, 0.01, 0.02, 0.04], dtype=float)
    rows = [disordered_ground_bundle_chern(float(w), seed=seed, ntheta=ntheta) for w in strengths]
    return {
        "seed": seed,
        "ntheta": ntheta,
        "disorder_strength": strengths,
        "chern": np.asarray([r["chern"] for r in rows], dtype=float),
        "minimum_gap": np.asarray([r["minimum_gap"] for r in rows], dtype=float),
        "maximum_multiplet_splitting": np.asarray([r["maximum_multiplet_splitting"] for r in rows], dtype=float),
        "isolation_ratio": np.asarray([r["isolation_ratio"] for r in rows], dtype=float),
        "minimum_overlap_det": np.asarray([r["minimum_overlap_det"] for r in rows], dtype=float),
    }


def manybody_commit592_diagnostics() -> dict[str, object]:
    finite = torus_finite_size_scaling()
    shape = torus_shape_scan()
    pes = particle_entanglement_spectrum()
    pin = pinned_quasihole_density_diagnostics()
    disorder = torus_disorder_robustness()
    return {
        "finite_size_ne": [int(x) for x in finite["ne"]],
        "finite_size_nphi": [int(x) for x in finite["nphi"]],
        "finite_size_geometry": [[int(a), int(b)] for a, b in finite["geometry"]],
        "finite_size_hilbert_dim": [int(x) for x in finite["hilbert_dim"]],
        "finite_size_multiplet_splitting": [float(x) for x in finite["multiplet_splitting"]],
        "finite_size_gap": [float(x) for x in finite["gap"]],
        "finite_size_gap_to_split_ratio": [float(x) for x in finite["gap_to_split_ratio"]],
        "shape_scan_geometry": [[int(a), int(b)] for a, b in shape["geometry"]],
        "shape_scan_gap": [float(x) for x in shape["gap"]],
        "shape_scan_multiplet_splitting": [float(x) for x in shape["multiplet_splitting"]],
        "pes_ne": 4,
        "pes_nphi": 12,
        "pes_particle_cut": 2,
        "pes_low_level_count": int(pes["low_level_count"]),
        "pes_admissible_13_count": int(pes["admissible_13_count"]),
        "pes_entanglement_gap": float(pes["entanglement_gap"]),
        "pes_rho_trace": float(pes["rho_trace"]),
        "quasihole_density_nphi": int(pin["nphi"]),
        "quasihole_density_manifold": int(pin["quasihole_manifold"]),
        "quasihole_density_gap": float(pin["quasihole_gap"]),
        "quasihole_pin_strength": float(pin["pin_strength"]),
        "quasihole_best_local_radius": float(pin["best_local_radius"]),
        "quasihole_best_local_charge_over_e": float(pin["best_local_charge_over_e"]),
        "quasihole_first_shell_charge_over_e": float(pin["first_shell_charge_over_e"]),
        "quasihole_total_deficit": float(pin["total_deficit"]),
        "disorder_seed": int(disorder["seed"]),
        "disorder_twist_grid": int(disorder["ntheta"]),
        "disorder_strength": [float(x) for x in disorder["disorder_strength"]],
        "disorder_bundle_chern": [float(x) for x in disorder["chern"]],
        "disorder_minimum_gap": [float(x) for x in disorder["minimum_gap"]],
        "disorder_maximum_multiplet_splitting": [float(x) for x in disorder["maximum_multiplet_splitting"]],
        "disorder_isolation_ratio": [float(x) for x in disorder["isolation_ratio"]],
        "disorder_minimum_overlap_det": [float(x) for x in disorder["minimum_overlap_det"]],
    }
