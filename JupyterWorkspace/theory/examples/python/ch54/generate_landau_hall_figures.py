#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import json
import numpy as np
import matplotlib.pyplot as plt

from landau_hall_quantitative import (
    clean_hall_diagnostics,
    diagnostics_summary,
    disorder_ensemble_spectra,
    disorder_plateau_diagnostics,
    gaussian_dos,
    strip_spectrum,
    kubo_band_chern_numbers,
    streda_lowest_gap_counting,
    laughlin_flux_pump,
    lll_interaction_filter,
    coulomb_pseudopotentials,
    interaction_cyclotron_ratio,
    response_fractional_diagnostics,
    finite_size_v1_gaps,
    v1_sphere_spectrum,
    quasihole_zero_mode_diagnostics,
    v1_coulomb_spectral_flow,
    pair_amplitude_diagnostics,
    manybody_commit590_diagnostics,
    torus_momentum_sector_diagnostics,
    torus_twist_spectral_flow,
    nonabelian_ground_bundle_chern,
    quasiparticle_charge_diagnostics,
    manybody_commit591_diagnostics,
    torus_finite_size_scaling,
    torus_shape_scan,
    particle_entanglement_spectrum,
    pinned_quasihole_density_diagnostics,
    torus_disorder_robustness,
    manybody_commit592_diagnostics,
)

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "generated/ch54/computational"
OUT.mkdir(parents=True, exist_ok=True)


def save(fig, name):
    fig.tight_layout()
    fig.savefig(OUT / name, bbox_inches="tight")
    plt.close(fig)


def finite_strip():
    d = strip_spectrum()
    ky = d["ky"] / np.pi
    e = d["energies"]
    w = d["edge_weight"]
    fig, ax = plt.subplots(figsize=(7.1, 4.6))
    for j in range(e.shape[1]):
        ax.scatter(ky, e[:, j], c=w[:, j], s=2.8, vmin=0.0, vmax=1.0)
    ax.set_xlabel(r"$k_y/\pi$")
    ax.set_ylabel(r"energy $E/t$")
    ax.set_title("Finite magnetic strip: bulk subbands and edge-weighted states")
    save(fig, "finite_strip_landau_spectrum.pdf")


def disorder_localization():
    clean, dis = disorder_ensemble_spectra()
    p = disorder_plateau_diagnostics()
    grid = np.linspace(-4.2, 4.2, 700)
    dos0 = gaussian_dos(clean, grid, eta=0.055)
    dosw = gaussian_dos(dis, grid, eta=0.075)
    fig, axes = plt.subplots(2, 1, figsize=(7.1, 6.0), sharex=True)
    axes[0].plot(grid, dos0, label="clean")
    axes[0].plot(grid, dosw, label="disordered ensemble")
    axes[0].set_ylabel("normalized DOS")
    axes[0].legend()
    axes[0].set_title("Disorder broadens magnetic subbands and fills spectral gaps")
    axes[1].scatter(p["energies"], p["ipr"], s=18)
    axes[1].set_xlabel(r"energy $E/t$")
    axes[1].set_ylabel("IPR")
    axes[1].set_title("One finite realization: localization varies across the broadened spectrum")
    save(fig, "disorder_broadening_localization.pdf")


def clean_chern():
    d = clean_hall_diagnostics()
    filled = np.array([1, 2, 3])
    cum = np.asarray(d["cumulative_chern"])
    band = np.asarray(d["band_chern"])
    fig, axes = plt.subplots(2, 1, figsize=(6.7, 5.8), sharex=True)
    axes[0].step(filled, cum, where="mid")
    axes[0].scatter(filled, cum)
    axes[0].axhline(0.0, linewidth=0.8)
    axes[0].set_ylabel(r"cumulative $C$")
    axes[0].set_title(r"Clean $\alpha=1/3$ torus: Hall response from boundary-twist Chern number")
    axes[1].bar(filled, band)
    axes[1].axhline(0.0, linewidth=0.8)
    axes[1].set_xlabel("magnetic bands filled")
    axes[1].set_ylabel("band Chern number")
    axes[1].set_xticks(filled)
    save(fig, "clean_hall_chern_response.pdf")


