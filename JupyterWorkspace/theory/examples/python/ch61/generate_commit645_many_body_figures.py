from pathlib import Path
import math, numpy as np
import matplotlib.pyplot as plt
from many_body_launch import *

def save(fig,path):
    path.parent.mkdir(parents=True,exist_ok=True); fig.tight_layout(); fig.savefig(path); plt.close(fig)

def main(outdir):
    out=Path(outdir)
    modes=np.arange(2,15)
    fig,ax=plt.subplots(); ax.semilogy(modes,[2**m for m in modes],label="full Fock space"); ax.semilogy(modes,[math.comb(m,m//2) for m in modes],label="half-filled sector")
    ax.set(xlabel="single-particle modes",ylabel="basis dimension",title="Fock-space growth"); ax.legend()
    save(fig,out/"fock_space_basis_growth.pdf")

    fig,ax=plt.subplots()
    L=np.arange(2,14)
    ax.plot(L,L,label="one-particle basis"); ax.semilogy(L,[2**x for x in L],label="many-particle Fock basis")
    ax.set(xlabel="orbital count",ylabel="state count",title="One-particle versus many-particle basis"); ax.legend()
    save(fig,out/"one_vs_many_particle_basis.pdf")

    e=tight_binding_spectrum(40)
    fig,ax=plt.subplots(); ax.plot(np.arange(len(e)),e,marker=".",linestyle="none")
    ax.set(xlabel="eigenvalue index",ylabel="energy / t",title="Periodic tight-binding chain spectrum")
    save(fig,out/"tight_binding_chain_spectrum.pdf")

    Us=np.linspace(-6,8,100); levels=[]
    for U in Us: levels.append(np.linalg.eigvalsh(hubbard_matrix(2,U=U,N=2)[0])[:4])
    levels=np.array(levels)
    fig,ax=plt.subplots()
    for j in range(levels.shape[1]): ax.plot(Us,levels[:,j])
    ax.set(xlabel="U/t",ylabel="two-particle energy / t",title="Hubbard dimer low-energy levels")
    save(fig,out/"hubbard_dimer_levels.pdf")

    Us=np.linspace(-6,8,100); occ=[]
    for U in Us:
        _,p=bose_ground_probabilities(2,U=U)
        occ.append(p)
    occ=np.array(occ)
    fig,ax=plt.subplots()
    for n in range(3): ax.plot(Us,occ[:,n],label=f"|{n},{2-n}>")
    ax.set(xlabel="U/J",ylabel="ground-state probability",title="Two-site Bose-Hubbard occupations"); ax.legend()
    save(fig,out/"bose_hubbard_two_site_occupations.pdf")

    Us=np.linspace(-8,1,100); bind=[pair_binding_energy(U=u) for u in Us]
    fig,ax=plt.subplots(); ax.plot(Us,bind); ax.axhline(0,linewidth=.8)
    ax.set(xlabel="U/t",ylabel="pair-binding energy",title="Attractive-Hubbard pair-binding diagnostic")
    save(fig,out/"attractive_hubbard_pair_binding.pdf")

    dims=particle_number_blocks(10)
    fig,ax=plt.subplots(); ax.bar(np.arange(len(dims)),dims)
    ax.set(xlabel="particle number N",ylabel="block dimension",title="Many-body Hamiltonian block structure by particle number")
    save(fig,out/"particle_number_block_structure.pdf")

if __name__=="__main__":
    import sys; main(sys.argv[1] if len(sys.argv)>1 else "generated/ch61/computational")
