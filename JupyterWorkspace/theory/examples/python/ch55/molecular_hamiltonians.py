"""Deterministic quantitative companion for Chapter 55 launch (Commit 603)."""
from __future__ import annotations

import math
import numpy as np

ELECTRON_MASS_U = 5.48579909065e-4


def reduced_mass(m1: float, m2: float) -> float:
    if m1 <= 0 or m2 <= 0:
        raise ValueError("masses must be positive")
    return m1 * m2 / (m1 + m2)


def bo_velocity_ratio(nuclear_mass_in_electron_masses: float) -> float:
    """Characteristic electronic/nuclear velocity-scale parameter sqrt(m_e/M)."""
    if nuclear_mass_in_electron_masses <= 0:
        raise ValueError("nuclear mass must be positive")
    return 1.0 / math.sqrt(nuclear_mass_in_electron_masses)


def morse_potential(r, de: float, a: float, re: float):
    if de <= 0 or a <= 0 or re <= 0:
        raise ValueError("D_e, a, and R_e must be positive")
    r = np.asarray(r, dtype=float)
    return de * (1.0 - np.exp(-a * (r - re))) ** 2 - de


def morse_curvature(de: float, a: float) -> float:
    if de <= 0 or a <= 0:
        raise ValueError("D_e and a must be positive")
    return 2.0 * de * a * a


def harmonic_angular_frequency_from_curvature(k: float, mu: float) -> float:
    if k <= 0 or mu <= 0:
        raise ValueError("k and mu must be positive")
    return math.sqrt(k / mu)


def morse_local_angular_frequency(de: float, a: float, mu: float) -> float:
    return harmonic_angular_frequency_from_curvature(morse_curvature(de, a), mu)


def lcao_normalizations(overlap: float) -> tuple[float, float]:
    if not (-1.0 < overlap < 1.0):
        raise ValueError("overlap must satisfy -1 < S < 1")
    ng = 1.0 / math.sqrt(2.0 * (1.0 + overlap))
    nu = 1.0 / math.sqrt(2.0 * (1.0 - overlap))
    return ng, nu


def two_center_lcao_energies(alpha: float, beta: float, overlap: float) -> tuple[float, float]:
    """Return energies of symmetric (g) and antisymmetric (u) LCAO states."""
    if not (-1.0 < overlap < 1.0):
        raise ValueError("overlap must satisfy -1 < S < 1")
    eg = (alpha + beta) / (1.0 + overlap)
    eu = (alpha - beta) / (1.0 - overlap)
    return eg, eu


def two_center_matrices(alpha: float, beta: float, overlap: float) -> tuple[np.ndarray, np.ndarray]:
    if not (-1.0 < overlap < 1.0):
        raise ValueError("overlap must satisfy -1 < S < 1")
    h = np.array([[alpha, beta], [beta, alpha]], dtype=float)
    s = np.array([[1.0, overlap], [overlap, 1.0]], dtype=float)
    return h, s


def generalized_residual(alpha: float, beta: float, overlap: float, parity: str) -> float:
    h, s = two_center_matrices(alpha, beta, overlap)
    eg, eu = two_center_lcao_energies(alpha, beta, overlap)
    if parity == "g":
        c, e = np.array([1.0, 1.0]), eg
    elif parity == "u":
        c, e = np.array([1.0, -1.0]), eu
    else:
        raise ValueError("parity must be 'g' or 'u'")
    return float(np.linalg.norm(h @ c - e * (s @ c)))


def isotope_frequency_ratio(mu_light: float, mu_heavy: float) -> float:
    """omega_heavy/omega_light for the same Born-Oppenheimer curvature."""
    if mu_light <= 0 or mu_heavy <= 0:
        raise ValueError("reduced masses must be positive")
    return math.sqrt(mu_light / mu_heavy)


def hellmann_feynman_finite_difference(energies, coordinates, index: int) -> float:
    """Centered finite-difference dE/dR for a sampled PES."""
    e = np.asarray(energies, dtype=float)
    r = np.asarray(coordinates, dtype=float)
    if e.ndim != 1 or r.ndim != 1 or e.size != r.size:
        raise ValueError("energies and coordinates must be equal-length 1D arrays")
    if not (0 < index < e.size - 1):
        raise ValueError("index must have neighbors on both sides")
    return float((e[index + 1] - e[index - 1]) / (r[index + 1] - r[index - 1]))


def generalized_eigensystem(h, s) -> tuple[np.ndarray, np.ndarray]:
    """Solve H c = E S c for real symmetric H and positive-definite S.

    Returns ascending eigenvalues and columns of S-orthonormal eigenvectors.
    """
    h = np.asarray(h, dtype=float)
    s = np.asarray(s, dtype=float)
    if h.ndim != 2 or s.ndim != 2 or h.shape != s.shape or h.shape[0] != h.shape[1]:
        raise ValueError("H and S must be equal-size square matrices")
    if not np.allclose(h, h.T, atol=1e-12) or not np.allclose(s, s.T, atol=1e-12):
        raise ValueError("H and S must be symmetric")
    se, su = np.linalg.eigh(s)
    if np.min(se) <= 1e-12:
        raise ValueError("overlap matrix must be positive definite")
    x = (su * (1.0 / np.sqrt(se))) @ su.T
    hp = x.T @ h @ x
    e, u = np.linalg.eigh(hp)
    c = x @ u
    # Canonicalize eigenvector signs for deterministic diagnostics.
    for j in range(c.shape[1]):
        i = int(np.argmax(np.abs(c[:, j])))
        if c[i, j] < 0:
            c[:, j] *= -1.0
    return e, c


def generalized_eigen_residuals(h, s, energies, coefficients) -> np.ndarray:
    h = np.asarray(h, dtype=float)
    s = np.asarray(s, dtype=float)
    e = np.asarray(energies, dtype=float)
    c = np.asarray(coefficients, dtype=float)
    if c.ndim != 2 or e.ndim != 1 or c.shape[1] != e.size:
        raise ValueError("coefficient columns must match the energy array")
    return np.array([np.linalg.norm(h @ c[:, j] - e[j] * (s @ c[:, j])) for j in range(e.size)])


