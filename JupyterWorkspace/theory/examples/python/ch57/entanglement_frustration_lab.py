from __future__ import annotations
import numpy as np

SX = np.array([[0, 1], [1, 0]], dtype=complex)
SY = np.array([[0, -1j], [1j, 0]], dtype=complex)
SZ = np.array([[1, 0], [0, -1]], dtype=complex)
I2 = np.eye(2, dtype=complex)
PAULI = (SX, SY, SZ)
SPIN = tuple(0.5 * s for s in PAULI)

UP = np.array([1, 0], dtype=complex)
DOWN = np.array([0, 1], dtype=complex)

def kron_all(ops):
    out = np.array([[1.0 + 0.0j]])
    for op in ops:
        out = np.kron(out, op)
    return out

def normalize(psi):
    v = np.asarray(psi, dtype=complex).reshape(-1)
    n = np.linalg.norm(v)
    if n <= 0:
        raise ValueError('state norm must be positive')
    return v / n

def basis_state(bits):
    v = np.array([1.0 + 0.0j])
    for b in bits:
        v = np.kron(v, UP if b == 1 else DOWN)
    return v

def singlet_state():
    return normalize(np.kron(UP, DOWN) - np.kron(DOWN, UP))

def triplet_zero_state():
    return normalize(np.kron(UP, DOWN) + np.kron(DOWN, UP))

def triplet_plus_state():
    return np.kron(UP, UP)

def product_updown_state():
    return np.kron(UP, DOWN)

def local_operator(N: int, site: int, single: np.ndarray):
    if not (0 <= site < N):
        raise ValueError('site out of range')
    ops = [I2] * N
    ops[site] = np.asarray(single, dtype=complex)
    return kron_all(ops)

def two_site_term(N: int, i: int, j: int, Jx=1.0, Jy=1.0, Jz=1.0):
    return (Jx * local_operator(N, i, SPIN[0]) @ local_operator(N, j, SPIN[0]) +
            Jy * local_operator(N, i, SPIN[1]) @ local_operator(N, j, SPIN[1]) +
            Jz * local_operator(N, i, SPIN[2]) @ local_operator(N, j, SPIN[2]))

def heisenberg_triangle(J: float = 1.0):
    N = 3
    H = np.zeros((2**N, 2**N), dtype=complex)
    for i, j in [(0, 1), (1, 2), (2, 0)]:
        H += J * two_site_term(N, i, j, 1.0, 1.0, 1.0)
    return H

def xxz_dimer(Jxy=1.0, Jz=1.0):
    return two_site_term(2, 0, 1, Jxy, Jxy, Jz)

def xyz_dimer(Jx=1.0, Jy=0.8, Jz=1.3):
    return two_site_term(2, 0, 1, Jx, Jy, Jz)

def j1j2_chain(N: int, J1=1.0, J2=0.0, pbc=True):
    H = np.zeros((2**N, 2**N), dtype=complex)
    nn = [(i, i + 1) for i in range(N - 1)]
    if pbc and N > 2:
        nn += [(N - 1, 0)]
    for i, j in nn:
        H += J1 * two_site_term(N, i, j)
    nnn = []
    if pbc:
        for i in range(N):
            j = (i + 2) % N
            pair = tuple(sorted((i, j)))
            if pair not in nnn:
                nnn.append(pair)
    else:
        for i in range(N - 2):
            nnn.append((i, i + 2))
    for i, j in nnn:
        H += J2 * two_site_term(N, i, j)
    return H

def dimerized_open_chain(N: int, Jstrong=1.0, Jweak=0.0):
    H = np.zeros((2**N, 2**N), dtype=complex)
    for i in range(N - 1):
        J = Jstrong if (i % 2 == 0) else Jweak
        H += J * two_site_term(N, i, i + 1)
    return H



def groundspace_density_matrix(H, tol=1e-10):
    vals, vecs = np.linalg.eigh(H)
    e0 = float(np.real(vals[0]))
    mask = np.abs(np.real(vals) - e0) < tol
    basis = vecs[:, mask]
    rho = basis @ basis.conj().T / basis.shape[1]
    return e0, rho

def groundspace_expectation(H, O, tol=1e-10):
    _, rho = groundspace_density_matrix(H, tol=tol)
    return float(np.real(np.trace(rho @ O)))
def ground_state(H):
    vals, vecs = np.linalg.eigh(H)
    return float(np.real(vals[0])), vecs[:, 0]

def lowest_energies(H, k=4):
    vals = np.linalg.eigvalsh(H)
    return np.sort(np.real(vals))[:k]

def reduced_density_matrix(psi, keep, dims=None):
    psi = normalize(psi)
    if dims is None:
        N = int(round(np.log2(len(psi))))
        dims = [2] * N
    dims = list(dims)
    keep = list(keep)
    N = len(dims)
    trace = [i for i in range(N) if i not in keep]
    tensor = psi.reshape(dims)
    perm = keep + trace
    tensor = np.transpose(tensor, perm)
    d_keep = int(np.prod([dims[i] for i in keep], dtype=int))
    d_trace = int(np.prod([dims[i] for i in trace], dtype=int))
    tensor = tensor.reshape(d_keep, d_trace)
    return tensor @ tensor.conj().T

