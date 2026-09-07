"""Commit 633 companion: engineered two-level platforms and quantum control."""
from __future__ import annotations
import argparse
from pathlib import Path
import numpy as np

I2 = np.eye(2, dtype=complex)
SX = np.array([[0,1],[1,0]], complex)
SY = np.array([[0,-1j],[1j,0]], complex)
SZ = np.array([[1,0],[0,-1]], complex)


def unitary_pauli(angle, phase=0.0, detuning_ratio=0.0, amplitude_scale=1.0):
    """Rectangular pulse. Nominal angle=Omega*t; detuning_ratio=Delta/Omega."""
    ax = amplitude_scale*np.cos(phase)
    ay = amplitude_scale*np.sin(phase)
    az = detuning_ratio
    r = float(np.sqrt(ax*ax + ay*ay + az*az))
    if r < 1e-15:
        return I2.copy()
    theta = angle*r
    nH = (ax*SX + ay*SY + az*SZ)/r
    return np.cos(theta/2)*I2 - 1j*np.sin(theta/2)*nH

def unitary_pauli_components(hx, hy, hz, dt):
    """Exact exp[-i(hx sx + hy sy + hz sz)dt] for a traceless 2x2 Hamiltonian."""
    r = float(np.sqrt(hx*hx + hy*hy + hz*hz))
    if r < 1e-15:
        return I2.copy()
    H = hx*SX + hy*SY + hz*SZ
    return np.cos(r*dt)*I2 - 1j*np.sin(r*dt)*H/r


def average_gate_fidelity(U, target):
    U = np.asarray(U, complex)
    target = np.asarray(target, complex)
    tr = np.trace(target.conj().T @ U)
    return float((abs(tr)**2 + 2.0)/6.0)


def rx(theta):
    return np.cos(theta/2)*I2 - 1j*np.sin(theta/2)*SX


def bb1(theta=np.pi, amplitude_error=0.0):
    phi = float(np.arccos(-theta/(4*np.pi)))
    scale = 1.0 + amplitude_error
    seq = [
        (theta/2, 0.0),
        (np.pi, phi),
        (2*np.pi, 3*phi),
        (np.pi, phi),
        (theta/2, 0.0),
    ]
    U = I2.copy()
    for ang, ph in seq:
        U = unitary_pauli(ang, ph, amplitude_scale=scale) @ U
    return U


def primitive_x(theta=np.pi, amplitude_error=0.0, detuning_ratio=0.0):
    return unitary_pauli(theta, 0.0, detuning_ratio=detuning_ratio,
                         amplitude_scale=1.0+amplitude_error)


def corpse_pi(detuning_ratio=0.0):
    # Standard CORPSE pi choice: 420_x, 300_-x, 60_x.
    seq = [
        (7*np.pi/3, 0.0),
        (5*np.pi/3, np.pi),
        (np.pi/3, 0.0),
    ]
    U = I2.copy()
    for ang, ph in seq:
        U = unitary_pauli(ang, ph, detuning_ratio=detuning_ratio) @ U
    return U


def dqd_energies(epsilon, tc):
    epsilon = np.asarray(epsilon, float)
    gap = np.sqrt(epsilon**2 + 4*tc**2)
    return -0.5*gap, 0.5*gap


def dqd_ground_polarization(epsilon, tc):
    epsilon = np.asarray(epsilon, float)
    return -epsilon/np.sqrt(epsilon**2 + 4*tc**2)


def transmon_levels(EJ, EC, nmax=4):
    m = np.arange(nmax, dtype=float)
    return (-EJ + np.sqrt(8*EJ*EC)*(m+0.5)
            - EC*(6*m*m+6*m+3)/12.0)


def transmon_anharmonicity(EJ, EC):
    E = transmon_levels(EJ, EC, 3)
    w01 = E[1]-E[0]
    w12 = E[2]-E[1]
    return float(w12-w01)


def unitary_from_hermitian(H, dt):
    evals, evecs = np.linalg.eigh(np.asarray(H, complex))
    return evecs @ np.diag(np.exp(-1j*evals*dt)) @ evecs.conj().T