def heteronuclear_two_center(alpha_a: float, alpha_b: float, coupling: float, overlap: float = 0.0):
    """Two-center generalized eigenproblem with unequal on-site energies."""
    if not (-1.0 < overlap < 1.0):
        raise ValueError("overlap must satisfy -1 < S < 1")
    h = np.array([[alpha_a, coupling], [coupling, alpha_b]], dtype=float)
    s = np.array([[1.0, overlap], [overlap, 1.0]], dtype=float)
    e, c = generalized_eigensystem(h, s)
    return e, c, h, s


def mulliken_populations(coefficients, overlap_matrix) -> np.ndarray:
    """Return one-orbital Mulliken gross populations for a real coefficient vector."""
    c = np.asarray(coefficients, dtype=float)
    s = np.asarray(overlap_matrix, dtype=float)
    if c.ndim != 1 or s.ndim != 2 or s.shape != (c.size, c.size):
        raise ValueError("coefficient vector and overlap matrix dimensions do not match")
    norm = float(c @ s @ c)
    if norm <= 0:
        raise ValueError("S norm must be positive")
    c = c / math.sqrt(norm)
    return c * (s @ c)


def bond_order(n_bonding: float, n_antibonding: float) -> float:
    if n_bonding < 0 or n_antibonding < 0:
        raise ValueError("orbital occupations cannot be negative")
    return 0.5 * (n_bonding - n_antibonding)


def diatomic_orbital_family(lambda_abs: int) -> str:
    if int(lambda_abs) != lambda_abs or lambda_abs < 0:
        raise ValueError("Lambda must be a nonnegative integer")
    names = {0: "sigma", 1: "pi", 2: "delta", 3: "phi"}
    return names.get(int(lambda_abs), f"Lambda={int(lambda_abs)}")


def heitler_london_normalizations(overlap: float) -> tuple[float, float]:
    """Normalization constants for symmetric and antisymmetric AB +/- BA products."""
    if not (-1.0 < overlap < 1.0):
        raise ValueError("overlap must satisfy -1 < S < 1")
    ns = 1.0 / math.sqrt(2.0 * (1.0 + overlap * overlap))
    nt = 1.0 / math.sqrt(2.0 * (1.0 - overlap * overlap))
    return ns, nt


def minimal_ci_ground(e_g2: float, e_u2: float, coupling: float) -> tuple[float, np.ndarray]:
    """Ground eigenpair of the |g^2>, |u^2> singlet two-configuration Hamiltonian."""
    h = np.array([[e_g2, coupling], [coupling, e_u2]], dtype=float)
    e, c = np.linalg.eigh(h)
    vec = c[:, 0].copy()
    i = int(np.argmax(np.abs(vec)))
    if vec[i] < 0:
        vec *= -1.0
    return float(e[0]), vec


def mass_weighted_hessian(hessian, masses) -> np.ndarray:
    """Return M^{-1/2} K M^{-1/2} for Cartesian-coordinate masses."""
    k = np.asarray(hessian, dtype=float)
    m = np.asarray(masses, dtype=float)
    if k.ndim != 2 or k.shape[0] != k.shape[1]:
        raise ValueError("hessian must be square")
    if not np.allclose(k, k.T, atol=1e-12):
        raise ValueError("hessian must be symmetric")
    if m.ndim != 1 or m.size != k.shape[0]:
        raise ValueError("masses must have one positive entry per coordinate")
    if np.any(m <= 0):
        raise ValueError("masses must be positive")
    d = 1.0 / np.sqrt(m)
    return d[:, None] * k * d[None, :]


