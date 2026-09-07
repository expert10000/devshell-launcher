"""Quantitative gauge diagnostics for Volume VIII, Chapter 53, Commit 585.

The computational examples use dimensionless units unless otherwise stated.
The defaults are hbar = m = 1 and a signed charge q = -1.  The module is
intentionally small: every result is tied to a closed-form gauge-covariant
identity used in the chapter text.
"""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np


def electric_scalar_gauge(x: np.ndarray | float, E: float) -> tuple[np.ndarray, np.ndarray]:
    """Uniform +x electric field: phi=-E x, A_x=0."""
    x = np.asarray(x, dtype=float)
    return -E * x, np.zeros_like(x)


def electric_vector_gauge(x: np.ndarray | float, t: float, E: float) -> tuple[np.ndarray, np.ndarray]:
    """Gauge-equivalent uniform +x electric field: phi=0, A_x=-E t."""
    x = np.asarray(x, dtype=float)
    return np.zeros_like(x), np.full_like(x, -E * t)


def electric_gauge_function(x: np.ndarray | float, t: float, E: float) -> np.ndarray:
    """chi=-E x t maps the scalar gauge to the time-dependent vector gauge."""
    return -E * np.asarray(x, dtype=float) * t


def gauge_phase(chi: np.ndarray | float, q: float = -1.0, hbar: float = 1.0) -> np.ndarray:
    if hbar <= 0:
        raise ValueError("hbar must be positive")
    return np.exp(1j * q * np.asarray(chi) / hbar)


def gaussian_density_1d(x: np.ndarray, *, x0: float = 0.0, sigma: float = 1.0) -> np.ndarray:
    if sigma <= 0:
        raise ValueError("sigma must be positive")
    x = np.asarray(x, dtype=float)
    rho = np.exp(-0.5 * ((x - x0) / sigma) ** 2)
    norm = np.trapezoid(rho, x)
    if norm <= 0:
        raise ValueError("grid must span a nonzero density")
    return rho / norm