def propagate_hamiltonian(times, psi0, H_of_t):
    times = np.asarray(times, float)
    psi = np.asarray(psi0, complex).copy()
    out = np.empty((len(times), len(psi)), complex)
    out[0] = psi
    for j in range(len(times)-1):
        dt = times[j+1]-times[j]
        tm = 0.5*(times[j+1]+times[j])
        psi = unitary_from_hermitian(H_of_t(tm), dt) @ psi
        out[j+1] = psi
    return out


def arp_transfer(beta=0.25, omega=1.0, detuning_span=8.0, steps=5000):
    """Adiabatic rapid passage at fixed endpoint detuning |Delta|=detuning_span.

    Varying beta now changes the sweep speed without also changing how far the
    protocol begins and ends from resonance.
    """
    if beta <= 0 or omega <= 0 or detuning_span <= 0:
        raise ValueError("beta, omega, and detuning_span must be positive")
    T = detuning_span / beta
    times = np.linspace(-T, T, steps)

    def H(t):
        return 0.5*(omega*SX + beta*t*SZ)

    # Prepare the instantaneous lower-energy eigenstate at the initial endpoint.
    evals, evecs = np.linalg.eigh(H(-T))
    psi0 = evecs[:, 0]
    traj = propagate_hamiltonian(times, psi0, H)
    return float(abs(traj[-1,1])**2), times, traj


def bias_modulated_max_excitation(epsilon0, g, A, omega_d, periods=8, steps_per_period=60):
    """Fast exact 2x2 propagation for a bias-modulated avoided crossing."""
    T = 2*np.pi/omega_d
    nsteps = int(periods*steps_per_period)
    dt = T/steps_per_period

    H0 = 0.5*(epsilon0 + A)*SZ + g*SX
    vals, vecs = np.linalg.eigh(H0)
    psi = vecs[:,0].copy()
    excited = vecs[:,1]

    pmax = float(abs(np.vdot(excited, psi))**2)
    for j in range(nsteps):
        tm = (j+0.5)*dt
        hz = 0.5*(epsilon0 + A*np.cos(omega_d*tm))
        U = unitary_pauli_components(g,0.0,hz,dt)
        psi = U @ psi
        p = float(abs(np.vdot(excited, psi))**2)
        if p > pmax:
            pmax = p
    return pmax


def lz_scatter(P, phi=0.0):
    P = float(P)
    if not 0 <= P <= 1:
        raise ValueError("P must lie in [0,1]")
    a = np.sqrt(P)
    b = np.sqrt(1-P)
    return np.array([[a*np.exp(-1j*phi), -b],
                     [b, a*np.exp(1j*phi)]], complex)


def phase_gate(phi):
    return np.diag([np.exp(-0.5j*phi), np.exp(0.5j*phi)])


def stuckelberg_gate(P, dyn_phase, stokes=0.0):
    S = lz_scatter(P, stokes)
    return S @ phase_gate(dyn_phase) @ S


def remove_global_phase(U):
    det = np.linalg.det(U)
    return U / np.sqrt(det)


def su2_angle_axis(U):
    V = remove_global_phase(np.asarray(U, complex))
    tr = np.trace(V)
    c = np.clip(np.real(tr)/2.0, -1.0, 1.0)
    theta = float(2*np.arccos(c))
    if abs(np.sin(theta/2)) < 1e-10:
        return theta, np.array([0.0,0.0,1.0])
    nx = np.real(1j*np.trace(SX@V)/(2*np.sin(theta/2)))
    ny = np.real(1j*np.trace(SY@V)/(2*np.sin(theta/2)))
    nz = np.real(1j*np.trace(SZ@V)/(2*np.sin(theta/2)))
    n = np.array([nx,ny,nz], float)
    norm = np.linalg.norm(n)
    if norm > 0:
        n /= norm
    return theta, n


def floquet_operator(omega0=1.0, A=0.2, omega_d=1.0, longitudinal=0.15,
                     steps_per_period=1400):
    T = 2*np.pi/omega_d
    times = np.linspace(0,T,steps_per_period+1)
    U = I2.copy()
    for j in range(len(times)-1):
        dt = times[j+1]-times[j]
        tm = 0.5*(times[j+1]+times[j])
        H = (0.5*omega0*SZ
             + A*np.cos(omega_d*tm)*SX
             + longitudinal*np.cos(omega_d*tm)*SZ)
        U = unitary_from_hermitian(H, dt) @ U
    return U