def edge_flow():
    d = strip_spectrum(nky=181)
    ky = d["ky"] / np.pi
    e = d["energies"]
    pol = d["edge_polarization"]
    weight = d["edge_weight"]
    mask = (e > -3.27) & (e < -2.02) & (weight > 0.25)
    fig, ax = plt.subplots(figsize=(7.1, 4.5))
    yy, xx = np.where(mask)
    sc = ax.scatter(ky[yy], e[yy, xx], c=pol[yy, xx], s=10, vmin=-1.0, vmax=1.0)
    ax.set_xlabel(r"$k_y/\pi$")
    ax.set_ylabel(r"energy $E/t$")
    ax.set_title("Edge spectral flow across the first bulk magnetic gap")
    cbar = fig.colorbar(sc, ax=ax)
    cbar.set_label("right-edge minus left-edge weight")
    save(fig, "edge_spectral_flow.pdf")


def plateau():
    d = disorder_plateau_diagnostics()
    n = d["occupations"]
    ef = d["energies"][n - 1]
    c = d["chern"]
    sens = d["twist_sensitivity"][n - 1]
    ipr = d["ipr"][n - 1]
    fig, axes = plt.subplots(3, 1, figsize=(7.2, 7.2), sharex=True)
    axes[0].step(ef, c, where="post")
    axes[0].scatter(ef, c, s=16)
    axes[0].set_ylabel(r"$C(N)$")
    axes[0].set_title("Disordered finite torus: integer Hall response through a mobility region")
    axes[1].plot(ef, sens, marker="o", markersize=3)
    axes[1].set_ylabel("twist sensitivity")
    axes[2].plot(ef, ipr, marker="o", markersize=3)
    axes[2].set_ylabel("IPR")
    axes[2].set_xlabel(r"Fermi energy proxy $E_N/t$")
    save(fig, "disorder_plateau_diagnostic.pdf")



def kubo_streda():
    c = kubo_band_chern_numbers(3, 51)
    s = streda_lowest_gap_counting()
    fig, axes = plt.subplots(2, 1, figsize=(6.8, 6.0))
    bands = np.arange(1, 4)
    axes[0].bar(bands, c)
    axes[0].axhline(0.0, linewidth=0.8)
    axes[0].set_xticks(bands)
    axes[0].set_xlabel("magnetic band")
    axes[0].set_ylabel(r"Kubo $C_n$")
    axes[0].set_title(r"$\alpha=1/3$: velocity-matrix Berry-curvature integral")
    axes[1].plot(s["alpha"], s["density_per_site"], marker="o")
    x = np.linspace(float(np.min(s["alpha"])), float(np.max(s["alpha"])), 100)
    axes[1].plot(x, s["slope"] * x + s["intercept"], linestyle="--")
    axes[1].set_xlabel(r"flux density $\alpha$")
    axes[1].set_ylabel(r"lowest-gap density $na^2$")
    axes[1].set_title(r"St\v{r}eda gap-label counting: $d(na^2)/d\alpha=1$")
    save(fig, "kubo_streda_response.pdf")


def flux_pump():
    d = laughlin_flux_pump(3, nkx=101, nky=151)
    fig, ax = plt.subplots(figsize=(6.9, 4.3))
    ax.plot(d["twist"] / np.pi, d["center_shift"])
    ax.set_xlabel(r"boundary twist $\theta_x/\pi$")
    ax.set_ylabel(r"hybrid-center shift $\Delta X_W$")
    ax.set_title("One flux cycle winds the occupied-band Wilson loop once")
    ax.axhline(-1.0, linewidth=0.8, linestyle="--")
    save(fig, "laughlin_flux_pump.pdf")


def projected_form_factor():
    qell = np.linspace(0.0, 4.0, 300)
    filt = lll_interaction_filter(qell)
    fig, ax = plt.subplots(figsize=(6.8, 4.2))
    ax.plot(qell, filt)
    ax.set_xlabel(r"$q\ell_B$")
    ax.set_ylabel(r"$|F_0(q)|^2$")
    ax.set_title("Lowest-Landau-level projection filters short wavelengths")
    ax.set_ylim(bottom=0.0)
    save(fig, "projected_landau_form_factor.pdf")


