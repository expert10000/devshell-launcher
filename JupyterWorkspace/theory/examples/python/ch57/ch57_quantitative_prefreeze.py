"""Commit 630 quantitative Chapter 57 companion.

Finite-chain propagation, explicit Lindblad superoperators, Liouvillian spectra,
exceptional-point normal forms, noise comparisons, and Dicke-rate scaling.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import numpy as np


def paulis():
    I = np.eye(2, dtype=complex)
    sx = np.array([[0,1],[1,0]], complex)
    sy = np.array([[0,-1j],[1j,0]], complex)
    sz = np.array([[1,0],[0,-1]], complex)
    sm = np.array([[0,1],[0,0]], complex)
    sp = sm.conj().T
    return I, sx, sy, sz, sm, sp


def lindblad_superoperator(H, jumps):
    """Column-vectorization convention vec(A rho B)=(B^T kron A)vec(rho)."""
    H = np.asarray(H, dtype=complex)
    d = H.shape[0]
    I = np.eye(d, dtype=complex)
    L = -1j * (np.kron(I, H) - np.kron(H.T, I))
    for J in jumps:
        J = np.asarray(J, dtype=complex)
        A = J.conj().T @ J
        L += np.kron(J.conj(), J)
        L -= 0.5 * np.kron(I, A)
        L -= 0.5 * np.kron(A.T, I)
    return L


def single_spin_liouvillian(omega0=2.0, gamma_down=0.6, gamma_up=0.0, gamma_phi=0.2):
    I,sx,sy,sz,sm,sp = paulis()
    H = 0.5 * omega0 * sz
    jumps = []
    if gamma_down > 0:
        jumps.append(np.sqrt(gamma_down) * sm)
    if gamma_up > 0:
        jumps.append(np.sqrt(gamma_up) * sp)
    if gamma_phi > 0:
        jumps.append(np.sqrt(gamma_phi/2.0) * sz)
    return lindblad_superoperator(H, jumps)


def expected_single_spin_eigenvalues(omega0, gamma_down, gamma_up, gamma_phi):
    g1 = gamma_down + gamma_up
    g2 = 0.5*g1 + gamma_phi
    return np.array([0.0, -g1, -g2+1j*omega0, -g2-1j*omega0], complex)


def _op_on_two(op, which):
    I = np.eye(2, dtype=complex)
    return np.kron(op,I) if which == 0 else np.kron(I,op)


def two_spin_liouvillian(omega0=1.5, exchange=0.12, gamma=0.35,
                         collective=False, asymmetry=0.0):
    I,sx,sy,sz,sm,sp = paulis()
    sx1,sx2 = _op_on_two(sx,0), _op_on_two(sx,1)
    sy1,sy2 = _op_on_two(sy,0), _op_on_two(sy,1)
    sz1,sz2 = _op_on_two(sz,0), _op_on_two(sz,1)
    sm1,sm2 = _op_on_two(sm,0), _op_on_two(sm,1)
    H = 0.5*omega0*(sz1+sz2) + exchange*(sx1@sx2 + sy1@sy2 + sz1@sz2)
    H += asymmetry*(sz1-sz2)
    if collective:
        jumps = [np.sqrt(gamma)*(sm1+sm2)]
    else:
        jumps = [np.sqrt(gamma)*sm1, np.sqrt(gamma)*sm2]
    return lindblad_superoperator(H, jumps)


def liouvillian_gap(L, tol=1e-9):
    vals = np.linalg.eigvals(L)
    decay = [-v.real for v in vals if abs(v) > tol and v.real < -tol]
    return float(min(decay)) if decay else 0.0


def trace_left_vector(d):
    return np.eye(d, dtype=complex).reshape(-1, order="F").conj()


def one_magnon_hamiltonian(N=31, J=1.0, disorder=None, seed=0):
    if N < 2:
        raise ValueError("N must be >=2")
    H = np.zeros((N,N), complex)
    for j in range(N-1):
        H[j,j+1] = H[j+1,j] = -J
    if disorder is not None and disorder != 0:
        rng = np.random.default_rng(seed)
        H += np.diag(rng.uniform(-disorder/2, disorder/2, N))
    return H


def exact_unitary_propagation(H, psi0, times):
    H = np.asarray(H, complex)
    psi0 = np.asarray(psi0, complex)
    evals, evecs = np.linalg.eigh(H)
    coeff = evecs.conj().T @ psi0
    times = np.asarray(times, float)
    phase = np.exp(-1j * np.outer(evals, times))
    return (evecs @ (coeff[:,None] * phase)).T


def inverse_participation_ratio(psi):
    p = np.abs(np.asarray(psi))**2
    norm = p.sum(axis=-1, keepdims=True)
    p = p / norm
    return np.sum(p**2, axis=-1)


def ep_matrix(mu, gamma=1.0):
    return np.array([[-gamma, 1.0],[mu, -gamma]], complex)


def ep_eigenvalues(mu, gamma=1.0):
    return np.array([-gamma + np.sqrt(complex(mu)), -gamma - np.sqrt(complex(mu))])


def jordan_ep_propagator(t, gamma=1.0):
    t = float(t)
    return np.exp(-gamma*t) * np.array([[1.0,t],[0.0,1.0]], complex)


def gaussian_quasistatic_envelope(t, sigma=1.0):
    t = np.asarray(t,float)
    return np.exp(-0.5*(sigma*t)**2)


def exponential_envelope(t, T2=1.0):
    t = np.asarray(t,float)
    return np.exp(-t/T2)


def ou_spectrum(omega, delta=1.0, tau_c=1.0):
    omega = np.asarray(omega,float)
    return 2*delta**2*tau_c/(1+(omega*tau_c)**2)


def ou_ramsey_envelope(t, delta=1.0, tau_c=1.0):
    """Exact Gaussian dephasing envelope for OU noise under free induction."""
    t = np.asarray(t,float)
    chi = delta**2 * tau_c**2 * (t/tau_c - 1.0 + np.exp(-t/tau_c))
    return np.exp(-chi)


def dicke_rates(N, gamma=1.0):
    n = np.arange(N+1, dtype=float)
    return gamma * n * (N-n+1.0)


def dicke_rate_rhs(P, N, gamma=1.0):
    rates = dicke_rates(N,gamma)
    dP = -rates * P
    dP[:-1] += rates[1:] * P[1:]
    return dP


def dicke_rate_trajectory(N, gamma=1.0, tmax=3.0, steps=4000):
    """RK4 integration of ideal Dicke population rate equations, initial n=N."""
    t = np.linspace(0,tmax,steps)
    dt = t[1]-t[0]
    P = np.zeros(N+1,float)
    P[N] = 1.0
    hist = np.empty((steps,N+1),float)
    hist[0] = P
    for i in range(1,steps):
        k1 = dicke_rate_rhs(P,N,gamma)
        k2 = dicke_rate_rhs(P+0.5*dt*k1,N,gamma)
        k3 = dicke_rate_rhs(P+0.5*dt*k2,N,gamma)
        k4 = dicke_rate_rhs(P+dt*k3,N,gamma)
        P = P + dt*(k1+2*k2+2*k3+k4)/6.0
        P[P < 0] = 0.0
        P /= P.sum()
        hist[i] = P
    rates = dicke_rates(N,gamma)
    intensity = hist @ rates
    return t, hist, intensity


def generate_figures(output: Path):
    import matplotlib.pyplot as plt
    output.mkdir(parents=True, exist_ok=True)

    # 1. Single-spin spectrum
    omega0, gd, gu, gp = 2.3, 0.6, 0.1, 0.18
    vals = np.linalg.eigvals(single_spin_liouvillian(omega0,gd,gu,gp))
    fig, ax = plt.subplots(figsize=(7.2,5.4))
    ax.scatter(vals.real, vals.imag, s=70)
    ax.axvline(0, linewidth=0.9)
    ax.axhline(0, linewidth=0.9)
    ax.set_xlabel(r"$\mathrm{Re}\,\lambda$")
    ax.set_ylabel(r"$\mathrm{Im}\,\lambda$")
    ax.set_title("Single-spin Liouvillian spectrum")
    ax.grid(alpha=0.25)
    fig.tight_layout(); fig.savefig(output/"liouvillian_single_spin_complex_plane.pdf"); plt.close(fig)

    # 2. Two-spin independent vs collective
    Li = two_spin_liouvillian(collective=False)
    Lc = two_spin_liouvillian(collective=True)
    vi, vc = np.linalg.eigvals(Li), np.linalg.eigvals(Lc)
    fig, ax = plt.subplots(figsize=(8.0,5.4))
    ax.scatter(vi.real,vi.imag,s=40,label="independent decay")
    ax.scatter(vc.real,vc.imag,s=55,marker="x",label="collective decay")
    ax.axvline(0, linewidth=0.9); ax.axhline(0, linewidth=0.9)
    ax.set_xlabel(r"$\mathrm{Re}\,\lambda$"); ax.set_ylabel(r"$\mathrm{Im}\,\lambda$")
    ax.set_title("Two-spin 16-mode Liouvillian spectra")
    ax.grid(alpha=0.25); ax.legend()
    fig.tight_layout(); fig.savefig(output/"liouvillian_two_spin_complex_plane.pdf"); plt.close(fig)

    # 3. EP
    mu = np.linspace(-1.0,1.0,600)
    l1 = np.array([ep_eigenvalues(x)[0] for x in mu])
    l2 = np.array([ep_eigenvalues(x)[1] for x in mu])
    fig, ax = plt.subplots(figsize=(8.0,5.2))
    ax.plot(mu,l1.real,label=r"$\mathrm{Re}\lambda_+$")
    ax.plot(mu,l2.real,label=r"$\mathrm{Re}\lambda_-$")
    ax.plot(mu,l1.imag,linestyle="--",label=r"$\mathrm{Im}\lambda_+$")
    ax.plot(mu,l2.imag,linestyle="--",label=r"$\mathrm{Im}\lambda_-$")
    ax.axvline(0, linewidth=1.0, label="exceptional point")
    ax.set_xlabel(r"control parameter $\mu$"); ax.set_ylabel("eigenvalue component")
    ax.set_title("Eigenvalue coalescence at an exceptional point")
    ax.grid(alpha=0.25); ax.legend(ncol=2)
    fig.tight_layout(); fig.savefig(output/"liouvillian_exceptional_point.pdf"); plt.close(fig)

    # 4. Finite chain heatmap
    N=41
    H = one_magnon_hamiltonian(N,J=1.0)
    psi0 = np.zeros(N,complex); psi0[N//2]=1
    times = np.linspace(0,22,300)
    psi = exact_unitary_propagation(H,psi0,times)
    P = np.abs(psi)**2
    fig, ax = plt.subplots(figsize=(8.4,5.5))
    im = ax.imshow(P.T,origin="lower",aspect="auto",extent=[times[0],times[-1],0,N-1])
    fig.colorbar(im,ax=ax,label="probability")
    ax.set_xlabel("time"); ax.set_ylabel("site")
    ax.set_title("Exact finite-chain one-magnon propagation")
    fig.tight_layout(); fig.savefig(output/"finite_chain_magnon_heatmap.pdf"); plt.close(fig)

    # 5. Disorder comparison
    times = np.linspace(0,20,260)
    Hc = one_magnon_hamiltonian(N,J=1.0)
    Hd = one_magnon_hamiltonian(N,J=1.0,disorder=7.0,seed=3)
    Pc = np.abs(exact_unitary_propagation(Hc,psi0,times))**2
    Pd = np.abs(exact_unitary_propagation(Hd,psi0,times))**2
    fig, ax = plt.subplots(figsize=(8.2,5.0))
    ax.plot(np.arange(N),Pc[-1],label="clean chain")
    ax.plot(np.arange(N),Pd[-1],label="strong static disorder")
    ax.set_xlabel("site"); ax.set_ylabel("probability at final time")
    ax.set_title("Disorder suppresses coherent spatial spreading")
    ax.grid(alpha=0.25); ax.legend()
    fig.tight_layout(); fig.savefig(output/"disorder_clean_vs_localized.pdf"); plt.close(fig)

    # 6. Noise comparisons
    t=np.linspace(0,5,700)
    fig, ax = plt.subplots(figsize=(8.2,5.0))
    ax.plot(t,exponential_envelope(t,1.6),label="Markov exponential")
    ax.plot(t,gaussian_quasistatic_envelope(t,0.8),label="quasistatic Gaussian")
    ax.plot(t,ou_ramsey_envelope(t,delta=0.9,tau_c=0.55),label="Ornstein-Uhlenbeck")
    ax.set_xlabel("time"); ax.set_ylabel("normalized coherence")
    ax.set_ylim(-0.02,1.03)
    ax.set_title("Different noise spectra produce different coherence envelopes")
    ax.grid(alpha=0.25); ax.legend()
    fig.tight_layout(); fig.savefig(output/"noise_models_coherence_comparison.pdf"); plt.close(fig)

    # 7. Superradiance scaling
    Ns=np.array([4,6,8,12,16,24,32])
    peaks=[]
    for Nn in Ns:
        t_,P_,I_=dicke_rate_trajectory(int(Nn),tmax=2.5,steps=6000)
        peaks.append(I_.max())
    peaks=np.array(peaks)
    indep=Ns.astype(float)
    fig, ax = plt.subplots(figsize=(8.2,5.0))
    ax.loglog(Ns,peaks,"o-",label="Dicke-rate peak")
    ax.loglog(Ns,indep,"--",label=r"$\propto N$")
    ref=peaks[-1]/Ns[-1]**2
    ax.loglog(Ns,ref*Ns**2,":",label=r"$\propto N^2$")
    ax.set_xlabel("$N$"); ax.set_ylabel("peak intensity")
    ax.set_title("Superradiant peak scaling")
    ax.grid(alpha=0.25,which="both"); ax.legend()
    fig.tight_layout(); fig.savefig(output/"superradiance_scaling.pdf"); plt.close(fig)


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--generate-figures",action="store_true")
    p.add_argument("--output",type=Path,default=Path("generated/ch57/computational"))
    a=p.parse_args()
    if a.generate_figures:
        generate_figures(a.output)

if __name__=="__main__":
    main()