def electric_currents_two_gauges(
    x: np.ndarray,
    *,
    t: float,
    E: float,
    k: float,
    q: float = -1.0,
    hbar: float = 1.0,
    m: float = 1.0,
    sigma: float = 1.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Current of one Gaussian phase profile in two gauge representations.

    The scalar-gauge phase gradient is k.  After psi' = exp(i q chi/hbar) psi,
    the vector-gauge phase gradient becomes k + q grad(chi)/hbar.  The explicit
    -q A/m term cancels the added phase gradient exactly.
    """
    if m <= 0:
        raise ValueError("m must be positive")
    rho = gaussian_density_1d(np.asarray(x, dtype=float), sigma=sigma)
    j_scalar = rho * (hbar * k) / m
    grad_chi = -E * t
    A_vector = -E * t
    j_vector = rho * (hbar * k + q * grad_chi - q * A_vector) / m
    return j_scalar, j_vector


def landau_gauge_A(x: np.ndarray | float, y: np.ndarray | float, B: float) -> tuple[np.ndarray, np.ndarray]:
    x, y = np.broadcast_arrays(np.asarray(x, dtype=float), np.asarray(y, dtype=float))
    return np.zeros_like(x), B * x


def symmetric_gauge_A(x: np.ndarray | float, y: np.ndarray | float, B: float) -> tuple[np.ndarray, np.ndarray]:
    x, y = np.broadcast_arrays(np.asarray(x, dtype=float), np.asarray(y, dtype=float))
    return -0.5 * B * y, 0.5 * B * x


def magnetic_gauge_function(x: np.ndarray | float, y: np.ndarray | float, B: float) -> np.ndarray:
    """chi=-Bxy/2 maps A_L=(0,Bx) to A_S=(-By/2,Bx/2)."""
    x, y = np.broadcast_arrays(np.asarray(x, dtype=float), np.asarray(y, dtype=float))
    return -0.5 * B * x * y


def magnetic_currents_two_gauges(
    x: np.ndarray,
    y: np.ndarray,
    *,
    B: float,
    kx: float = 0.7,
    ky: float = -0.35,
    q: float = -1.0,
    hbar: float = 1.0,
    m: float = 1.0,
    sigma: float = 1.2,
) -> tuple[tuple[np.ndarray, np.ndarray], tuple[np.ndarray, np.ndarray], np.ndarray]:
    """Gauge-invariant current for a Gaussian envelope on a 2D grid."""
    if m <= 0 or sigma <= 0:
        raise ValueError("m and sigma must be positive")
    X, Y = np.meshgrid(np.asarray(x, dtype=float), np.asarray(y, dtype=float), indexing="xy")
    rho = np.exp(-(X * X + Y * Y) / (2.0 * sigma * sigma))
    rho /= np.sum(rho)

    ALx, ALy = landau_gauge_A(X, Y, B)
    ASx, ASy = symmetric_gauge_A(X, Y, B)
    # grad chi = (-By/2, -Bx/2)
    gx = -0.5 * B * Y
    gy = -0.5 * B * X

    jLx = rho * (hbar * kx - q * ALx) / m
    jLy = rho * (hbar * ky - q * ALy) / m
    jSx = rho * (hbar * kx + q * gx - q * ASx) / m
    jSy = rho * (hbar * ky + q * gy - q * ASy) / m
    return (jLx, jLy), (jSx, jSy), rho


def landau_levels(n: np.ndarray | int, *, B: float, q: float = -1.0, hbar: float = 1.0, m: float = 1.0) -> np.ndarray:
    if m <= 0 or B == 0 or q == 0:
        raise ValueError("require m>0 and nonzero q,B")
    n = np.asarray(n, dtype=float)
    omega_c = abs(q) * abs(B) / m
    return hbar * omega_c * (n + 0.5)


def magnetic_translation_commutator_phase(
    a: tuple[float, float],
    b: tuple[float, float],
    *,
    B: float,
    q: float = -1.0,
    hbar: float = 1.0,
) -> complex:
    """Phase in T(a)T(b)=phase*T(b)T(a) for the convention used in Ch. 53."""
    ax, ay = map(float, a)
    bx, by = map(float, b)
    flux = B * (ax * by - ay * bx)
    return complex(np.exp(1j * q * flux / hbar))


def magnetic_translation_composition_phase(
    a: tuple[float, float],
    b: tuple[float, float],
    *,
    B: float,
    q: float = -1.0,
    hbar: float = 1.0,
) -> complex:
    """Phase in T(a)T(b)=phase*T(a+b)."""
    ax, ay = map(float, a)
    bx, by = map(float, b)
    flux = B * (ax * by - ay * bx)
    return complex(np.exp(0.5j * q * flux / hbar))


def flux_quantum(*, q: float = -1.0, hbar: float = 1.0) -> float:
    if q == 0 or hbar <= 0:
        raise ValueError("require nonzero q and positive hbar")
    return 2.0 * np.pi * hbar / abs(q)


def ab_phase(flux: np.ndarray | float, *, q: float = -1.0, hbar: float = 1.0) -> np.ndarray:
    return q * np.asarray(flux, dtype=float) / hbar


def ab_interference_probability(
    flux: np.ndarray | float,
    *,
    q: float = -1.0,
    hbar: float = 1.0,
    visibility: float = 1.0,
    dynamical_phase: float = 0.0,
) -> np.ndarray:
    if not 0 <= visibility <= 1:
        raise ValueError("visibility must lie in [0,1]")
    phase = dynamical_phase + ab_phase(flux, q=q, hbar=hbar)
    return 0.5 * (1.0 + visibility * np.cos(phase))


def ring_energies(
    n: np.ndarray | int,
    flux: np.ndarray | float,
    *,
    q: float = -1.0,
    hbar: float = 1.0,
    m: float = 1.0,
    R: float = 1.0,
) -> np.ndarray:
    if m <= 0 or R <= 0 or hbar <= 0:
        raise ValueError("m,R,hbar must be positive")
    n = np.asarray(n, dtype=float)
    flux = np.asarray(flux, dtype=float)
    alpha = q * flux / (2.0 * np.pi * hbar)
    return hbar**2 / (2.0 * m * R**2) * (n - alpha) ** 2


def ring_persistent_current(
    n: np.ndarray | int,
    flux: np.ndarray | float,
    *,
    q: float = -1.0,
    hbar: float = 1.0,
    m: float = 1.0,
    R: float = 1.0,
) -> np.ndarray:
    n = np.asarray(n, dtype=float)
    flux = np.asarray(flux, dtype=float)
    alpha = q * flux / (2.0 * np.pi * hbar)
    return q * hbar / (2.0 * np.pi * m * R**2) * (n - alpha)


def lowest_ring_branch(flux: np.ndarray, *, q: float = -1.0, hbar: float = 1.0, nmax: int = 8) -> tuple[np.ndarray, np.ndarray]:
    flux = np.asarray(flux, dtype=float)
    ns = np.arange(-nmax, nmax + 1)
    energies = np.vstack([ring_energies(n, flux, q=q, hbar=hbar) for n in ns])
    idx = np.argmin(energies, axis=0)
    return ns[idx], energies[idx, np.arange(flux.size)]



def pulse_vector_potential_and_field(
    t: np.ndarray | float,
    *,
    A0: float = 1.0,
    tau: float = 2.0,
    omega: float = 1.5,
) -> tuple[np.ndarray, np.ndarray]:
    """Gaussian-envelope vector-potential pulse and E=-dA/dt."""
    if tau <= 0:
        raise ValueError("tau must be positive")
    t = np.asarray(t, dtype=float)
    env = np.exp(-0.5 * (t / tau) ** 2)
    A = A0 * env * np.cos(omega * t)
    E = A0 * env * ((t / tau**2) * np.cos(omega * t) + omega * np.sin(omega * t))
    return A, E


def anharmonic_length_velocity_error(N: int, *, lam: float = 0.08) -> float:
    """Gauge-form matrix-element mismatch in a truncated oscillator basis.

    Units are hbar=m=omega=1.  For H=p^2/2+x^2/2+lam*x^4 the exact identity
    <b|p|a> = i(E_b-E_a)<b|x|a> is recovered as the basis is enlarged.
    """
    if N < 4:
        raise ValueError("N must be at least 4")
    if lam < 0:
        raise ValueError("lam must be nonnegative")
    a = np.zeros((N, N), dtype=complex)
    for n in range(1, N):
        a[n - 1, n] = np.sqrt(n)
    adag = a.conj().T
    x = (a + adag) / np.sqrt(2.0)
    p = 1j * (adag - a) / np.sqrt(2.0)
    H = 0.5 * (p @ p + x @ x) + lam * (x @ x @ x @ x)
    evals, evecs = np.linalg.eigh(H)
    v0, v1 = evecs[:, 0], evecs[:, 1]
    x10 = np.vdot(v1, x @ v0)
    p10 = np.vdot(v1, p @ v0)
    rhs = 1j * (evals[1] - evals[0]) * x10
    denom = max(abs(p10), abs(rhs), 1e-15)
    return float(abs(p10 - rhs) / denom)


def plaquette_wilson_loop(flux: np.ndarray | float, *, q: float = -1.0, hbar: float = 1.0) -> np.ndarray:
    """Gauge-invariant U(1) Wilson loop for enclosed flux."""
    if hbar <= 0 or q == 0:
        raise ValueError("require positive hbar and nonzero q")
    return np.exp(1j * q * np.asarray(flux, dtype=float) / hbar)


def ring_link_hamiltonian(
    N: int,
    total_phase: float,
    *,
    hopping: float = 1.0,
    gauge: str = "uniform",
) -> np.ndarray:
    """Nearest-neighbor ring with total Peierls phase around the loop.

    total_phase is q*Phi/hbar.  The directed transporter from site i to i+1
    is placed in H[i+1,i].
    """
    if N < 3 or hopping <= 0:
        raise ValueError("require N>=3 and positive hopping")
    if gauge not in {"uniform", "concentrated"}:
        raise ValueError("gauge must be 'uniform' or 'concentrated'")
    phases = np.zeros(N, dtype=float)
    if gauge == "uniform":
        phases[:] = total_phase / N
    else:
        phases[-1] = total_phase
    H = np.zeros((N, N), dtype=complex)
    for i in range(N):
        j = (i + 1) % N
        u = np.exp(1j * phases[i])
        H[j, i] = -hopping * u
        H[i, j] = -hopping * np.conj(u)
    return H


def local_gauge_transform(H: np.ndarray, chi: np.ndarray, *, q: float = -1.0, hbar: float = 1.0) -> np.ndarray:
    """Apply H' = G H G^dagger for site phases G_i=exp(iq chi_i/hbar)."""
    H = np.asarray(H, dtype=complex)
    chi = np.asarray(chi, dtype=float)
    if H.shape != (chi.size, chi.size):
        raise ValueError("H and chi dimensions are inconsistent")
    G = np.diag(np.exp(1j * q * chi / hbar))
    return G @ H @ G.conj().T


def ring_spectrum_link_gauge_error(N: int = 9, total_phase: float = 1.234) -> float:
    eu = np.linalg.eigvalsh(ring_link_hamiltonian(N, total_phase, gauge="uniform"))
    ec = np.linalg.eigvalsh(ring_link_hamiltonian(N, total_phase, gauge="concentrated"))
    return float(np.max(np.abs(eu - ec)))



def adiabaticity_parameter(
    lam: np.ndarray | float,
    *,
    gap: float = 0.6,
    slope: float = 1.0,
    sweep_rate: float = 0.05,
    hbar: float = 1.0,
) -> np.ndarray:
    """Local adiabaticity parameter for H=(slope*lam*sigma_z+gap*sigma_x)/2."""
    if gap <= 0 or slope <= 0 or sweep_rate < 0 or hbar <= 0:
        raise ValueError("require gap,slope,hbar>0 and sweep_rate>=0")
    lam=np.asarray(lam,dtype=float)
    G=np.sqrt((slope*lam)**2+gap**2)
    return hbar*sweep_rate*slope*gap/(2.0*G**3)


def landau_zener_probability(*, gap: float, sweep_rate: float, hbar: float = 1.0) -> float:
    """Diabatic transition estimate for H=(sweep_rate*t*sigma_z+gap*sigma_x)/2."""
    if gap <= 0 or sweep_rate <= 0 or hbar <= 0:
        raise ValueError("gap, sweep_rate, and hbar must be positive")
    return float(np.exp(-np.pi*gap**2/(2.0*hbar*sweep_rate)))


def twisted_boundary_spectrum(N: int, total_phase: float, *, hopping: float = 1.0) -> np.ndarray:
    """Ring spectrum when the entire holonomy is placed on the boundary bond."""
    return np.linalg.eigvalsh(ring_link_hamiltonian(N,total_phase,hopping=hopping,gauge="concentrated"))


def local_gauge_transform_state(psi: np.ndarray, chi: np.ndarray, *, q: float = -1.0, hbar: float = 1.0) -> np.ndarray:
    psi=np.asarray(psi,dtype=complex)
    chi=np.asarray(chi,dtype=float)
    if psi.ndim != 1 or psi.size != chi.size:
        raise ValueError("psi and chi must be one-dimensional arrays of equal size")
    return np.exp(1j*q*chi/hbar)*psi


def bond_current_matrix(H: np.ndarray, psi: np.ndarray, *, hbar: float = 1.0) -> np.ndarray:
    """Oriented probability current J[i,j] from site i to site j."""
    H=np.asarray(H,dtype=complex)
    psi=np.asarray(psi,dtype=complex)
    if hbar <= 0 or H.shape != (psi.size,psi.size):
        raise ValueError("invalid hbar or dimensions")
    z=np.conj(psi)[:,None]*H*psi[None,:]
    return -(2.0/hbar)*np.imag(z)


def schrodinger_density_derivative(H: np.ndarray, psi: np.ndarray, *, hbar: float = 1.0) -> np.ndarray:
    H=np.asarray(H,dtype=complex)
    psi=np.asarray(psi,dtype=complex)
    if hbar <= 0 or H.shape != (psi.size,psi.size):
        raise ValueError("invalid hbar or dimensions")
    return (2.0/hbar)*np.imag(np.conj(psi)*(H@psi))


def continuity_algebra_residual(H: np.ndarray, psi: np.ndarray, *, hbar: float = 1.0) -> float:
    J=bond_current_matrix(H,psi,hbar=hbar)
    dn=schrodinger_density_derivative(H,psi,hbar=hbar)
    return float(np.max(np.abs(dn+np.sum(J,axis=1))))


def exact_propagate(H: np.ndarray, psi: np.ndarray, dt: float, *, hbar: float = 1.0) -> np.ndarray:
    H=np.asarray(H,dtype=complex)
    psi=np.asarray(psi,dtype=complex)
    if hbar <= 0 or H.shape != (psi.size,psi.size):
        raise ValueError("invalid hbar or dimensions")
    e,V=np.linalg.eigh(H)
    c=V.conj().T@psi
    return V@(np.exp(-1j*e*dt/hbar)*c)


def continuity_finite_difference_residual(H: np.ndarray, psi: np.ndarray, dt: float, *, hbar: float = 1.0) -> float:
    if dt <= 0:
        raise ValueError("dt must be positive")
    pp=exact_propagate(H,psi,dt,hbar=hbar)
    pm=exact_propagate(H,psi,-dt,hbar=hbar)
    dn=(np.abs(pp)**2-np.abs(pm)**2)/(2.0*dt)
    J=bond_current_matrix(H,psi,hbar=hbar)
    return float(np.max(np.abs(dn+np.sum(J,axis=1))))


def bond_current_gauge_error(N: int = 12, total_phase: float = 0.83) -> float:
    H=ring_link_hamiltonian(N,total_phase,gauge="uniform")
    x=np.arange(N,dtype=float)
    psi=np.exp(-0.18*(x-(N-1)/2.0)**2+1j*0.47*x)
    psi=psi/np.linalg.norm(psi)
    chi=0.43*np.sin(0.7*x)+0.09*x*x/N
    J=bond_current_matrix(H,psi)
    Hp=local_gauge_transform(H,chi)
    psip=local_gauge_transform_state(psi,chi)
    Jp=bond_current_matrix(Hp,psip)
    return float(np.max(np.abs(J-Jp)))

@dataclass(frozen=True)
class GaugeDiagnostics:
    electric_current_max_difference: float
    magnetic_current_max_difference: float
    flux_quantum: float
    translation_phase_at_one_flux_quantum: complex
    ab_periodicity_max_difference: float
    ring_relabel_max_difference: float
    lattice_ring_gauge_spectrum_max_difference: float
    wilson_one_flux_max_difference: float
    length_velocity_error_N8: float
    length_velocity_error_N32: float
    adiabatic_eta_slow: float
    adiabatic_eta_fast: float
    landau_zener_slow: float
    landau_zener_fast: float
    twisted_boundary_spectrum_max_difference: float
    bond_current_gauge_max_difference: float
    continuity_algebra_max_residual: float
    continuity_fd_dt_1e2: float
    continuity_fd_dt_5e3: float


def diagnostics() -> GaugeDiagnostics:
    q = -1.0
    hbar = 1.0
    x = np.linspace(-5.0, 5.0, 1201)
    je1, je2 = electric_currents_two_gauges(x, t=0.8, E=0.55, k=1.1, q=q, hbar=hbar)
    eerr = float(np.max(np.abs(je1 - je2)))

    xy = np.linspace(-3.0, 3.0, 81)
    (jlx, jly), (jsx, jsy), _ = magnetic_currents_two_gauges(xy, xy, B=0.7, q=q, hbar=hbar)
    berr = float(max(np.max(np.abs(jlx - jsx)), np.max(np.abs(jly - jsy))))

    phi0 = flux_quantum(q=q, hbar=hbar)
    phase1 = magnetic_translation_commutator_phase((1.0, 0.0), (0.0, phi0 / 0.7), B=0.7, q=q, hbar=hbar)

    f = np.linspace(-0.7 * phi0, 0.7 * phi0, 301)
    p1 = ab_interference_probability(f, q=q, hbar=hbar, visibility=0.83, dynamical_phase=0.27)
    p2 = ab_interference_probability(f + phi0, q=q, hbar=hbar, visibility=0.83, dynamical_phase=0.27)
    perr = float(np.max(np.abs(p1 - p2)))

    # E_n(Phi+Phi0)=E_{n-sign(q)}(Phi).
    n = np.arange(-4, 5)
    test_flux = 0.31 * phi0
    s = int(np.sign(q))
    rerr = float(np.max(np.abs(
        ring_energies(n, test_flux + phi0, q=q, hbar=hbar)
        - ring_energies(n - s, test_flux, q=q, hbar=hbar)
    )))

    lerr = ring_spectrum_link_gauge_error(N=11, total_phase=0.73)
    werr = float(abs(plaquette_wilson_loop(phi0, q=q, hbar=hbar) - 1.0))
    g8 = anharmonic_length_velocity_error(8)
    g32 = anharmonic_length_velocity_error(32)

    eta_s=float(adiabaticity_parameter(0.0,gap=0.6,slope=1.0,sweep_rate=0.01))
    eta_f=float(adiabaticity_parameter(0.0,gap=0.6,slope=1.0,sweep_rate=0.08))
    lz_s=landau_zener_probability(gap=0.6,sweep_rate=0.01)
    lz_f=landau_zener_probability(gap=0.6,sweep_rate=0.08)
    twist_err=float(np.max(np.abs(
        np.linalg.eigvalsh(ring_link_hamiltonian(12,0.91,gauge="uniform"))
        - twisted_boundary_spectrum(12,0.91)
    )))
    current_err=bond_current_gauge_error(12,0.83)
    Hc=ring_link_hamiltonian(11,0.64,gauge="uniform")
    xx=np.arange(11,dtype=float)
    psic=np.exp(-0.12*(xx-5.0)**2+1j*0.38*xx); psic/=np.linalg.norm(psic)
    cont_alg=continuity_algebra_residual(Hc,psic)
    cont_1=continuity_finite_difference_residual(Hc,psic,1e-2)
    cont_2=continuity_finite_difference_residual(Hc,psic,5e-3)

    return GaugeDiagnostics(eerr, berr, phi0, phase1, perr, rerr, lerr, werr, g8, g32,
        eta_s, eta_f, lz_s, lz_f, twist_err, current_err, cont_alg, cont_1, cont_2)