def pseudopotentials():
    v = coulomb_pseudopotentials(9)
    m = np.arange(v.size)
    fig, ax = plt.subplots(figsize=(6.8, 4.2))
    ax.bar(m, v)
    ax.scatter(m[1::2], v[1::2], s=34, label="odd m: spin-polarized fermions")
    ax.set_xlabel(r"relative angular momentum $m$")
    ax.set_ylabel(r"$V_m/E_C$")
    ax.set_title("LLL Coulomb Haldane pseudopotentials")
    ax.legend()
    save(fig, "coulomb_pseudopotentials.pdf")


def mixing_ratio():
    b = np.linspace(1.0, 20.0, 200)
    kappa = interaction_cyclotron_ratio(b)
    fig, ax = plt.subplots(figsize=(6.8, 4.2))
    ax.plot(b, kappa)
    ax.set_xlabel("magnetic field B (T)")
    ax.set_ylabel(r"$\kappa=E_C/(\hbar\omega_c)$")
    ax.set_title("Illustrative GaAs-like Landau-level-mixing scale")
    ax.set_ylim(bottom=0.0)
    save(fig, "interaction_cyclotron_ratio.pdf")



def v1_manybody_gap():
    d = finite_size_v1_gaps()
    fig, axes = plt.subplots(1, 2, figsize=(8.0, 3.9))
    for x, ne in enumerate(d["ne"]):
        e, _, _ = v1_sphere_spectrum(int(ne), 0)
        nshow = min(10, len(e))
        axes[0].scatter(np.full(nshow, x), e[:nshow], s=18)
    axes[0].set_xticks(range(len(d["ne"])), [str(int(x)) for x in d["ne"]])
    axes[0].set_xlabel(r"$N_e$")
    axes[0].set_ylabel(r"energy $E/V_1$")
    axes[0].set_title("Low-energy parent-Hamiltonian spectra")
    axes[1].plot(d["ne"], d["gap"], marker="o")
    axes[1].set_xlabel(r"$N_e$")
    axes[1].set_ylabel(r"finite-size gap $\Delta/V_1$")
    axes[1].set_title("First nonzero eigenvalue")
    save(fig, "v1_manybody_gap.pdf")


def quasihole_modes():
    e0, _, nphi0 = v1_sphere_spectrum(4, 0)
    e1, _, nphi1 = v1_sphere_spectrum(4, 1)
    fig, ax = plt.subplots(figsize=(6.9, 4.2))
    nshow = 18
    ax.scatter(np.zeros(nshow), e0[:nshow], s=24, label=fr"$N_\phi={nphi0}$")
    ax.scatter(np.ones(nshow), e1[:nshow], s=24, label=fr"$N_\phi={nphi1}$")
    ax.set_xticks([0, 1], ["Laughlin flux", "+1 flux"])
    ax.set_ylabel(r"energy $E/V_1$")
    ax.set_title(r"$N_e=4$: one added flux quantum creates a zero-mode multiplet")
    ax.legend()
    save(fig, "quasihole_zero_modes.pdf")


def interaction_spectral_flow():
    d = v1_coulomb_spectral_flow()
    fig, axes = plt.subplots(2, 1, figsize=(7.0, 6.2), sharex=True)
    for j in range(min(7, d["levels"].shape[1])):
        axes[0].plot(d["lambda"], d["levels"][:, j])
    axes[0].set_ylabel("many-body energy")
    axes[0].set_title(r"$N_e=4$: $V_1$ parent $\rightarrow$ projected Coulomb")
    axes[1].plot(d["lambda"], d["gap"], marker="o", markersize=3, label="gap")
    axes[1].plot(d["lambda"], d["overlap_sq"], label=r"$|\langle\Psi_{V_1}|\Psi_0(\lambda)\rangle|^2$")
    axes[1].set_xlabel(r"interpolation $\lambda$")
    axes[1].set_ylabel("diagnostic")
    axes[1].legend()
    save(fig, "v1_coulomb_spectral_flow.pdf")


