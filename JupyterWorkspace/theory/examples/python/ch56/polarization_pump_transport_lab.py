from __future__ import annotations
import numpy as np

SIGMA_X = np.array([[0.0,1.0],[1.0,0.0]], dtype=complex)
SIGMA_Y = np.array([[0.0,-1j],[1j,0.0]], dtype=complex)
SIGMA_Z = np.array([[1.0,0.0],[0.0,-1.0]], dtype=complex)

def ssh_hamiltonian(k: float, t1: float, t2: float) -> np.ndarray:
    dx = t1 + t2*np.cos(k)
    dy = t2*np.sin(k)
    return dx*SIGMA_X + dy*SIGMA_Y

def rice_mele_hamiltonian(k: float, theta: float, t0: float=1.0,
                          delta_t: float=0.35, delta0: float=0.6) -> np.ndarray:
    t1 = t0 + delta_t*np.cos(theta)
    t2 = t0 - delta_t*np.cos(theta)
    delta = delta0*np.sin(theta)
    dx = t1 + t2*np.cos(k)
    dy = t2*np.sin(k)
    return dx*SIGMA_X + dy*SIGMA_Y + delta*SIGMA_Z

def occupied_vector(H: np.ndarray) -> np.ndarray:
    vals, vecs = np.linalg.eigh(H)
    return vecs[:, np.argmin(vals)]

def normalized_overlap(u: np.ndarray, v: np.ndarray) -> complex:
    z = np.vdot(u, v)
    if abs(z) < 1e-14:
        raise ValueError("Overlap too small for a stable link.")
    return z/abs(z)

def zak_phase_ssh(t1: float, t2: float, nk: int=801) -> float:
    ks = np.linspace(-np.pi, np.pi, nk, endpoint=False)
    us = [occupied_vector(ssh_hamiltonian(float(k), t1, t2)) for k in ks]
    W = 1.0 + 0.0j
    for j in range(nk):
        W *= normalized_overlap(us[j], us[(j+1)%nk])
    gamma = (-np.angle(W)) % (2*np.pi)
    if abs(gamma - 2*np.pi) < 1e-10:
        gamma = 0.0
    return float(gamma)

def polarization_branch_from_zak(gamma: float) -> float:
    return float((-gamma/(2*np.pi)) % 1.0)

def inversion_parity_ssh(k: float, t1: float, t2: float) -> int:
    if abs(k) > 1e-10 and abs(abs(k)-np.pi) > 1e-10:
        raise ValueError("Inversion parity shortcut is evaluated at k=0 or pi.")
    u = occupied_vector(ssh_hamiltonian(k, t1, t2))
    xi = float(np.real(np.vdot(u, SIGMA_X @ u)))
    return 1 if xi >= 0 else -1

def inversion_indicator_ssh(t1: float, t2: float) -> dict:
    xi0 = inversion_parity_ssh(0.0, t1, t2)
    xipi = inversion_parity_ssh(np.pi, t1, t2)
    product = xi0*xipi
    z2 = 0 if product == 1 else 1
    return {"xi0": xi0, "xipi": xipi, "product": product, "z2": z2}

def direct_gap(H: np.ndarray) -> float:
    vals = np.linalg.eigvalsh(H)
    return float(vals[1]-vals[0])

def minimum_rice_mele_gap(t0: float=1.0, delta_t: float=0.35,
                          delta0: float=0.6, nk: int=121, ntheta: int=121) -> float:
    ks = np.linspace(-np.pi, np.pi, nk, endpoint=False)
    th = np.linspace(0, 2*np.pi, ntheta, endpoint=False)
    g = np.inf
    for theta in th:
        for k in ks:
            g = min(g, direct_gap(rice_mele_hamiltonian(float(k), float(theta), t0, delta_t, delta0)))
    return float(g)

def chern_rice_mele(t0: float=1.0, delta_t: float=0.35, delta0: float=0.6,
                     nk: int=51, ntheta: int=51) -> int:
    ks = np.linspace(-np.pi, np.pi, nk, endpoint=False)
    ths = np.linspace(0, 2*np.pi, ntheta, endpoint=False)
    u = np.empty((ntheta, nk, 2), dtype=complex)
    for a, th in enumerate(ths):
        for b, k in enumerate(ks):
            u[a,b] = occupied_vector(rice_mele_hamiltonian(float(k), float(th), t0, delta_t, delta0))
    total = 0.0
    for a in range(ntheta):
        ap = (a+1)%ntheta
        for b in range(nk):
            bp = (b+1)%nk
            Uk = normalized_overlap(u[a,b], u[a,bp])
            Ut = normalized_overlap(u[a,b], u[ap,b])
            Uk_t = normalized_overlap(u[ap,b], u[ap,bp])
            Ut_k = normalized_overlap(u[a,bp], u[ap,bp])
            plaquette = Uk * Ut_k / (Uk_t * Ut)
            total += np.angle(plaquette)
    return int(np.rint(total/(2*np.pi)))

def pump_charge_e_units(**kwargs) -> int:
    return chern_rice_mele(**kwargs)

def ideal_chern_hall_conductance_e2_over_h(C: int) -> int:
    return int(C)

def ideal_qsh_two_terminal_conductance_e2_over_h(kramers_pairs: int=1) -> int:
    if kramers_pairs < 0:
        raise ValueError("Number of Kramers pairs must be nonnegative.")
    return 2*int(kramers_pairs)

def reference_summary() -> dict:
    triv = zak_phase_ssh(1.2,0.8,801)
    top = zak_phase_ssh(0.8,1.2,801)
    ind_triv = inversion_indicator_ssh(1.2,0.8)
    ind_top = inversion_indicator_ssh(0.8,1.2)
    C = chern_rice_mele(nk=51, ntheta=51)
    gap = minimum_rice_mele_gap(nk=81, ntheta=81)
    return {
        "zak_trivial": triv,
        "zak_topological": top,
        "polarization_trivial_e": polarization_branch_from_zak(triv),
        "polarization_topological_e": polarization_branch_from_zak(top),
        "indicator_trivial": ind_triv,
        "indicator_topological": ind_top,
        "pump_chern": C,
        "pump_charge_e": C,
        "pump_min_gap": gap,
        "chern_hall_e2_over_h_for_C1": ideal_chern_hall_conductance_e2_over_h(1),
        "qsh_two_terminal_e2_over_h_one_pair": ideal_qsh_two_terminal_conductance_e2_over_h(1),
    }

if __name__ == "__main__":
    import json
    print(json.dumps(reference_summary(), indent=2))
