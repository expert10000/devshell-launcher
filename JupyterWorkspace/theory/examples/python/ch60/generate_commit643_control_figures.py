from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from open_system_control import *

def save(fig,path):
    path.parent.mkdir(parents=True,exist_ok=True)
    fig.tight_layout(); fig.savefig(path); plt.close(fig)

def main(outdir):
    out=Path(outdir)
    ts=np.linspace(0,5,90)
    fig,ax=plt.subplots()
    for s in ["FID","HAHN","CPMG"]:
        ax.plot(ts,[gaussian_ou_coherence(t,s) for t in ts],label=s)
    ax.set(xlabel="time",ylabel="coherence",title="Free induction, Hahn echo, and CPMG under OU dephasing"); ax.legend()
    save(fig,out/"coherence_fid_hahn_cpmg.pdf")

    omega=np.logspace(-1,2,500)
    fig,ax=plt.subplots()
    for s in ["XY4","XY8"]:
        ax.loglog(omega,filter_function(omega,4,s)+1e-14,label=s)
    ax.set(xlabel="angular frequency",ylabel=r"$|Y(\omega)|^2$",title="Dynamical-decoupling filter comparison"); ax.legend()
    save(fig,out/"xy4_xy8_filter_comparison.pdf")

    widths=np.linspace(0,0.35,60)
    fig,ax=plt.subplots(); ax.plot(widths,finite_width_scan(widths))
    ax.set(xlabel="pi-pulse width",ylabel="final coherence",title="Finite-pulse-width degradation")
    save(fig,out/"finite_pulse_width_degradation.pdf")

    t=np.linspace(0,8,1200); target,free,fb=feedback_rabi_trajectory(t)
    fig,ax=plt.subplots(); ax.plot(t,target,label="target",alpha=.7); ax.plot(t,free,label="uncontrolled",alpha=.7); ax.plot(t,fb,label="feedback",alpha=.8)
    ax.set(xlabel="time",ylabel="Rabi quadrature",title="Feedback-stabilized noisy Rabi trajectory"); ax.legend()
    save(fig,out/"feedback_stabilized_rabi_trajectory.pdf")

    t=np.linspace(0,6,250)
    fig,ax=plt.subplots(); ax.plot(t,dark_state_fidelity(t))
    ax.set(xlabel="time",ylabel="dark-state fidelity",title="Engineered-jump convergence to a dark state")
    save(fig,out/"dark_state_convergence.pdf")

    k=np.logspace(-1,1.2,160)
    fig,ax=plt.subplots()
    for e in [0.0,0.12,0.25]:
        ax.semilogx(k,dissipative_prep_fidelity(k,e,0.25),label=f"mismatch={e:.2f}")
    ax.set(xlabel="engineered dissipation kappa",ylabel="target fidelity",title="Dissipative-state-preparation fidelity"); ax.legend()
    save(fig,out/"dissipative_state_preparation_fidelity.pdf")

    vals=np.linalg.eigvals(engineered_jump_liouvillian())
    fig,ax=plt.subplots(); ax.scatter(vals.real,vals.imag)
    ax.axvline(0,linewidth=.8); ax.axhline(0,linewidth=.8)
    ax.set(xlabel="Re(lambda)",ylabel="Im(lambda)",title="Engineered-jump Liouvillian spectrum")
    save(fig,out/"engineered_jump_liouvillian_spectrum.pdf")

    s=np.linspace(0,5,160); noise,cost,rob=pareto_curve(s)
    fig,ax=plt.subplots(); ax.plot(cost,1-noise,label="suppression"); ax.plot(cost,rob,label="robustness")
    ax.set(xlabel="normalized control cost",ylabel="benefit / robustness",title="Control-noise Pareto diagram"); ax.legend()
    save(fig,out/"control_noise_pareto.pdf")

if __name__=="__main__":
    import sys; main(sys.argv[1] if len(sys.argv)>1 else "generated/ch60/computational")