def pair_amplitudes():
    d = pair_amplitude_diagnostics()
    m = d["m"]
    x = np.arange(len(m), dtype=float)
    width = 0.38
    fig, ax = plt.subplots(figsize=(7.0, 4.3))
    ax.bar(x - width / 2, d["laughlin"], width=width, label=r"$V_1$ ground state")
    ax.bar(x + width / 2, d["compact_slater"], width=width, label="compact Slater")
    ax.set_xticks(x, [str(int(v)) for v in m])
    ax.set_xlabel(r"relative angular momentum $m$")
    ax.set_ylabel(r"pair amplitude $A_m$")
    ax.set_title(r"Correlation hole as suppression of the $m=1$ pair channel")
    ax.legend()
    save(fig, "pair_amplitude_correlations.pdf")


def torus_momentum_sectors():
    d = torus_momentum_sector_diagnostics()
    rows = d["sector_rows"]
    x = np.arange(len(rows))
    ground = np.array([row[3][0] for row in rows], dtype=float)
    labels = [fr"$({row[0]},{row[1]})$" for row in rows]
    fig, ax = plt.subplots(figsize=(7.4, 4.3))
    ax.scatter(x, ground, s=30)
    for i, row in enumerate(rows):
        for e in row[3][1:4]:
            ax.scatter([i], [e], s=13)
    ax.set_xticks(x, labels, rotation=45)
    ax.set_xlabel(r"many-body momentum sector $(K_x,K_y)$")
    ax.set_ylabel("projected interaction energy")
    ax.set_title(r"$N_e=3,N_\phi=9$: three low states in $K_y=0,3,6$")
    save(fig, "torus_manybody_momentum_sectors.pdf")


def torus_twist_flow_figure():
    d = torus_twist_spectral_flow(31)
    fig, ax = plt.subplots(figsize=(7.0, 4.4))
    for j in range(d["levels"].shape[1]):
        ax.plot(d["theta_x"] / np.pi, d["levels"][:, j])
    ax.set_xlabel(r"twist $\theta_x/\pi$")
    ax.set_ylabel("projected interaction energy")
    ax.set_title("Three-state ground manifold remains isolated through one flux cycle")
    save(fig, "torus_ground_multiplet_twist_flow.pdf")


def manybody_chern_figure():
    d = nonabelian_ground_bundle_chern(7)
    theta = d["theta"] / np.pi
    fig, ax = plt.subplots(figsize=(6.2, 5.0))
    im = ax.imshow(d["curvature_phase"].T, origin="lower", extent=[theta[0], 2.0, theta[0], 2.0], aspect="auto")
    ax.set_xlabel(r"$\theta_x/\pi$")
    ax.set_ylabel(r"$\theta_y/\pi$")
    ax.set_title(r"Non-Abelian plaquette Berry phase: $C_{\rm MB}=-1$")
    fig.colorbar(im, ax=ax, label="Berry phase per twist plaquette")
    save(fig, "nonabelian_manybody_chern_curvature.pdf")


def quasiparticle_charge_figure():
    d = quasiparticle_charge_diagnostics(ground_bundle_chern=-1.0, ground_multiplet=3)
    vals = [d["electron_number_deficit"], d["pumped_charge_magnitude_over_e"]]
    fig, ax = plt.subplots(figsize=(6.4, 4.0))
    ax.bar([0, 1], vals)
    ax.axhline(1.0 / 3.0, linestyle="--", linewidth=0.9)
    ax.set_xticks([0, 1], ["+1 flux counting", "|C|/3 pump"])
    ax.set_ylabel(r"fractional charge magnitude $|q^*|/e$")
    ax.set_ylim(0.0, 0.45)
    ax.set_title(r"Independent torus diagnostics agree on $|q^*|=e/3$")
    save(fig, "quasiparticle_charge_consistency.pdf")



def torus_finite_size_figure():
    d = torus_finite_size_scaling()
    x = d["inverse_nphi"]
    fig, ax = plt.subplots(figsize=(7.0, 4.4))
    ax.plot(x, d["gap"], marker="o", label=r"gap $\Delta_{\rm MB}$")
    ax.plot(x, d["multiplet_splitting"], marker="s", label=r"splitting $\delta_{\rm GS}$")
    for xx, ne, geom in zip(x, d["ne"], d["geometry"]):
        ax.annotate(fr"$N_e={int(ne)}$, {geom[0]}$\times${geom[1]}", (xx, d["gap"][list(x).index(xx)]), xytext=(4, 5), textcoords="offset points", fontsize=8)
    ax.set_xlabel(r"inverse flux number $1/N_\phi$")
    ax.set_ylabel("projected interaction energy")
    ax.set_title(r"Finite-size sequence: low multiplet remains separated for $N_e=2,3,4$")
    ax.legend()
    save(fig, "torus_finite_size_scaling.pdf")


