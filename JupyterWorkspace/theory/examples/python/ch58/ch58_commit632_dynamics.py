"""Commit 632 numerical companion for driven two-level Hamiltonians.

Uses exact 2x2 midpoint-unitary steps, so norm preservation is built into the
time propagation without requiring scipy.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import numpy as np

I2 = np.eye(2, dtype=complex)
SX = np.array([[0,1],[1,0]], complex)
SY = np.array([[0,-1j],[1j,0]], complex)
SZ = np.array([[1,0],[0,-1]], complex)


def unitary_from_pauli(hx, hy, hz, dt):
    """exp[-i (hx sx + hy sy + hz sz) dt], hbar=1."""
    r = float(np.sqrt(hx*hx + hy*hy + hz*hz))
    if r < 1e-15:
        return I2.copy()
    c = np.cos(r*dt)
    s = np.sin(r*dt)/r
    H = hx*SX + hy*SY + hz*SZ
    return c*I2 - 1j*s*H


def propagate_pauli(times, psi0, hvec):
    """Midpoint piecewise-constant unitary propagation."""
    times = np.asarray(times, float)
    psi = np.asarray(psi0, complex).copy()
    out = np.empty((len(times),2), complex)
    out[0] = psi
    for j in range(len(times)-1):
        dt = times[j+1]-times[j]
        tm = 0.5*(times[j+1]+times[j])
        hx,hy,hz = hvec(tm)
        psi = unitary_from_pauli(hx,hy,hz,dt) @ psi
        out[j+1] = psi
    return out


def lz_asymptotic_probability(g, v, hbar=1.0):
    if v <= 0 or hbar <= 0:
        raise ValueError("v and hbar must be positive")
    return float(np.exp(-2*np.pi*g*g/(hbar*v)))


def finite_lz_survival(g=0.5, v=1.0, T=8.0, steps=8000):
    if T <= 0 or steps < 2:
        raise ValueError("T>0 and steps>=2 required")
    times = np.linspace(-T,T,steps)
    psi0 = np.array([1.0,0.0], complex)  # diabatic |0>
    traj = propagate_pauli(times, psi0, lambda t:(g,0.0,0.5*v*t))
    return float(abs(traj[-1,0])**2), times, traj


def lzs_probability(P_lz, phase, stokes=0.0):
    P_lz = np.asarray(P_lz,float)
    phase = np.asarray(phase,float)
    return 4*P_lz*(1-P_lz)*np.sin(0.5*phase+stokes)**2


def rabi_rwa_probability(t, A, detuning=0.0):
    t=np.asarray(t,float)
    eff=np.sqrt(A*A+detuning*detuning)
    if eff < 1e-15:
        return np.zeros_like(t)
    return (A*A/eff**2)*np.sin(0.5*eff*t)**2


def driven_trajectory(omega0=1.0, A=0.1, omega_d=1.0, tmax=40.0, steps=12000):
    times=np.linspace(0,tmax,steps)
    psi0=np.array([0.0,1.0],complex)  # ground state for +omega0/2 sigma_z
    traj=propagate_pauli(times,psi0,
                         lambda t:(A*np.cos(omega_d*t),0.0,0.5*omega0))
    return times,traj


def bloch_siegert_shift(A, omega0=1.0, omega_d=None):
    if omega_d is None:
        omega_d=omega0
    return float(A*A/(4.0*(omega0+omega_d)))


def floquet_operator(omega0=1.0,A=0.2,omega_d=1.0,steps_per_period=4000):
    T=2*np.pi/omega_d
    times=np.linspace(0,T,steps_per_period+1)
    U=I2.copy()
    for j in range(len(times)-1):
        dt=times[j+1]-times[j]
        tm=0.5*(times[j+1]+times[j])
        Us=unitary_from_pauli(A*np.cos(omega_d*tm),0.0,0.5*omega0,dt)
        U=Us@U
    return U


def floquet_quasienergies(omega0=1.0,A=0.2,omega_d=1.0,steps_per_period=4000):
    U=floquet_operator(omega0,A,omega_d,steps_per_period)
    vals=np.linalg.eigvals(U)
    T=2*np.pi/omega_d
    eps=-np.angle(vals)/T
    eps=np.sort(eps)
    return eps


def sambe_matrix(omega0=1.0,A=0.2,omega_d=1.0,M=2):
    """Floquet-Sambe matrix for H=omega0/2 sz + A cos(omega t) sx, hbar=1."""
    sectors=list(range(-M,M+1))
    d=2*len(sectors)
    F=np.zeros((d,d),complex)
    H0=0.5*omega0*SZ
    H1=0.5*A*SX
    for ia,m in enumerate(sectors):
        sl=slice(2*ia,2*ia+2)
        F[sl,sl]=H0 + m*omega_d*I2
        for ib,n in enumerate(sectors):
            if abs(m-n)==1:
                slb=slice(2*ib,2*ib+2)
                F[sl,slb]=H1
    return F


def sambe_quasienergies(omega0=1.0,A=0.2,omega_d=1.0,M=3):
    vals=np.linalg.eigvalsh(sambe_matrix(omega0,A,omega_d,M))
    folded=((vals+0.5*omega_d)%omega_d)-0.5*omega_d
    return np.sort(folded)


def generate_figures(output: Path):
    import matplotlib.pyplot as plt
    output.mkdir(parents=True,exist_ok=True)

    # finite time LZ convergence
    g,v=0.42,1.0
    Ts=np.linspace(1.5,12.0,75)
    exact=[]
    for T in Ts:
        p,_,_=finite_lz_survival(g,v,T,steps=max(1200,int(700*T)))
        exact.append(p)
    asym=lz_asymptotic_probability(g,v)
    fig,ax=plt.subplots(figsize=(8.2,4.8))
    ax.plot(Ts,exact,label="finite-window exact propagation")
    ax.axhline(asym,linestyle="--",label="infinite-time Landau-Zener limit")
    ax.set_xlabel("half sweep duration $T$")
    ax.set_ylabel("diabatic survival probability")
    ax.set_title("Finite-time Landau-Zener convergence")
    ax.grid(alpha=0.25); ax.legend()
    fig.tight_layout(); fig.savefig(output/"finite_time_landau_zener.pdf"); plt.close(fig)

    # Stückelberg fringes
    phase=np.linspace(0,4*np.pi,600)
    Ps=np.linspace(0.01,0.99,240)
    Z=np.array([lzs_probability(p,phase,stokes=np.pi/8) for p in Ps])
    fig,ax=plt.subplots(figsize=(8.2,5.0))
    im=ax.imshow(Z,origin="lower",aspect="auto",
                 extent=[phase[0]/np.pi,phase[-1]/np.pi,Ps[0],Ps[-1]])
    fig.colorbar(im,ax=ax,label="output probability")
    ax.set_xlabel(r"dynamical phase $\Phi_{\rm dyn}/\pi$")
    ax.set_ylabel(r"$P_{\rm LZ}$")
    ax.set_title("Landau-Zener-Stückelberg interference")
    fig.tight_layout(); fig.savefig(output/"stuckelberg_interference.pdf"); plt.close(fig)

    # exact vs RWA
    omega0=1.0
    fig,ax=plt.subplots(figsize=(8.2,5.0))
    for A,style in [(0.12,"weak"),(0.55,"strong")]:
        t,tr=driven_trajectory(omega0,A,omega0,tmax=28,steps=14000)
        pe=np.abs(tr[:,0])**2
        ax.plot(t,pe,label=f"exact {style}, A={A:g}")
        if A==0.55:
            ax.plot(t,rabi_rwa_probability(t,A,0),linestyle="--",label="RWA strong-drive prediction")
    ax.set_xlabel("time"); ax.set_ylabel("excited-state probability")
    ax.set_title("Strong driving beyond the rotating-wave approximation")
    ax.grid(alpha=0.25); ax.legend()
    fig.tight_layout(); fig.savefig(output/"exact_vs_rwa_strong_drive.pdf"); plt.close(fig)

    # Bloch-Siegert scaling
    As=np.linspace(0,0.65,300)
    shifts=np.array([bloch_siegert_shift(a,1.0,1.0) for a in As])
    fig,ax=plt.subplots(figsize=(8.0,4.8))
    ax.plot(As,shifts,label=r"$\delta_{\rm BS}\simeq A^2/(8\omega_0)$")
    ax.set_xlabel(r"drive amplitude $A/\omega_0$")
    ax.set_ylabel(r"frequency shift $\delta_{\rm BS}/\omega_0$")
    ax.set_title("Perturbative Bloch-Siegert shift")
    ax.grid(alpha=0.25); ax.legend()
    fig.tight_layout(); fig.savefig(output/"bloch_siegert_shift.pdf"); plt.close(fig)

    # Floquet quasienergies vs amplitude
    amps=np.linspace(0,1.0,90)
    e1=[];e2=[]
    for a in amps:
        e=floquet_quasienergies(omega0=1.0,A=a,omega_d=0.82,steps_per_period=1200)
        e1.append(e[0]);e2.append(e[1])
    fig,ax=plt.subplots(figsize=(8.2,4.8))
    ax.plot(amps,e1,label="lower quasienergy")
    ax.plot(amps,e2,label="upper quasienergy")
    ax.axhline(0.41,linestyle=":",linewidth=0.8)
    ax.axhline(-0.41,linestyle=":",linewidth=0.8)
    ax.set_xlabel("drive amplitude $A$")
    ax.set_ylabel("folded quasienergy")
    ax.set_title("Exact Floquet quasienergies from the one-period propagator")
    ax.grid(alpha=0.25); ax.legend()
    fig.tight_layout(); fig.savefig(output/"floquet_quasienergies.pdf"); plt.close(fig)


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--generate-figures",action="store_true")
    p.add_argument("--output",type=Path,default=Path("generated/ch58/computational"))
    a=p.parse_args()
    if a.generate_figures:
        generate_figures(a.output)

if __name__=="__main__":
    main()