def von_neumann_entropy(rho, base=2.0):
    vals = np.linalg.eigvalsh((rho + rho.conj().T) / 2.0)
    vals = np.real_if_close(vals)
    vals = vals[vals > 1e-14]
    if len(vals) == 0:
        return 0.0
    logs = np.log(vals) / np.log(base)
    return float(-np.sum(vals * logs))

def concurrence(rho):
    Y = np.kron(SY, SY)
    R = rho @ Y @ rho.conj() @ Y
    eig = np.linalg.eigvals(R)
    lam = np.sort(np.sqrt(np.maximum(np.real(eig), 0.0)))[::-1]
    lam = np.pad(lam, (0, max(0, 4 - len(lam))), constant_values=0.0)
    return float(max(0.0, lam[0] - lam[1] - lam[2] - lam[3]))

def total_spin_squared(N):
    comps = [sum(local_operator(N, i, SPIN[a]) for i in range(N)) for a in range(3)]
    return sum(c @ c for c in comps)

def expectation(psi, O):
    v = normalize(psi)
    return np.vdot(v, O @ v)

def bond_correlation(psi, N, i, j):
    return float(np.real(expectation(psi, two_site_term(N, i, j))))

def connected_zz(psi, N, i, j):
    si = local_operator(N, i, SPIN[2])
    sj = local_operator(N, j, SPIN[2])
    return float(np.real(expectation(psi, si @ sj) - expectation(psi, si) * expectation(psi, sj)))

def structure_factor_zz(psi, N, q):
    total = 0.0 + 0.0j
    for i in range(N):
        for j in range(N):
            total += np.exp(1j * q * (i - j)) * expectation(psi, local_operator(N, i, SPIN[2]) @ local_operator(N, j, SPIN[2]))
    value = float(np.real(total / N))
    # S^{zz}(q) is nonnegative in exact arithmetic.  Small negative values can
    # appear from eigensolver / summation roundoff on different BLAS backends.
    if abs(value) < 1e-12:
        return 0.0
    return value

def mg_states_N4():
    s = singlet_state()
    A = np.kron(s, s)
    B = np.zeros(16, dtype=complex)
    coeffs = {
        (1, 0, 1, 0): 0.5,
        (1, 1, 0, 0): -0.5,
        (0, 0, 1, 1): -0.5,
        (0, 1, 0, 1): 0.5,
    }
    for bits, c in coeffs.items():
        B += c * basis_state(bits)
    return normalize(A), normalize(B)

def state_fidelity(psi, phi):
    psi = normalize(psi); phi = normalize(phi)
    return float(abs(np.vdot(psi, phi)) ** 2)

def gap(H):
    vals = np.sort(np.real(np.linalg.eigvalsh(H)))
    return float(vals[1] - vals[0])

def dimer_indicator(psi, N):
    if N < 3:
        return 0.0
    return bond_correlation(psi, N, 0, 1) - bond_correlation(psi, N, 1, 2)

def reference_summary():
    rho_s = reduced_density_matrix(singlet_state(), [0], [2, 2])
    Htri = heisenberg_triangle(1.0)
    e_tri, psi_tri = ground_state(Htri)
    Hxxz = xxz_dimer(1.0, 1.5)
    Hmg = j1j2_chain(4, 1.0, 0.5, pbc=True)
    evals_mg = np.sort(np.real(np.linalg.eigvalsh(Hmg)))
    Hd = dimerized_open_chain(4, 1.0, 0.0)
    _, psi_d = ground_state(Hd)
    rho_block = reduced_density_matrix(psi_d, [0, 1], [2, 2, 2, 2])
    H6 = j1j2_chain(6, 1.0, 0.0, pbc=False)
    _, psi6 = ground_state(H6)
    return {
        'singlet_entropy': von_neumann_entropy(rho_s),
        'singlet_concurrence': concurrence(np.outer(singlet_state(), singlet_state().conj())),
        'triangle_ground_energy': e_tri,
        'triangle_bond_corr_01': groundspace_expectation(Htri, two_site_term(3, 0, 1)),
        'triangle_total_s2': float(np.real(expectation(psi_tri, total_spin_squared(3)))),
        'xxz_eigenvalues': np.sort(np.real(np.linalg.eigvalsh(Hxxz))).tolist(),
        'mg_ground_energy': float(evals_mg[0]),
        'mg_first_excited_energy': float(evals_mg[1]),
        'mg_dimer_energy_A': float(np.real(np.vdot(mg_states_N4()[0], Hmg @ mg_states_N4()[0]))),
        'mg_dimer_energy_B': float(np.real(np.vdot(mg_states_N4()[1], Hmg @ mg_states_N4()[1]))),
        'dimer_block_entropy_12': von_neumann_entropy(rho_block),
        'dimer_single_entropy_1': von_neumann_entropy(reduced_density_matrix(psi_d, [0], [2, 2, 2, 2])),
        'chain6_gap': gap(H6),
        'chain6_Szz_pi': structure_factor_zz(psi6, 6, np.pi),
        'chain6_dimer_indicator': dimer_indicator(psi6, 6),
    }

if __name__ == '__main__':
    import json
    print(json.dumps(reference_summary(), indent=2))
