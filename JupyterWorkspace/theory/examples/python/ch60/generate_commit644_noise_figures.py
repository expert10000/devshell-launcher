from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from error_channels import *

def save(fig,path):
    path.parent.mkdir(parents=True,exist_ok=True); fig.tight_layout(); fig.savefig(path); plt.close(fig)

def main(outdir):
    out=Path(outdir)
    t=np.linspace(0,5,250)
    c,d=correlated_dephasing_density(t)
    fig,ax=plt.subplots(); ax.plot(t,c,label="common-sensitive"); ax.plot(t,d,label="differential / DFS-like")
    ax.set(xlabel="time",ylabel="coherence factor",title="Correlated dephasing separates common and differential sectors"); ax.legend()
    save(fig,out/"correlated_dephasing_sectors.pdf")

    depth=np.arange(1,101)
    fig,ax=plt.subplots()
    for p in [0.001,0.003,0.01]:
        ax.plot(depth,repeated_depolarizing_error(p,depth),label=f"p={p}")
    ax.set(xlabel="circuit depth",ylabel="accumulated depolarizing error",title="Channel composition and circuit error accumulation"); ax.legend()
    save(fig,out/"channel_error_accumulation.pdf")

    w=np.logspace(-1,2,300)
    fig,ax=plt.subplots(); ax.loglog(w,lorentzian_psd(w))
    ax.set(xlabel="angular frequency",ylabel="noise PSD",title="Reference Lorentzian noise spectrum for qubit spectroscopy")
    save(fig,out/"noise_spectroscopy_lorentzian.pdf")

    t=np.linspace(0,4,250)
    fig,ax=plt.subplots(); ax.plot(t,ramsey_coherence(t),label="Ramsey"); ax.plot(t,echo_coherence(t),label="echo")
    ax.set(xlabel="time",ylabel="coherence",title="Ramsey/echo spectral inference contrast"); ax.legend()
    save(fig,out/"ramsey_echo_spectral_inference.pdf")

    scales=np.array([1.,1.5,2.,2.5,3.])
    true=.82; noisy=true-.05*scales+.012*scales**2
    fig,ax=plt.subplots(); ax.scatter(scales,noisy,label="noisy observations")
    s=np.linspace(0,3.2,160); coef=np.polyfit(scales,noisy,2); ax.plot(s,np.polyval(coef,s),label="quadratic fit")
    ax.scatter([0],[zne_extrapolate(scales,noisy,2)],label="ZNE intercept")
    ax.set(xlabel="noise scale",ylabel="observable",title="Zero-noise extrapolation diagnostic"); ax.legend()
    save(fig,out/"zero_noise_extrapolation.pdf")

    t=np.linspace(0,4,300); fi=dephasing_fisher_information(t,T2=1.3)
    fig,ax=plt.subplots(); ax.plot(t,fi)
    ax.set(xlabel="interrogation time",ylabel="Fisher information per shot",title="Decoherence-limited sensing information")
    save(fig,out/"open_system_fisher_information.pdf")

if __name__=="__main__":
    import sys; main(sys.argv[1] if len(sys.argv)>1 else "generated/ch60/computational")