def floquet_quasienergy_gap(omega0=1.0, A=0.2, omega_d=1.0, longitudinal=0.15,
                            steps_per_period=1400):
    U = floquet_operator(omega0,A,omega_d,longitudinal,steps_per_period)
    phases = np.sort(np.angle(np.linalg.eigvals(U)))
    dphi = abs(phases[1]-phases[0])
    dphi = min(dphi, 2*np.pi-dphi)
    return float(dphi * omega_d/(2*np.pi))


def floquet_gate_fidelity(target, omega0=1.0, A=0.2, omega_d=1.0,
                          longitudinal=0.15, steps_per_period=1400):
    U = floquet_operator(omega0,A,omega_d,longitudinal,steps_per_period)
    return average_gate_fidelity(U, target)


def generate_figures(output: Path):
    import matplotlib.pyplot as plt
    output.mkdir(parents=True, exist_ok=True)

    # DQD
    eps = np.linspace(-6,6,700)
    em, ep = dqd_energies(eps,1.0)
    pol = dqd_ground_polarization(eps,1.0)
    fig, ax = plt.subplots(figsize=(8.2,4.8))
    ax.plot(eps,em,label="ground energy")
    ax.plot(eps,ep,label="excited energy")
    ax2 = ax.twinx()
    ax2.plot(eps,pol,linestyle="--",label="ground-state charge polarization")
    ax.set_xlabel("detuning")
    ax.set_ylabel("energy")
    ax2.set_ylabel("charge polarization")
    ax.set_title("Double-quantum-dot avoided crossing")
    ax.grid(alpha=0.25)
    lines, labels = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines+lines2, labels+labels2, loc="best")
    fig.tight_layout(); fig.savefig(output/"dqd_avoided_crossing_control.pdf"); plt.close(fig)

    # Transmon ladder
    EJ, EC = 20.0, 0.28
    levels = transmon_levels(EJ,EC,5)
    levels -= levels[0]
    fig, ax = plt.subplots(figsize=(6.8,5.0))
    for i,e in enumerate(levels):
        ax.hlines(e,0.2,0.8)
        ax.text(0.84,e,f"$|{i}\\rangle$")
    ax.set_xlim(0,1.1)
    ax.set_xticks([])
    ax.set_ylabel("energy relative to ground")
    ax.set_title("Weakly anharmonic transmon ladder")
    ax.grid(axis="y",alpha=0.2)
    fig.tight_layout(); fig.savefig(output/"transmon_anharmonic_ladder.pdf"); plt.close(fig)

    # ARP
    fig, ax = plt.subplots(figsize=(8.2,4.8))
    for beta, label in [(0.06,"slow chirp"),(0.22,"intermediate"),(0.75,"fast chirp")]:
        p,t,tr = arp_transfer(beta=beta,omega=1.0,detuning_span=8.0,steps=6000)
        ax.plot(t,np.abs(tr[:,1])**2,label=f"{label}, final={p:.3f}")
    ax.set_xlabel("time")
    ax.set_ylabel("target-state population")
    ax.set_title("Adiabatic rapid passage")
    ax.grid(alpha=0.25); ax.legend()
    fig.tight_layout(); fig.savefig(output/"adiabatic_rapid_passage.pdf"); plt.close(fig)

    # BB1
    errs = np.linspace(-0.35,0.35,401)
    target = rx(np.pi)
    prim = np.array([1-average_gate_fidelity(primitive_x(np.pi,e),target) for e in errs])
    bb = np.array([1-average_gate_fidelity(bb1(np.pi,e),target) for e in errs])
    fig, ax = plt.subplots(figsize=(8.2,4.8))
    ax.semilogy(errs,np.maximum(prim,1e-14),label="primitive pi pulse")
    ax.semilogy(errs,np.maximum(bb,1e-14),label="BB1")
    ax.set_xlabel("fractional amplitude error")
    ax.set_ylabel("average gate infidelity")
    ax.set_title("Composite-pulse suppression of amplitude error")
    ax.grid(alpha=0.25); ax.legend()
    fig.tight_layout(); fig.savefig(output/"bb1_amplitude_robustness.pdf"); plt.close(fig)

    # CORPSE
    dets = np.linspace(-0.8,0.8,401)
    primd = np.array([1-average_gate_fidelity(primitive_x(np.pi,0,d),target) for d in dets])
    cor = np.array([1-average_gate_fidelity(corpse_pi(d),target) for d in dets])
    fig, ax = plt.subplots(figsize=(8.2,4.8))
    ax.semilogy(dets,np.maximum(primd,1e-14),label="primitive pi pulse")
    ax.semilogy(dets,np.maximum(cor,1e-14),label="CORPSE")
    ax.set_xlabel(r"detuning ratio $\Delta/\Omega$")
    ax.set_ylabel("average gate infidelity")
    ax.set_title("Composite-pulse suppression of off-resonance error")
    ax.grid(alpha=0.25); ax.legend()
    fig.tight_layout(); fig.savefig(output/"corpse_detuning_robustness.pdf"); plt.close(fig)

    # Multiphoton map
    freqs = np.linspace(0.24,1.15,48)
    amps = np.linspace(0.15,2.2,28)
    Z = np.empty((len(amps),len(freqs)))
    for ia,A in enumerate(amps):
        for iw,w in enumerate(freqs):
            Z[ia,iw] = bias_modulated_max_excitation(
                epsilon0=0.8,g=0.30,A=A,omega_d=w,periods=6,steps_per_period=40
            )
    fig, ax = plt.subplots(figsize=(8.4,5.0))
    im = ax.imshow(Z,origin="lower",aspect="auto",
                   extent=[freqs[0],freqs[-1],amps[0],amps[-1]],
                   vmin=0,vmax=1)
    fig.colorbar(im,ax=ax,label="maximum excitation")
    ax.set_xlabel("drive frequency")
    ax.set_ylabel("modulation amplitude")
    ax.set_title("Multiphoton resonance map")
    fig.tight_layout(); fig.savefig(output/"multiphoton_resonance_map.pdf"); plt.close(fig)

    # Stückelberg gate fidelity map to X
    Ps = np.linspace(0.01,0.99,150)
    phases = np.linspace(0,2*np.pi,180)
    Z = np.empty((len(Ps),len(phases)))
    for i,P in enumerate(Ps):
        for j,ph in enumerate(phases):
            Z[i,j] = average_gate_fidelity(stuckelberg_gate(P,ph,0.2),target)
    fig, ax = plt.subplots(figsize=(8.4,5.0))
    im = ax.imshow(Z,origin="lower",aspect="auto",
                   extent=[0,2,Ps[0],Ps[-1]],vmin=1/3,vmax=1)
    fig.colorbar(im,ax=ax,label="average fidelity to X")
    ax.set_xlabel(r"dynamical phase / $\pi$")
    ax.set_ylabel(r"$P_{\rm LZ}$")
    ax.set_title("Stückelberg gate landscape")
    fig.tight_layout(); fig.savefig(output/"stuckelberg_gate_map.pdf"); plt.close(fig)

    # Floquet diagnostics
    amps = np.linspace(0,1.0,90)
    gaps = []
    angles = []
    fids = []
    target_y = np.cos(np.pi/4)*I2 - 1j*np.sin(np.pi/4)*SY
    for A in amps:
        U = floquet_operator(omega0=1.0,A=A,omega_d=0.86,longitudinal=0.18,
                             steps_per_period=850)
        gaps.append(floquet_quasienergy_gap(1.0,A,0.86,0.18,850))
        th,_ = su2_angle_axis(U)
        angles.append(th/np.pi)
        fids.append(average_gate_fidelity(U,target_y))
    fig, ax = plt.subplots(figsize=(8.3,5.0))
    ax.plot(amps,gaps,label="Floquet quasienergy gap")
    ax.plot(amps,angles,label=r"one-period rotation angle / $\pi$")
    ax.plot(amps,fids,label="fidelity to target gate")
    ax.set_xlabel("drive amplitude")
    ax.set_ylabel("diagnostic value")
    ax.set_title("Floquet control diagnostics")
    ax.grid(alpha=0.25); ax.legend()
    fig.tight_layout(); fig.savefig(output/"floquet_control_diagnostics.pdf"); plt.close(fig)


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--generate-figures",action="store_true")
    p.add_argument("--output",type=Path,default=Path("generated/ch58/computational"))
    a=p.parse_args()
    if a.generate_figures:
        generate_figures(a.output)

if __name__=="__main__":
    main()