def torus_shape_scan_figure():
    d = torus_shape_scan()
    fig, ax = plt.subplots(figsize=(7.0, 4.4))
    ax.plot(d["cell_aspect"], d["gap"], marker="o", label=r"gap $\Delta_{\rm MB}$")
    ax.plot(d["cell_aspect"], d["multiplet_splitting"], marker="s", label=r"splitting $\delta_{\rm GS}$")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel(r"magnetic-cell shape parameter $N_x/N_y$")
    ax.set_ylabel("projected interaction energy")
    ax.set_title(r"Fixed $N_e=4,N_\phi=12$: thin geometries expose finite-size fragility")
    ax.legend()
    save(fig, "torus_shape_scan.pdf")


def particle_entanglement_figure():
    d = particle_entanglement_spectrum()
    xi = d["entanglement_energy"]
    levels = np.arange(1, len(xi) + 1)
    fig, ax = plt.subplots(figsize=(7.0, 4.4))
    ax.scatter(levels, xi, s=18)
    ax.axvline(d["admissible_13_count"] + 0.5, linestyle="--", linewidth=0.9)
    ax.set_xlabel("particle-entanglement level index")
    ax.set_ylabel(r"entanglement energy $\xi=-\ln\lambda$")
    ax.set_title(r"$N_e=4,N_\phi=12$, $N_A=2$: 42 levels below the primary gap")
    save(fig, "particle_entanglement_spectrum.pdf")


def pinned_quasihole_charge_figure():
    d = pinned_quasihole_density_diagnostics()
    fig, ax = plt.subplots(figsize=(7.0, 4.4))
    ax.plot(d["radii"], d["integrated_deficit"], marker="o")
    ax.axhline(1.0 / 3.0, linestyle="--", linewidth=0.9)
    ax.set_xlabel("periodic distance from pinning center")
    ax.set_ylabel(r"integrated electron deficit $\Delta N(R)$")
    ax.set_title(r"Weakly pinned one-flux quasihole: first shell gives $0.3365\simeq1/3$")
    save(fig, "pinned_quasihole_charge_profile.pdf")


def disorder_ground_bundle_figure():
    d = torus_disorder_robustness()
    w = d["disorder_strength"]
    fig, ax = plt.subplots(figsize=(7.0, 4.4))
    ax.plot(w, d["minimum_gap"], marker="o", label=r"minimum twist gap")
    ax.plot(w, d["maximum_multiplet_splitting"], marker="s", label=r"maximum multiplet splitting")
    ax.set_xlabel("projected disorder strength $W$")
    ax.set_ylabel("projected interaction energy")
    ax.set_title(r"Fixed disorder realization: $C_{\rm MB}=-1$ while isolation degrades")
    ax.legend()
    save(fig, "disorder_manybody_bundle_robustness.pdf")


if __name__ == "__main__":
    finite_strip()
    disorder_localization()
    clean_chern()
    edge_flow()
    plateau()
    kubo_streda()
    flux_pump()
    projected_form_factor()
    pseudopotentials()
    mixing_ratio()
    v1_manybody_gap()
    quasihole_modes()
    interaction_spectral_flow()
    pair_amplitudes()
    torus_momentum_sectors()
    torus_twist_flow_figure()
    manybody_chern_figure()
    quasiparticle_charge_figure()
    torus_finite_size_figure()
    torus_shape_scan_figure()
    particle_entanglement_figure()
    pinned_quasihole_charge_figure()
    disorder_ground_bundle_figure()
    summary = diagnostics_summary()
    summary.update(response_fractional_diagnostics())
    summary.update(manybody_commit590_diagnostics())
    summary.update(manybody_commit591_diagnostics())
    summary.update(manybody_commit592_diagnostics())
    summary["commit"] = 592
    (OUT / "diagnostics.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