def normal_modes(hessian, masses, negative_tolerance: float = 1e-10) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Diagonalize a stable mass-weighted Hessian.

    Returns angular frequencies, orthonormal mass-weighted eigenvectors, and
    Cartesian displacement eigenvectors. Small negative numerical eigenvalues
    are clipped to zero; a genuine negative curvature raises ValueError.
    """
    if negative_tolerance < 0:
        raise ValueError("negative_tolerance must be nonnegative")
    f = mass_weighted_hessian(hessian, masses)
    lam, l = np.linalg.eigh(f)
    if np.min(lam) < -negative_tolerance:
        raise ValueError("hessian contains an unstable negative-curvature mode")
    lam = np.where(lam < 0.0, 0.0, lam)
    omega = np.sqrt(lam)
    m = np.asarray(masses, dtype=float)
    cart = (1.0 / np.sqrt(m))[:, None] * l
    for j in range(l.shape[1]):
        i = int(np.argmax(np.abs(l[:, j])))
        if l[i, j] < 0:
            l[:, j] *= -1.0
            cart[:, j] *= -1.0
    return omega, l, cart


def vibrational_mode_count(n_atoms: int, linear: bool) -> int:
    if int(n_atoms) != n_atoms or n_atoms < 2:
        raise ValueError("a molecular vibration count requires at least two atoms")
    n = int(n_atoms)
    if linear:
        return 3 * n - 5
    if n < 3:
        raise ValueError("a two-atom molecule is necessarily linear")
    return 3 * n - 6


def harmonic_levels(omega: float, n_levels: int, hbar: float = 1.0) -> np.ndarray:
    if omega <= 0 or hbar <= 0:
        raise ValueError("omega and hbar must be positive")
    if int(n_levels) != n_levels or n_levels < 1:
        raise ValueError("n_levels must be a positive integer")
    v = np.arange(int(n_levels), dtype=float)
    return hbar * omega * (v + 0.5)


def harmonic_zero_point_energy(frequencies, hbar: float = 1.0, zero_tolerance: float = 1e-12) -> float:
    w = np.asarray(frequencies, dtype=float)
    if w.ndim != 1 or np.any(w < -zero_tolerance):
        raise ValueError("frequencies must be a 1D nonnegative array")
    if hbar <= 0 or zero_tolerance < 0:
        raise ValueError("hbar must be positive and tolerance nonnegative")
    w = np.where(np.abs(w) <= zero_tolerance, 0.0, w)
    return float(0.5 * hbar * np.sum(w))


def morse_bound_state_count(de: float, a: float, mu: float, hbar: float = 1.0) -> int:
    if de <= 0 or a <= 0 or mu <= 0 or hbar <= 0:
        raise ValueError("D_e, a, mu, and hbar must be positive")
    lam = math.sqrt(2.0 * mu * de) / (hbar * a)
    if lam <= 0.5:
        return 0
    # Bound integers satisfy v + 1/2 < lambda. Subtract a tiny tolerance so
    # an exactly threshold state is not counted as bound.
    vmax = math.floor(lam - 0.5 - 1e-12)
    return max(0, vmax + 1)


def morse_bound_energies(de: float, a: float, mu: float, hbar: float = 1.0) -> np.ndarray:
    """Exact Morse bound energies measured upward from the well minimum."""
    n = morse_bound_state_count(de, a, mu, hbar)
    if n == 0:
        return np.empty(0, dtype=float)
    omega = a * math.sqrt(2.0 * de / mu)
    vhalf = np.arange(n, dtype=float) + 0.5
    return hbar * omega * vhalf - (hbar * hbar * a * a / (2.0 * mu)) * vhalf * vhalf


def dissociation_energy_from_ground(de: float, ground_energy_from_bottom: float) -> float:
    if de <= 0 or ground_energy_from_bottom < 0 or ground_energy_from_bottom >= de:
        raise ValueError("require 0 <= ground energy < D_e")
    return de - ground_energy_from_bottom


def mode_participation_ratio(mode) -> float:
    v = np.asarray(mode, dtype=float)
    if v.ndim != 1 or v.size == 0:
        raise ValueError("mode must be a nonempty 1D vector")
    n = float(v @ v)
    if n <= 0:
        raise ValueError("mode norm must be positive")
    u = v / math.sqrt(n)
    return float(1.0 / np.sum(u**4))


def mode_overlap_matrix(modes_a, modes_b) -> np.ndarray:
    a = np.asarray(modes_a, dtype=float)
    b = np.asarray(modes_b, dtype=float)
    if a.ndim != 2 or b.ndim != 2 or a.shape[0] != b.shape[0]:
        raise ValueError("mode matrices must share the same coordinate dimension")
    if not np.allclose(a.T @ a, np.eye(a.shape[1]), atol=1e-10):
        raise ValueError("modes_a columns must be orthonormal")
    if not np.allclose(b.T @ b, np.eye(b.shape[1]), atol=1e-10):
        raise ValueError("modes_b columns must be orthonormal")
    return a.T @ b


def duschinsky_transform(q, rotation, displacement) -> np.ndarray:
    q = np.asarray(q, dtype=float)
    j = np.asarray(rotation, dtype=float)
    k = np.asarray(displacement, dtype=float)
    if q.ndim != 1 or k.ndim != 1 or j.ndim != 2 or j.shape != (q.size, q.size) or k.size != q.size:
        raise ValueError("Duschinsky dimensions do not match")
    if not np.allclose(j.T @ j, np.eye(q.size), atol=1e-10):
        raise ValueError("Duschinsky rotation must be orthogonal")
    return j @ q + k

# Commit 606: rotational Hamiltonians and rovibrational coupling.
def rotational_constant(moment_of_inertia: float, hbar: float = 1.0) -> float:
    if moment_of_inertia <= 0 or hbar <= 0:
        raise ValueError("moment of inertia and hbar must be positive")
    return hbar * hbar / (2.0 * moment_of_inertia)


def diatomic_moment_of_inertia(m1: float, m2: float, bond_length: float) -> float:
    if bond_length <= 0:
        raise ValueError("bond length must be positive")
    return reduced_mass(m1, m2) * bond_length * bond_length


def rigid_rotor_levels(B: float, j_max: int) -> np.ndarray:
    if B <= 0:
        raise ValueError("B must be positive")
    if int(j_max) != j_max or j_max < 0:
        raise ValueError("j_max must be a nonnegative integer")
    j = np.arange(int(j_max) + 1, dtype=float)
    return B * j * (j + 1.0)


def rotational_degeneracy(J: int) -> int:
    if int(J) != J or J < 0:
        raise ValueError("J must be a nonnegative integer")
    return 2 * int(J) + 1


def rotational_isotope_ratio(mu_light: float, mu_heavy: float, r_light: float = 1.0, r_heavy: float = 1.0) -> float:
    """B_heavy/B_light for two isotopologues."""
    if min(mu_light, mu_heavy, r_light, r_heavy) <= 0:
        raise ValueError("masses and bond lengths must be positive")
    return (mu_light * r_light * r_light) / (mu_heavy * r_heavy * r_heavy)


def symmetric_top_energy(A: float, B: float, J: int, K: int) -> float:
    if A <= 0 or B <= 0:
        raise ValueError("rotational constants must be positive")
    if int(J) != J or J < 0 or int(K) != K or abs(K) > J:
        raise ValueError("require integer J>=0 and |K|<=J")
    return B * J * (J + 1) + (A - B) * K * K


def centrifugal_distorted_levels(B: float, D: float, j_max: int) -> np.ndarray:
    if B <= 0 or D < 0:
        raise ValueError("require B>0 and D>=0")
    if int(j_max) != j_max or j_max < 0:
        raise ValueError("j_max must be a nonnegative integer")
    j = np.arange(int(j_max) + 1, dtype=float)
    x = j * (j + 1.0)
    return B * x - D * x * x


def vibration_dependent_rotational_constant(B_e: float, alpha_e: float, v: int) -> float:
    if B_e <= 0 or alpha_e < 0:
        raise ValueError("require B_e>0 and alpha_e>=0")
    if int(v) != v or v < 0:
        raise ValueError("v must be a nonnegative integer")
    b = B_e - alpha_e * (v + 0.5)
    if b <= 0:
        raise ValueError("parameters produce a nonpositive B_v")
    return b


def rovibrational_term_value(G_v: float, B_v: float, J: int, D_v: float = 0.0) -> float:
    if B_v <= 0 or D_v < 0:
        raise ValueError("require B_v>0 and D_v>=0")
    if int(J) != J or J < 0:
        raise ValueError("J must be a nonnegative integer")
    x = float(J * (J + 1))
    return float(G_v + B_v * x - D_v * x * x)


def diatomic_pr_branch_positions(band_origin: float, B_lower: float, B_upper: float, j_max: int) -> dict[str, np.ndarray]:
    """Ideal P/R line positions for v->v' using rigid upper/lower rotational constants.

    P lines originate from lower J=1..j_max and terminate at J'=J-1.
    R lines originate from lower J=0..j_max and terminate at J'=J+1.
    """
    if B_lower <= 0 or B_upper <= 0:
        raise ValueError("rotational constants must be positive")
    if int(j_max) != j_max or j_max < 1:
        raise ValueError("j_max must be a positive integer")
    p=[]
    for J in range(1, int(j_max)+1):
        p.append(band_origin + B_upper*(J-1)*J - B_lower*J*(J+1))
    r=[]
    for J in range(0, int(j_max)+1):
        r.append(band_origin + B_upper*(J+1)*(J+2) - B_lower*J*(J+1))
    return {"P": np.asarray(p,float), "R": np.asarray(r,float)}


# ---------------------------------------------------------------------------
# Commit 607 -- IR/Raman and quantitative rovibrational spectroscopy
# ---------------------------------------------------------------------------

import math as _math607

_C2_CM_K_607 = 1.438776877  # h c / k_B in cm K
_EPS0_607 = 8.8541878128e-12
_HBAR_607 = 1.054571817e-34
_C_607 = 299792458.0


def vibrational_term_cm(v, omega_e_cm, omega_exe_cm=0.0):
    """Dunham/Morse-leading vibrational term value in cm^-1."""
    if v < 0 or int(v) != v:
        raise ValueError("v must be a nonnegative integer")
    x = float(v) + 0.5
    return float(omega_e_cm) * x - float(omega_exe_cm) * x * x


def vibration_rotation_constant_cm(B_e_cm, alpha_e_cm, v):
    """B_v = B_e - alpha_e (v + 1/2), in cm^-1."""
    if v < 0 or int(v) != v:
        raise ValueError("v must be a nonnegative integer")
    return float(B_e_cm) - float(alpha_e_cm) * (float(v) + 0.5)


def rotational_term_cm(J, B_cm, D_cm=0.0):
    """F(J)=B J(J+1)-D[J(J+1)]^2, in cm^-1."""
    if J < 0 or int(J) != J:
        raise ValueError("J must be a nonnegative integer")
    q = float(J) * (float(J) + 1.0)
    return float(B_cm) * q - float(D_cm) * q * q


def pure_rotational_lines_cm(B_cm, Jmax, D_cm=0.0):
    """Absorption line positions J -> J+1 for J=0..Jmax."""
    if Jmax < 0:
        raise ValueError("Jmax must be nonnegative")
    out = []
    for J in range(int(Jmax) + 1):
        nu = rotational_term_cm(J + 1, B_cm, D_cm) - rotational_term_cm(J, B_cm, D_cm)
        out.append((J, J + 1, nu))
    return out


def rovibrational_pr_lines_cm(nu0_cm, B_lower_cm, B_upper_cm, Jmax,
                              D_lower_cm=0.0, D_upper_cm=0.0):
    """P/R line positions for a simple parallel-band diatomic model.

    Returns {"P": [(J, J-1, nu), ...], "R": [(J, J+1, nu), ...]}.
    No universal Q branch is inserted: its existence depends on angular/electronic symmetry.
    """
    if Jmax < 0:
        raise ValueError("Jmax must be nonnegative")
    P, R = [], []
    for J in range(int(Jmax) + 1):
        Fl = rotational_term_cm(J, B_lower_cm, D_lower_cm)
        FuR = rotational_term_cm(J + 1, B_upper_cm, D_upper_cm)
        R.append((J, J + 1, float(nu0_cm) + FuR - Fl))
        if J >= 1:
            FuP = rotational_term_cm(J - 1, B_upper_cm, D_upper_cm)
            P.append((J, J - 1, float(nu0_cm) + FuP - Fl))
    return {"P": P, "R": R}


def ir_activity_strength(dmu_dq):
    """Simple IR activity proxy |d mu/dQ|^2 for scalar/vector derivatives."""
    if isinstance(dmu_dq, (int, float, complex)):
        return float(abs(dmu_dq) ** 2)
    return float(sum(abs(x) ** 2 for x in dmu_dq))


def raman_activity_strength(dalpha_dq):
    """Simple positive Raman activity proxy: Frobenius norm squared of d alpha/dQ."""
    if isinstance(dalpha_dq, (int, float, complex)):
        return float(abs(dalpha_dq) ** 2)
    total = 0.0
    for row in dalpha_dq:
        if isinstance(row, (int, float, complex)):
            total += abs(row) ** 2
        else:
            total += sum(abs(x) ** 2 for x in row)
    return float(total)


def honl_london_sigma_sigma(J, branch):
    """Normalized simple 1Sigma-1Sigma P/R HĂ¶nl--London factors."""
    if J < 0 or int(J) != J:
        raise ValueError("J must be a nonnegative integer")
    b = str(branch).upper()
    den = 2.0 * float(J) + 1.0
    if b == "P":
        return 0.0 if J == 0 else float(J) / den
    if b == "R":
        return (float(J) + 1.0) / den
    raise ValueError("branch must be P or R")


def rotational_boltzmann_populations(B_cm, temperature_K, Jmax, D_cm=0.0):
    """Normalized rigid/nonrigid linear-rotor populations p_J."""
    if temperature_K <= 0:
        raise ValueError("temperature_K must be positive")
    if Jmax < 0:
        raise ValueError("Jmax must be nonnegative")
    weights = []
    for J in range(int(Jmax) + 1):
        F = rotational_term_cm(J, B_cm, D_cm)
        w = (2 * J + 1) * _math607.exp(-_C2_CM_K_607 * F / float(temperature_K))
        weights.append(w)
    z = sum(weights)
    return [w / z for w in weights]


def rovibrational_stick_spectrum(nu0_cm, B_lower_cm, B_upper_cm, temperature_K,
                                 Jmax, D_lower_cm=0.0, D_upper_cm=0.0,
                                 transition_moment_sq=1.0):
    """Simple thermal P/R stick spectrum: (center_cm, strength, branch, Jlower)."""
    lines = rovibrational_pr_lines_cm(
        nu0_cm, B_lower_cm, B_upper_cm, Jmax, D_lower_cm, D_upper_cm
    )
    pops = rotational_boltzmann_populations(B_lower_cm, temperature_K, Jmax, D_lower_cm)
    sticks = []
    for J, Jp, nu in lines["P"]:
        s = pops[J] * honl_london_sigma_sigma(J, "P") * float(transition_moment_sq)
        sticks.append((nu, s, "P", J))
    for J, Jp, nu in lines["R"]:
        s = pops[J] * honl_london_sigma_sigma(J, "R") * float(transition_moment_sq)
        sticks.append((nu, s, "R", J))
    sticks.sort(key=lambda x: x[0])
    return sticks


def einstein_A_electric_dipole(frequency_Hz, dipole_Cm):
    """Nondegenerate electric-dipole spontaneous-emission rate A in s^-1."""
    if frequency_Hz < 0:
        raise ValueError("frequency_Hz must be nonnegative")
    omega = 2.0 * _math607.pi * float(frequency_Hz)
    return (omega ** 3) * (abs(dipole_Cm) ** 2) / (
        3.0 * _math607.pi * _EPS0_607 * _HBAR_607 * (_C_607 ** 3)
    )


def radiative_lifetime_and_branching(rates_s):
    """Return (lifetime_s, normalized_branching_list) for positive partial rates."""
    rates = [float(x) for x in rates_s]
    if any(x < 0 for x in rates):
        raise ValueError("rates must be nonnegative")
    total = sum(rates)
    if total <= 0:
        raise ValueError("at least one rate must be positive")
    return 1.0 / total, [x / total for x in rates]


def gaussian_profile(x, center=0.0, fwhm=1.0):
    """Normalized Gaussian line profile evaluated at x."""
    if fwhm <= 0:
        raise ValueError("fwhm must be positive")
    sigma = float(fwhm) / (2.0 * _math607.sqrt(2.0 * _math607.log(2.0)))
    z = (float(x) - float(center)) / sigma
    return _math607.exp(-0.5 * z * z) / (sigma * _math607.sqrt(2.0 * _math607.pi))


def lorentzian_profile(x, center=0.0, fwhm=1.0):
    """Normalized Lorentzian line profile evaluated at x."""
    if fwhm <= 0:
        raise ValueError("fwhm must be positive")
    h = 0.5 * float(fwhm)
    dx = float(x) - float(center)
    return (h / _math607.pi) / (dx * dx + h * h)


def broaden_stick_spectrum(grid, sticks, fwhm, kind="gaussian"):
    """Broaden [(center,strength), ...] onto a supplied frequency/wavenumber grid."""
    fn = gaussian_profile if str(kind).lower().startswith("g") else lorentzian_profile
    out = []
    for x in grid:
        out.append(sum(float(s) * fn(float(x), float(c), fwhm) for c, s in sticks))
    return out

# COMMIT608_VIBRONIC_BEGIN
def franck_condon_0n(n, huang_rhys):
    """Franck--Condon factor |<n|0>|^2 for equal-frequency displaced oscillators."""
    import math
    n = int(n)
    S = float(huang_rhys)
    if n < 0:
        raise ValueError("n must be nonnegative")
    if S < 0.0:
        raise ValueError("Huang--Rhys factor must be nonnegative")
    return math.exp(-S) * (S ** n) / math.factorial(n)


def franck_condon_progression(huang_rhys, nmax):
    import numpy as np
    nmax = int(nmax)
    if nmax < 0:
        raise ValueError("nmax must be nonnegative")
    return np.asarray([franck_condon_0n(n, huang_rhys) for n in range(nmax + 1)], dtype=float)


def displaced_oscillator_0n_amplitude(n, huang_rhys):
    import math
    n = int(n)
    S = float(huang_rhys)
    if n < 0 or S < 0.0:
        raise ValueError("n and Huang--Rhys factor must be nonnegative")
    return math.exp(-0.5 * S) * ((-math.sqrt(S)) ** n) / math.sqrt(math.factorial(n))


def huang_rhys_from_dimensionless_displacement(delta_q):
    dq = float(delta_q)
    return 0.5 * dq * dq


def dimensionless_displacement_from_huang_rhys(huang_rhys):
    import math
    S = float(huang_rhys)
    if S < 0.0:
        raise ValueError("Huang--Rhys factor must be nonnegative")
    return math.sqrt(2.0 * S)


def multimode_fc_zero_to_state(quanta, huang_rhys):
    import numpy as np
    q = np.asarray(quanta, dtype=int)
    S = np.asarray(huang_rhys, dtype=float)
    if q.ndim != 1 or S.ndim != 1 or q.size != S.size:
        raise ValueError("quanta and huang_rhys must be one-dimensional arrays of equal length")
    if np.any(q < 0) or np.any(S < 0.0):
        raise ValueError("quanta and Huang--Rhys factors must be nonnegative")
    out = 1.0
    for ni, si in zip(q.tolist(), S.tolist()):
        out *= franck_condon_0n(int(ni), float(si))
    return float(out)


def thermal_vibrational_populations(theta_over_T, nmax):
    import numpy as np
    x = float(theta_over_T)
    nmax = int(nmax)
    if x <= 0.0:
        raise ValueError("theta_over_T must be positive")
    if nmax < 0:
        raise ValueError("nmax must be nonnegative")
    r = float(np.exp(-x))
    n = np.arange(nmax + 1, dtype=float)
    return (1.0 - r) * (r ** n)


def harmonic_vibrational_partition(theta_over_T):
    import math
    x = float(theta_over_T)
    if x <= 0.0:
        raise ValueError("theta_over_T must be positive")
    return 1.0 / (1.0 - math.exp(-x))


def duschinsky_transform(q, J, K):
    import numpy as np
    q = np.asarray(q, dtype=float)
    J = np.asarray(J, dtype=float)
    K = np.asarray(K, dtype=float)
    if q.ndim != 1 or K.ndim != 1 or J.ndim != 2:
        raise ValueError("q and K must be vectors and J a matrix")
    if J.shape != (q.size, q.size) or K.size != q.size:
        raise ValueError("incompatible Duschinsky dimensions")
    return J @ q + K


def duschinsky_inverse(q_prime, J, K):
    import numpy as np
    qp = np.asarray(q_prime, dtype=float)
    J = np.asarray(J, dtype=float)
    K = np.asarray(K, dtype=float)
    if qp.ndim != 1 or K.ndim != 1 or J.ndim != 2:
        raise ValueError("q_prime and K must be vectors and J a matrix")
    if J.shape != (qp.size, qp.size) or K.size != qp.size:
        raise ValueError("incompatible Duschinsky dimensions")
    return J.T @ (qp - K)


def duschinsky_orthogonality_error(J):
    import numpy as np
    J = np.asarray(J, dtype=float)
    if J.ndim != 2 or J.shape[0] != J.shape[1]:
        raise ValueError("J must be square")
    I = np.eye(J.shape[0])
    return float(np.linalg.norm(J.T @ J - I, ord="fro"))


def is_orthogonal_duschinsky(J, tol=1e-10):
    return duschinsky_orthogonality_error(J) <= float(tol)


def condon_intensity(mu0, fc_factor):
    fc = float(fc_factor)
    if fc < 0.0:
        raise ValueError("Franck--Condon factor must be nonnegative")
    return float(abs(mu0) ** 2 * fc)


def herzberg_teller_moment(mu0, dipole_gradient, q_matrix_element):
    return mu0 + dipole_gradient * q_matrix_element


def herzberg_teller_intensity(mu0, dipole_gradient, q_matrix_element):
    m = herzberg_teller_moment(mu0, dipole_gradient, q_matrix_element)
    return float(abs(m) ** 2)


def vibronic_stick_spectrum_0n(origin_cm, mode_cm, huang_rhys, nmax, scale=1.0):
    import numpy as np
    nmax = int(nmax)
    if nmax < 0 or float(mode_cm) <= 0.0:
        raise ValueError("nmax must be nonnegative and mode_cm positive")
    n = np.arange(nmax + 1, dtype=float)
    pos = float(origin_cm) + float(mode_cm) * n
    strength = float(scale) * franck_condon_progression(huang_rhys, nmax)
    return pos, strength


def multimode_vibronic_sticks(origin_cm, mode_cm, huang_rhys, max_quanta):
    import itertools
    import numpy as np
    w = np.asarray(mode_cm, dtype=float)
    S = np.asarray(huang_rhys, dtype=float)
    mq = int(max_quanta)
    if w.ndim != 1 or S.ndim != 1 or w.size != S.size or w.size == 0:
        raise ValueError("mode_cm and huang_rhys must be nonempty equal-length vectors")
    if np.any(w <= 0.0) or np.any(S < 0.0) or mq < 0:
        raise ValueError("invalid frequencies, Huang--Rhys factors, or max_quanta")
    states = list(itertools.product(range(mq + 1), repeat=w.size))
    pos, strength = [], []
    for st in states:
        q = np.asarray(st, dtype=int)
        pos.append(float(origin_cm + np.dot(w, q)))
        strength.append(multimode_fc_zero_to_state(q, S))
    return np.asarray(pos), np.asarray(strength), np.asarray(states, dtype=int)


def gaussian_broaden_vibronic_spectrum(grid_cm, positions_cm, strengths, sigma_cm):
    import numpy as np
    x = np.asarray(grid_cm, dtype=float)
    p = np.asarray(positions_cm, dtype=float)
    s = np.asarray(strengths, dtype=float)
    sigma = float(sigma_cm)
    if x.ndim != 1 or p.ndim != 1 or s.ndim != 1 or p.size != s.size:
        raise ValueError("grid, positions, and strengths must be compatible vectors")
    if sigma <= 0.0 or np.any(s < 0.0):
        raise ValueError("sigma must be positive and strengths nonnegative")
    y = np.zeros_like(x)
    norm = 1.0 / (sigma * np.sqrt(2.0 * np.pi))
    for pi, si in zip(p, s):
        y += si * norm * np.exp(-0.5 * ((x - pi) / sigma) ** 2)
    return y
# COMMIT608_VIBRONIC_END

# COMMIT609_NONADIABATIC_BEGIN
def two_state_adiabatic_energies(V1, V2, W):
    """Eigenvalues E_- and E_+ of [[V1,W],[W,V2]]."""
    import numpy as np
    V1 = np.asarray(V1, dtype=float)
    V2 = np.asarray(V2, dtype=float)
    W = np.asarray(W, dtype=float)
    mean = 0.5 * (V1 + V2)
    split = np.sqrt((0.5 * (V1 - V2)) ** 2 + W ** 2)
    return mean - split, mean + split


def avoided_crossing_min_gap(W):
    """Minimum adiabatic gap at a diabatic crossing V1=V2."""
    import numpy as np
    return 2.0 * np.abs(np.asarray(W, dtype=float))


def two_state_mixing_angle(V1, V2, W):
    """Angle theta with tan(2 theta)=2W/(V1-V2), using atan2 for quadrant safety."""
    import numpy as np
    return 0.5 * np.arctan2(2.0 * np.asarray(W, dtype=float),
                            np.asarray(V1, dtype=float) - np.asarray(V2, dtype=float))


def rotation_matrix_2state(theta):
    """Real orthogonal two-state rotation U(theta)."""
    import numpy as np
    c = float(np.cos(theta))
    s = float(np.sin(theta))
    return np.asarray([[c, -s], [s, c]], dtype=float)


def adiabatic_to_diabatic_potential(E1, E2, theta):
    """H_d = U diag(E1,E2) U^T for the Chapter 55 real two-state convention."""
    import numpy as np
    U = rotation_matrix_2state(theta)
    Ha = np.diag([float(E1), float(E2)])
    return U @ Ha @ U.T


def diagonalize_real_two_state(V1, V2, W):
    """Return ascending eigenvalues and orthonormal eigenvectors of a real two-state Hamiltonian."""
    import numpy as np
    H = np.asarray([[float(V1), float(W)], [float(W), float(V2)]], dtype=float)
    return np.linalg.eigh(H)


def derivative_coupling_linear_crossing(R, slope, W):
    """d theta/dR for Delta(R)=slope*R and constant W, theta=1/2 atan2(2W,Delta)."""
    import numpy as np
    R = np.asarray(R, dtype=float)
    a = float(slope)
    w = float(W)
    delta = a * R
    return -(w * a) / (delta * delta + 4.0 * w * w)


def derivative_coupling_from_hamiltonian_gradient(offdiag_gradient_matrix_element, energy_gap):
    """Local off-diagonal identity d_ab=<a|grad H|b>/(E_b-E_a)."""
    import numpy as np
    gap = np.asarray(energy_gap, dtype=float)
    if np.any(gap == 0.0):
        raise ValueError("energy gap must be nonzero")
    return np.asarray(offdiag_gradient_matrix_element, dtype=float) / gap


def landau_zener_gamma(W, gap_sweep_rate, hbar=1.0):
    """Gamma_LZ=W^2/(hbar*|dDelta/dt|)."""
    w = float(W)
    rate = abs(float(gap_sweep_rate))
    hb = float(hbar)
    if rate <= 0.0 or hb <= 0.0:
        raise ValueError("gap_sweep_rate and hbar must be positive")
    return (w * w) / (hb * rate)


def landau_zener_diabatic_survival(W, gap_sweep_rate, hbar=1.0):
    """P_diab=exp(-2*pi*Gamma_LZ), in the convention used in Chapter 55."""
    import math
    g = landau_zener_gamma(W, gap_sweep_rate, hbar=hbar)
    return math.exp(-2.0 * math.pi * g)


def landau_zener_adiabatic_following(W, gap_sweep_rate, hbar=1.0):
    """Complement of diabatic survival for the ideal isolated two-state passage."""
    return 1.0 - landau_zener_diabatic_survival(W, gap_sweep_rate, hbar=hbar)


def landau_zener_sweep_rate(spatial_gap_slope, velocity):
    """|dDelta/dt|=|dDelta/dR|*|v|."""
    return abs(float(spatial_gap_slope) * float(velocity))


def conical_intersection_energies(x, y, kappa=1.0, lam=1.0, E0=0.0):
    """E_- and E_+ for H=E0 I + kappa*x sigma_z + lam*y sigma_x."""
    import numpy as np
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    r = np.sqrt((float(kappa) * x) ** 2 + (float(lam) * y) ** 2)
    return float(E0) - r, float(E0) + r


def conical_intersection_gap(x, y, kappa=1.0, lam=1.0):
    """Adiabatic gap 2*sqrt((kappa x)^2+(lambda y)^2)."""
    lo, hi = conical_intersection_energies(x, y, kappa=kappa, lam=lam, E0=0.0)
    return hi - lo


def winding_number_xy(points):
    """Integer winding number of a closed planar polygonal path around the origin."""
    import numpy as np
    z = np.asarray(points, dtype=float)
    if z.ndim != 2 or z.shape[1] != 2 or z.shape[0] < 3:
        raise ValueError("points must have shape (N,2), N>=3")
    if not np.allclose(z[0], z[-1]):
        z = np.vstack([z, z[0]])
    ang = np.unwrap(np.arctan2(z[:, 1], z[:, 0]))
    return int(np.rint((ang[-1] - ang[0]) / (2.0 * np.pi)))


def conical_intersection_berry_phase(points):
    """Unwrapped geometric phase pi*winding for the ideal real two-state CI model."""
    import math
    return math.pi * winding_number_xy(points)


def normalize_state_vector(psi):
    """Normalize a complex finite-dimensional state vector."""
    import numpy as np
    z = np.asarray(psi, dtype=complex)
    n = float(np.linalg.norm(z))
    if n == 0.0:
        raise ValueError("state vector norm must be nonzero")
    return z / n


def two_state_populations(psi):
    """Basis populations |c_1|^2, |c_2|^2 after normalization."""
    import numpy as np
    z = normalize_state_vector(psi)
    return np.abs(z) ** 2


def transform_state_basis(psi, U):
    """Apply a unitary/orthogonal basis transformation to state amplitudes."""
    import numpy as np
    z = np.asarray(psi, dtype=complex)
    mat = np.asarray(U, dtype=complex)
    if mat.ndim != 2 or mat.shape[0] != mat.shape[1] or mat.shape[1] != z.size:
        raise ValueError("incompatible state and transformation dimensions")
    return mat @ z


def unitary_error(U):
    """Frobenius norm ||U^dagger U-I||_F."""
    import numpy as np
    mat = np.asarray(U, dtype=complex)
    if mat.ndim != 2 or mat.shape[0] != mat.shape[1]:
        raise ValueError("U must be square")
    return float(np.linalg.norm(mat.conj().T @ mat - np.eye(mat.shape[0]), ord="fro"))


def adiabaticity_regime(W, gap_sweep_rate, hbar=1.0):
    """Return Gamma_LZ and a compact qualitative regime label."""
    g = landau_zener_gamma(W, gap_sweep_rate, hbar=hbar)
    if g < 0.1:
        label = "diabatic"
    elif g > 1.0:
        label = "adiabatic"
    else:
        label = "intermediate"
    return g, label
# COMMIT609_NONADIABATIC_END

# COMMIT610_MOLECULAR_INTEGRATION_BEGIN
def molecular_lambda_letter(Lambda):
    """Return conventional molecular term letter for Lambda=0,1,2,... through H."""
    letters = ["Sigma", "Pi", "Delta", "Phi", "Gamma", "H"]
    n = int(Lambda)
    if n < 0 or n >= len(letters):
        raise ValueError("Lambda outside supported range 0..5")
    return letters[n]


def omega_projection(Lambda, Sigma):
    """Absolute molecular-axis projection Omega=|Lambda+Sigma|."""
    return abs(float(Lambda) + float(Sigma))


def spin_orbit_case_a_shift(A_so, Lambda, Sigma):
    """Case-(a) first-order spin-orbit shift A_so*Lambda*Sigma."""
    return float(A_so) * float(Lambda) * float(Sigma)


def spin_rotation_shift(gamma, J, N, S):
    """gamma/2 [J(J+1)-N(N+1)-S(S+1)]."""
    g=float(gamma); j=float(J); n=float(N); s=float(S)
    return 0.5*g*(j*(j+1.0)-n*(n+1.0)-s*(s+1.0))


def hund_case_indicator(A_so, B, J):
    """Dimensionless |A_so|/(|B|*max(J,1/2)) qualitative coupling indicator."""
    den=abs(float(B))*max(abs(float(J)),0.5)
    if den == 0.0:
        raise ValueError("B must be nonzero")
    return abs(float(A_so))/den


def lambda_doubling_splitting(q, J):
    """Simple effective Lambda-doubling splitting Delta=q*J(J+1)."""
    j=float(J)
    if j < 0.0:
        raise ValueError("J must be nonnegative")
    return float(q)*j*(j+1.0)


def lambda_doublet_levels(E0, q, J):
    """Parity-pair levels E0 +/- Delta/2 in the simple effective model."""
    d=lambda_doubling_splitting(q,J)
    return float(E0)-0.5*d, float(E0)+0.5*d


def stark_parity_doublet_levels(delta0, mu, field, center=0.0):
    """Two opposite-parity levels coupled by -mu E; returns ascending energies."""
    import math
    d=0.5*float(delta0)
    v=float(mu)*float(field)
    r=math.sqrt(d*d+v*v)
    c=float(center)
    return c-r, c+r


def zeeman_shift_linear(g_eff, M_J, B, mu_B=1.0):
    """Weak-field linear Zeeman shift g_eff*mu_B*M_J*B."""
    return float(g_eff)*float(mu_B)*float(M_J)*float(B)


def nuclear_spin_subspace_dimensions(I):
    """Dimensions of symmetric/antisymmetric spin spaces for two identical spin-I nuclei."""
    I=float(I)
    if I < 0.0:
        raise ValueError("I must be nonnegative")
    n=2.0*I+1.0
    gs=n*(n+1.0)/2.0
    ga=n*(n-1.0)/2.0
    if abs(gs-round(gs))>1e-10 or abs(ga-round(ga))>1e-10:
        raise ValueError("I must be integer or half-integer")
    return int(round(gs)), int(round(ga))


def required_nuclear_spin_weight(I, spin_exchange_symmetry):
    """Return spin multiplicity for requested exchange symmetry +1 symmetric or -1 antisymmetric."""
    gs,ga=nuclear_spin_subspace_dimensions(I)
    if spin_exchange_symmetry == 1:
        return gs
    if spin_exchange_symmetry == -1:
        return ga
    raise ValueError("spin_exchange_symmetry must be +1 or -1")


def asymmetric_top_matrix(J, A, B, C):
    """Rigid asymmetric-top matrix in |J,K> basis K=-J..J, a-axis quantization."""
    import numpy as np
    J=int(J)
    if J < 0:
        raise ValueError("J must be nonnegative integer")
    A=float(A); B=float(B); C=float(C)
    Ks=np.arange(-J,J+1,dtype=int)
    H=np.zeros((Ks.size,Ks.size),dtype=float)
    JJ=J*(J+1)
    for i,K in enumerate(Ks):
        H[i,i]=A*K*K+0.5*(B+C)*(JJ-K*K)
        K2=K+2
        if K2<=J:
            j=i+2
            f1=JJ-K*(K+1)
            f2=JJ-(K+1)*(K+2)
            val=0.25*(B-C)*(max(f1*f2,0.0)**0.5)
            H[i,j]=val
            H[j,i]=val
    return Ks,H


def asymmetric_top_levels(J, A, B, C):
    """Sorted rigid asymmetric-top eigenvalues for fixed J."""
    import numpy as np
    _,H=asymmetric_top_matrix(J,A,B,C)
    return np.linalg.eigvalsh(H)


def symmetric_top_energy(A, B, J, K):
    """Prolate symmetric-top energy B J(J+1)+(A-B)K^2.

    Public argument order is preserved as (A, B, J, K).
    """
    A=float(A); B=float(B); J=int(J); K=int(K)
    if J < 0 or abs(K) > J:
        raise ValueError("require J>=0 and |K|<=J")
    return B*J*(J+1)+(A-B)*K*K


def spherical_top_energy(J, B):
    """Spherical-top energy B J(J+1)."""
    J=int(J)
    if J<0:
        raise ValueError("J must be nonnegative")
    return float(B)*J*(J+1)


def fermi_resonance_levels(E1, E2, W):
    """Eigenvalues of [[E1,W],[W,E2]]."""
    import math
    e1=float(E1); e2=float(E2); w=float(W)
    m=0.5*(e1+e2)
    r=math.sqrt((0.5*(e1-e2))**2+w*w)
    return m-r,m+r


def fermi_resonance_splitting(E1, E2, W):
    """Observed two-level splitting sqrt((E1-E2)^2+4W^2)."""
    import math
    return math.sqrt((float(E1)-float(E2))**2+4.0*float(W)**2)


def fermi_mixing_angle(E1, E2, W):
    """Two-state mixing angle theta=1/2 atan2(2W,E1-E2)."""
    import math
    return 0.5*math.atan2(2.0*float(W),float(E1)-float(E2))


def coriolis_diagonal_shift(B, zeta, K, ell):
    """Simple diagonal Coriolis estimate -2 B zeta K ell."""
    return -2.0*float(B)*float(zeta)*float(K)*float(ell)


def field_mixing_fraction(delta0, coupling):
    """Minor-component probability for lower eigenstate of a symmetric two-level doublet."""
    import math
    d=float(delta0)
    v=float(coupling)
    if d==0.0 and v==0.0:
        raise ValueError("degenerate uncoupled doublet has undefined mixing angle")
    r=math.sqrt(d*d+4.0*v*v)
    return 0.5*(1.0-abs(d)/r)


def rotational_constant_from_inertia(I, hbar=1.0):
    """Energy-unit rotational constant hbar^2/(2I)."""
    I=float(I); hb=float(hbar)
    if I<=0.0 or hb<=0.0:
        raise ValueError("I and hbar must be positive")
    return hb*hb/(2.0*I)


def molecular_dependency_order():
    """Canonical Chapter 55 Hamiltonian dependency chain."""
    return (
        "electronic",
        "Born-Oppenheimer surface",
        "vibrational",
        "rotational",
        "rovibrational",
        "vibronic",
        "nonadiabatic",
    )
# COMMIT610_MOLECULAR_INTEGRATION_END
