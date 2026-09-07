from __future__ import annotations

import argparse
import hashlib
import json
import math
import textwrap
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Rectangle
from matplotlib.lines import Line2D

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
    "mathtext.fontset": "dejavusans",
})

BLUE = "#174a7a"
PALE_BLUE = "#eaf2fa"
GREEN = "#2f6f4e"
PALE_GREEN = "#edf7f0"
GOLD = "#9c6b13"
PALE_GOLD = "#fff7e8"
RED = "#8b3030"
PALE_RED = "#faeeee"
INK = "#17202a"
MUTED = "#53616f"
EDGE = "#7890a8"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def wrap(text: str, width: int) -> str:
    lines = []
    for paragraph in text.split("\n"):
        if not paragraph:
            lines.append("")
        elif paragraph.startswith("$") and paragraph.endswith("$"):
            lines.append(paragraph)
        else:
            lines.extend(textwrap.wrap(paragraph, width=width, break_long_words=False, break_on_hyphens=False))
    return "\n".join(lines)


def box(ax, xy, wh, title, body, face=PALE_BLUE, edge=BLUE, title_size=10.6, body_size=9.2, body_width=38):
    x, y = xy
    w, h = wh
    patch = FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0.008,rounding_size=0.012",
        linewidth=1.1, edgecolor=edge, facecolor=face,
        transform=ax.transAxes, clip_on=False,
    )
    ax.add_patch(patch)
    ax.text(x + 0.018, y + h - 0.018, title, transform=ax.transAxes,
            fontsize=title_size, fontweight="bold", color=edge, va="top")
    ax.text(x + 0.018, y + h - 0.055, wrap(body, body_width), transform=ax.transAxes,
            fontsize=body_size, color=INK, va="top", linespacing=1.16)
    return patch


def title(ax, heading, subtitle):
    ax.text(0.025, 0.978, heading, transform=ax.transAxes, fontsize=15.2,
            fontweight="bold", color=BLUE, va="top")
    ax.text(0.025, 0.940, subtitle, transform=ax.transAxes, fontsize=9.4,
            color=MUTED, va="top")
    ax.add_line(Line2D([0.025, 0.975], [0.918, 0.918], transform=ax.transAxes,
                       color=BLUE, linewidth=1.35))


def save(fig, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, format="pdf")
    plt.close(fig)


def base_figure():
    fig, ax = plt.subplots(figsize=(6.9, 7.7))
    fig.subplots_adjust(left=0.025, right=0.975, bottom=0.025, top=0.98)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    return fig, ax


def draw_chain(ax, y=0.67, alternating=True, labels=True):
    xs = [0.075, 0.155, 0.255, 0.335, 0.435, 0.515]
    for i, x in enumerate(xs):
        ax.add_patch(Circle((x, y), 0.016, transform=ax.transAxes,
                            facecolor="white", edgecolor=BLUE, linewidth=1.6))
        if labels:
            ax.text(x, y - 0.055, "A" if i % 2 == 0 else "B", transform=ax.transAxes,
                    ha="center", fontsize=8.3, color=MUTED)
    for i in range(len(xs) - 1):
        lw = 4.0 if (not alternating or i % 2 == 0) else 1.7
        color = GOLD if i % 2 == 0 else GREEN
        ax.add_line(Line2D([xs[i] + 0.016, xs[i + 1] - 0.016], [y, y],
                           transform=ax.transAxes, linewidth=lw, color=color))
    ax.text(0.075, y + 0.045, "open chain", transform=ax.transAxes,
            fontsize=8.5, color=MUTED)


def draw_square_lattice(ax, origin=(0.075, 0.59), nx=4, ny=3, w=0.42, h=0.19):
    ox, oy = origin
    for ix in range(nx):
        for iy in range(ny):
            x = ox + ix * w / (nx - 1)
            y = oy + iy * h / (ny - 1)
            if ix < nx - 1:
                ax.add_line(Line2D([x, ox + (ix + 1) * w / (nx - 1)], [y, y],
                                   transform=ax.transAxes, color=EDGE, linewidth=1.0))
            if iy < ny - 1:
                ax.add_line(Line2D([x, x], [y, oy + (iy + 1) * h / (ny - 1)],
                                   transform=ax.transAxes, color=EDGE, linewidth=1.0))
            ax.add_patch(Circle((x, y), 0.009, transform=ax.transAxes,
                                facecolor=PALE_BLUE, edgecolor=BLUE, linewidth=1.0))


def draw_edge_arrows(ax, y=0.600):
    for x in [0.09, 0.19, 0.29, 0.39]:
        ax.add_patch(FancyArrowPatch((x, y), (x + 0.065, y), transform=ax.transAxes,
                                     arrowstyle="-|>", mutation_scale=11,
                                     linewidth=1.7, color=RED))
    for x in [0.155, 0.255, 0.355, 0.455]:
        ax.add_patch(FancyArrowPatch((x, y + 0.12), (x - 0.065, y + 0.12), transform=ax.transAxes,
                                     arrowstyle="-|>", mutation_scale=11,
                                     linewidth=1.7, color=GREEN))


def model_panel(filename, heading, subtitle, system_title, system_body, hamiltonian,
                basis_body, invariant_body, observable_body, draw_fn=None):
    fig, ax = base_figure()
    title(ax, heading, subtitle)
    box(ax, (0.03, 0.565), (0.50, 0.315), system_title, system_body,
        face=PALE_BLUE, edge=BLUE, body_width=45)
    if draw_fn:
        draw_fn(ax)
    box(ax, (0.56, 0.565), (0.41, 0.315), "HAMILTONIAN", hamiltonian,
        face=PALE_GREEN, edge=GREEN, title_size=10.8, body_size=9.8, body_width=36)
    box(ax, (0.03, 0.390), (0.94, 0.135), "BASIS / COUPLINGS", basis_body,
        face=PALE_GOLD, edge=GOLD, body_width=76)
    box(ax, (0.03, 0.220), (0.94, 0.135), "SPECTRUM / INVARIANT", invariant_body,
        face=PALE_BLUE, edge=BLUE, body_width=76)
    box(ax, (0.03, 0.050), (0.94, 0.135), "BOUNDARY / OBSERVABLE", observable_body,
        face=PALE_RED, edge=RED, body_width=76)
    save(fig, filename)


def ssh(path):
    model_panel(
        path, "SSH CHAIN", "From dimerized bonds to winding and end states",
        "PHYSICAL SYSTEM", "One-dimensional bipartite chain with alternating intracell and intercell hopping.",
        "$H(k)=[t_1+t_2\\cos k]\\,\\sigma_x+t_2\\sin k\\,\\sigma_y$\nChiral symmetry: sigma_z H(k) sigma_z = -H(k)",
        "Basis: (A,B) in each cell.\nControls: t1, t2.\nGap closes at |t1|=|t2|.",
        "The d-vector winds around the origin when |t2|>|t1|.\nZak phase is quantized by chiral/inversion structure.",
        "An open chain has exponentially localized zero-energy end modes in the nontrivial dimerization.",
        lambda ax: draw_chain(ax, y=0.635, alternating=True),
    )


def rice(path):
    def draw(ax):
        draw_chain(ax, y=0.635, alternating=True)
        ax.text(0.12, 0.585, "+Delta", transform=ax.transAxes, fontsize=8.5, color=RED)
        ax.text(0.21, 0.585, "-Delta", transform=ax.transAxes, fontsize=8.5, color=GREEN)
        ax.add_patch(FancyArrowPatch((0.40, 0.595), (0.49, 0.645), transform=ax.transAxes,
                                     arrowstyle="-|>", mutation_scale=11, color=BLUE))
    model_panel(
        path, "RICE-MELE PUMP", "A gapped cycle converts polarization change into transported charge",
        "PHYSICAL SYSTEM", "Dimerized chain with a staggered onsite potential varied cyclically in time.",
        "$H(k,t)=[t_1(t)+t_2(t)\\cos k]\\sigma_x$\n$+t_2(t)\\sin k\\sigma_y+\\Delta(t)\\sigma_z$",
        "Basis: two sublattices.\nControls: dimerization and staggered potential.\nThe loop avoids the gap-closing point.",
        "The occupied band over (k,t) carries a pump Chern number.\nPolarization changes continuously during the cycle.",
        "One adiabatic cycle transports an integer charge when the band remains occupied and the gap stays open.",
        draw,
    )


def qwz(path):
    def draw(ax):
        draw_square_lattice(ax, origin=(0.075, 0.595), nx=4, ny=3, w=0.40, h=0.085)
        ax.add_patch(FancyArrowPatch((0.09, 0.715), (0.48, 0.715), transform=ax.transAxes,
                                     arrowstyle="-|>", mutation_scale=12, color=RED, linewidth=1.8))
        ax.text(0.22, 0.730, "chiral edge", transform=ax.transAxes, fontsize=8.4, color=RED)
    model_panel(
        path, "QWZ CHERN INSULATOR", "Two-dimensional band inversion, Berry curvature, and chiral transport",
        "PHYSICAL SYSTEM", "Two-orbital square-lattice model with a momentum-dependent mass term.",
        "$H(\\mathbf{k})=\\sin k_x\\,\\sigma_x+\\sin k_y\\,\\sigma_y$\n$+[m+\\cos k_x+\\cos k_y]\\sigma_z$",
        "Basis: two orbitals or pseudospins.\nControl: mass m.\nGap closings at high-symmetry momenta separate phases.",
        "Integrating Berry curvature over the Brillouin zone gives the integer Chern number C.",
        "A nonzero C produces chiral edge spectral flow and Hall response $\\sigma_{xy}=C e^2/h$ in the ideal filled-band limit.",
        draw,
    )


def bhz(path):
    def draw(ax):
        ax.add_patch(Rectangle((0.08, 0.595), 0.38, 0.095, transform=ax.transAxes,
                               facecolor="white", edgecolor=BLUE, linewidth=1.2))
        draw_edge_arrows(ax, y=0.600)
        ax.text(0.19, 0.720, "time-reversed edge pair", transform=ax.transAxes,
                fontsize=8.6, color=MUTED)
    model_panel(
        path, "BHZ QUANTUM SPIN HALL MODEL", "Time reversal pairs Dirac blocks and protects helical edges",
        "PHYSICAL SYSTEM", "Quantum-well electron and hole orbitals arranged into two time-reversal-related blocks.",
        "$H_{BHZ}(\\mathbf{k})=\\mathrm{diag}[h(\\mathbf{k}),h^*(-\\mathbf{k})]$\n$h=A k_x\\sigma_x+A k_y\\sigma_y+[M-Bk^2]\\sigma_z$",
        "Basis: electron/hole orbitals times Kramers partners.\nControls: M/B and inversion-breaking perturbations.",
        "Band inversion changes the Z2 class.\nWilson-loop partner switching provides a gauge-invariant diagnosis.",
        "An open sample supports counterpropagating helical edge states related by time reversal; elastic single-particle backscattering is constrained.",
        draw,
    )


def bbh(path):
    def draw(ax):
        ox, oy = 0.10, 0.600
        for i in range(2):
            for j in range(2):
                x, y = ox + i * 0.30, oy + j * 0.075
                ax.add_patch(Circle((x, y), 0.014, transform=ax.transAxes,
                                    facecolor="white", edgecolor=BLUE, linewidth=1.4))
        ax.add_line(Line2D([ox, ox + 0.30], [oy, oy], transform=ax.transAxes, color=GOLD, linewidth=4))
        ax.add_line(Line2D([ox, ox + 0.30], [oy + 0.075, oy + 0.075], transform=ax.transAxes, color=GOLD, linewidth=4))
        ax.add_line(Line2D([ox, ox], [oy, oy + 0.075], transform=ax.transAxes, color=GREEN, linewidth=2))
        ax.add_line(Line2D([ox + 0.30, ox + 0.30], [oy, oy + 0.075], transform=ax.transAxes, color=GREEN, linewidth=2))
        ax.text(0.17, 0.720, "four-site unit cell", transform=ax.transAxes, fontsize=8.5, color=MUTED)
    model_panel(
        path, "BBH QUADRUPOLE MODEL", "Crystalline symmetry organizes nested topology and corner states",
        "PHYSICAL SYSTEM", "Two-dimensional lattice with four sites per cell and alternating gamma/lambda bonds.",
        "$H(\\mathbf{k})=\\sum_{a=1}^{4} d_a(\\mathbf{k})\\,\\Gamma_a$\nMirror/rotation constraints quantize multipole data.",
        "Basis: four sublattice orbitals.\nControls: intracell gamma and intercell lambda couplings.\nFlux/sign pattern matters.",
        "Nested Wilson loops diagnose a quantized quadrupole phase when the required crystalline symmetries and spectral gaps are present.",
        "Open boundaries can carry gapped edges, edge polarization, and in-gap corner states: a higher-order bulk-boundary hierarchy.",
        draw,
    )


def kitaev(path):
    def draw(ax):
        xs = [0.09 + 0.075 * i for i in range(6)]
        for x in xs:
            ax.add_patch(Circle((x, 0.635), 0.012, transform=ax.transAxes,
                                facecolor="white", edgecolor=BLUE, linewidth=1.2))
        for x1, x2 in zip(xs[:-1], xs[1:]):
            ax.add_line(Line2D([x1 + 0.012, x2 - 0.012], [0.635, 0.635], transform=ax.transAxes,
                               color=GREEN, linewidth=2.0))
        ax.add_patch(Circle((xs[0] - 0.03, 0.635), 0.016, transform=ax.transAxes,
                            facecolor=PALE_RED, edgecolor=RED, linewidth=1.7))
        ax.add_patch(Circle((xs[-1] + 0.03, 0.635), 0.016, transform=ax.transAxes,
                            facecolor=PALE_RED, edgecolor=RED, linewidth=1.7))
        ax.text(0.15, 0.720, "Majorana end modes", transform=ax.transAxes, fontsize=8.5, color=RED)
    model_panel(
        path, "KITAEV TOPOLOGICAL SUPERCONDUCTOR", "Particle-hole-symmetric BdG structure and Majorana boundary modes",
        "PHYSICAL SYSTEM", "Spinless fermion chain with hopping, chemical potential, and nearest-neighbor p-wave pairing.",
        "$H(k)=(-\\mu-2t\\cos k)\\tau_z+2\\Delta\\sin k\\tau_y$\nParticle-hole symmetry relates positive and negative energies.",
        "Basis: Nambu particle/hole spinor.\nControls: mu, t, Delta.\nBulk gap closes at |mu|=2|t| for nonzero pairing.",
        "A winding or Pfaffian sign distinguishes the topological interval from the trivial phase.",
        "An open topological chain has Majorana end modes; finite length produces exponentially small hybridization splitting.",
        draw,
    )


def weyl(path):
    def draw(ax):
        ax.add_patch(Circle((0.27, 0.640), 0.024, transform=ax.transAxes,
                            facecolor=PALE_RED, edgecolor=RED, linewidth=1.7))
        for ang in [20, 85, 150, 215, 280, 345]:
            a = math.radians(ang)
            ax.add_patch(FancyArrowPatch((0.27, 0.640), (0.27 + 0.14 * math.cos(a), 0.640 + 0.050 * math.sin(a)),
                                         transform=ax.transAxes, arrowstyle="-|>", mutation_scale=10,
                                         color=BLUE, linewidth=1.3))
        ax.text(0.18, 0.720, "Berry-flux monopole", transform=ax.transAxes, fontsize=8.5, color=MUTED)
    model_panel(
        path, "WEYL HAMILTONIAN", "An isolated linear node carries quantized chirality",
        "PHYSICAL SYSTEM", "Three-dimensional two-band semimetal with isolated nondegenerate band-touching points.",
        "$H_\\chi(\\mathbf{q})=\\chi(v_x q_x\\sigma_x+v_y q_y\\sigma_y+v_z q_z\\sigma_z)$\nChirality: $\\chi=\\mathrm{sgn}(v_xv_yv_z)$",
        "Basis: two crossing bands.\nControls: node separation and symmetry-allowed tilts/masses.\nA generic Weyl node is stable to small perturbations.",
        "The Berry flux through a closed surface enclosing one node is quantized and equals its chirality.",
        "Opposite-chirality nodes are connected by surface Fermi arcs; annihilation requires bringing compensating charges together.",
        draw,
    )


def nodal(path):
    def draw(ax):
        t = [2 * math.pi * i / 160 for i in range(161)]
        xs = [0.27 + 0.15 * math.cos(v) for v in t]
        ys = [0.59 + 0.055 * math.sin(v) for v in t]
        ax.plot(xs, ys, transform=ax.transAxes, color=BLUE, linewidth=2.5)
        ax.add_patch(FancyArrowPatch((0.27, 0.585), (0.27, 0.695), transform=ax.transAxes,
                                     arrowstyle="-|>", mutation_scale=11, color=RED))
        ax.text(0.11, 0.720, "nodal ring in momentum space", transform=ax.transAxes, fontsize=8.5, color=MUTED)
    model_panel(
        path, "NODAL-LINE SEMIMETAL", "A symmetry-protected one-dimensional degeneracy manifold",
        "PHYSICAL SYSTEM", "Three-dimensional two-band model whose zero-energy conditions form a closed line rather than isolated points.",
        "$H(\\mathbf{k})=[m-k_x^2-k_y^2]\\sigma_x+v k_z\\sigma_z$\nThe ring occurs at $k_z=0$ and $k_x^2+k_y^2=m$.",
        "Basis: two crossing bands.\nProtection: PT, mirror, or another constraint forbidding the missing mass term.\nA symmetry-breaking term gaps the ring.",
        "A loop linked with the nodal line carries a quantized Berry phase under the protecting structure.",
        "The surface projection can support drumhead-like states; their detailed dispersion is boundary dependent.",
        draw,
    )


def table_figure(path, heading, subtitle, columns, rows, widths=None, font=8.4):
    fig, ax = base_figure()
    title(ax, heading, subtitle)
    widths = widths or [1.0 / len(columns)] * len(columns)
    header_limits = [max(8, int(70 * w)) for w in widths]
    body_limits = [max(9, int(104 * w)) for w in widths]
    wrapped_columns = [wrap(str(value), header_limits[i]) for i, value in enumerate(columns)]
    wrapped_rows = [
        [wrap(str(value), body_limits[i]) for i, value in enumerate(row)]
        for row in rows
    ]
    tab = ax.table(cellText=wrapped_rows, colLabels=wrapped_columns, cellLoc="left", colLoc="left",
                   bbox=[0.025, 0.060, 0.95, 0.820], colWidths=widths)
    tab.auto_set_font_size(False)
    tab.set_fontsize(font)
    for (r, c), cell in tab.get_celld().items():
        cell.set_edgecolor(EDGE)
        cell.set_linewidth(0.8)
        cell.PAD = 0.035
        if r == 0:
            cell.set_facecolor(BLUE)
            cell.get_text().set_color("white")
            cell.get_text().set_weight("bold")
            cell.get_text().set_fontsize(font + 0.3)
        elif r % 2:
            cell.set_facecolor(PALE_BLUE)
        else:
            cell.set_facecolor("white")
        cell.get_text().set_wrap(True)
        cell.get_text().set_va("center")
    save(fig, path)

def taxonomy(path):
    rows = [
        ["SSH", "1D; chiral/inversion", "winding / Zak phase", "zero-energy end mode"],
        ["Rice-Mele", "1D + cyclic parameter", "pump Chern number", "integer transported charge"],
        ["QWZ", "2D; class A", "Chern number", "chiral edge / Hall response"],
        ["BHZ", "2D; time reversal", "Z2 / Wilson flow", "helical Kramers edge pair"],
        ["BBH", "2D; crystalline", "nested Wilson / multipole", "edge polarization / corners"],
        ["Kitaev", "1D BdG; particle-hole", "winding / Pfaffian sign", "Majorana end modes"],
        ["Weyl", "3D; isolated nodes", "Berry-flux chirality", "surface Fermi arc"],
        ["Nodal line", "3D; PT or mirror", "linked-loop Berry phase", "surface projection states"],
    ]
    table_figure(path, "TOPOLOGICAL HAMILTONIAN TAXONOMY",
                 "Dimension and protecting structure determine the appropriate invariant and boundary test",
                 ["MODEL", "DIMENSION / PROTECTION", "BULK DIAGNOSTIC", "BOUNDARY / RESPONSE"], rows,
                 widths=[0.13, 0.27, 0.26, 0.30], font=8.5)


def decision(path):
    fig, ax = base_figure()
    title(ax, "SYMMETRY - INVARIANT - BOUNDARY WORKFLOW",
          "Choose the diagnostic from the actual Hamiltonian, then test it independently")
    nodes = [
        ("1  HAMILTONIAN", "State space, couplings, dimension, filling, and boundary conditions."),
        ("2  SYMMETRY", "Unitary, antiunitary, crystalline, particle-hole, and chiral constraints."),
        ("3  GAP / NODE", "Bulk gap, mobility gap, quasienergy gap, or a symmetry-protected zero set."),
        ("4  INVARIANT", "Winding, Chern, Z2, Wilson loop, real-space marker, or many-body phase."),
        ("5  INDEPENDENT TEST", "Boundary spectrum, pump, flux insertion, response, and disorder or size scaling."),
    ]
    ys = [0.770, 0.640, 0.510, 0.380, 0.250]
    for idx, ((head, body), y) in enumerate(zip(nodes, ys)):
        box(ax, (0.07, y), (0.86, 0.095), head, body,
            face=PALE_BLUE if idx % 2 == 0 else PALE_GREEN,
            edge=BLUE if idx % 2 == 0 else GREEN,
            title_size=9.8, body_size=8.9, body_width=105)
        if idx < len(nodes) - 1:
            ax.add_patch(FancyArrowPatch((0.50, y - 0.008), (0.50, y - 0.030), transform=ax.transAxes,
                                         arrowstyle="-|>", mutation_scale=12, color=GOLD, linewidth=1.8))
    box(ax, (0.06, 0.045), (0.42, 0.145), "ROBUSTNESS CHECK",
        "Keep the protecting structure and gap definition explicit. Vary size, mesh, disorder, boundary, and numerical tolerance.",
        face=PALE_GOLD, edge=GOLD, body_width=34)
    box(ax, (0.52, 0.045), (0.42, 0.145), "REJECTION RULE",
        "Reject the topological claim when the invariant is undefined, unconverged, or disconnected from the measured response.",
        face=PALE_RED, edge=RED, body_width=34)
    save(fig, path)

def reference_a(path):
    rows = [
        ["SSH", "A/B sublattices; t1,t2", "two-band chiral H(k)", "gap + winding", "end mode"],
        ["Rice-Mele", "A/B; t1,t2,Delta(t)", "SSH + staggered mass", "pump Chern", "pumped charge"],
        ["QWZ", "two orbitals; mass m", "sin kx, sin ky, mass", "Chern number", "chiral edge / Hall"],
        ["BHZ", "E/H orbitals; Kramers", "time-reversed Dirac blocks", "Z2 / Wilson flow", "helical edge"],
    ]
    table_figure(path, "HAMILTONIAN REFERENCE MATRIX I",
                 "Band and pump models: setup -> basis/couplings -> Hamiltonian -> invariant -> observable",
                 ["MODEL", "BASIS / COUPLINGS", "HAMILTONIAN", "SPECTRUM / INVARIANT", "BOUNDARY / OBSERVABLE"], rows,
                 widths=[0.12, 0.22, 0.23, 0.21, 0.20], font=8.25)


def reference_b(path):
    rows = [
        ["BBH", "four sites; gamma/lambda", "four-band Gamma matrix", "nested Wilson / quadrupole", "edge polarization / corners"],
        ["Kitaev", "Nambu basis; mu,t,Delta", "1D BdG", "winding / Pfaffian", "Majorana ends"],
        ["Weyl", "two bands; velocities", "linear 3D Pauli node", "chirality / flux", "Fermi arc"],
        ["Nodal line", "two bands; mass, velocity", "ring-zero Hamiltonian", "linked Berry phase", "surface projection"],
    ]
    table_figure(path, "HAMILTONIAN REFERENCE MATRIX II",
                 "Higher-order, superconducting, and semimetal models in the same visual grammar",
                 ["MODEL", "BASIS / COUPLINGS", "HAMILTONIAN", "SPECTRUM / INVARIANT", "BOUNDARY / OBSERVABLE"], rows,
                 widths=[0.12, 0.22, 0.23, 0.21, 0.20], font=8.25)


def symmap(path):
    rows = [
        ["Chiral", "off-diagonal / spectral symmetry", "1D winding", "zero-energy end structure", "break chiral term"],
        ["Time reversal", "Kramers pairing", "Z2 / Wilson partner flow", "helical edge", "TR-breaking perturbation"],
        ["Particle-hole", "BdG redundancy", "winding / Pfaffian", "Majorana boundary mode", "gap + parity checks"],
        ["Crystalline", "mirror / rotation / inversion", "indicators / nested Wilson", "corner, hinge, polarization", "symmetry-preserving disorder"],
        ["No protecting symmetry", "complex occupied bundle", "Chern number", "chiral edge / Hall", "mobility-gap scaling"],
    ]
    table_figure(path, "SYMMETRY - INVARIANT - BOUNDARY MAP",
                 "Interpret a boundary signature only after stating its protection, invariant, and robustness test",
                 ["STRUCTURE", "HAMILTONIAN CONSTRAINT", "INVARIANT", "BOUNDARY / RESPONSE", "ROBUSTNESS TEST"], rows,
                 widths=[0.14, 0.24, 0.20, 0.21, 0.19], font=8.15)


def coverage(path):
    models = ["SSH", "Rice-Mele", "QWZ", "BHZ", "BBH", "Kitaev", "Weyl", "Nodal line"]
    rows = [[model, "PASS", "PASS", "PASS", "PASS", "PASS"] for model in models]
    fig, ax = base_figure()
    title(ax, "CHAPTER 62 VISUAL COVERAGE",
          "Each canonical model is checked against the same five-column teaching contract")
    columns = ["MODEL", "PHYSICAL\nSYSTEM", "BASIS /\nCOUPLINGS", "HAMILTONIAN", "SPECTRUM /\nINVARIANT", "BOUNDARY /\nOBSERVABLE"]
    tab = ax.table(cellText=rows, colLabels=columns, cellLoc="center", colLoc="center",
                   bbox=[0.03, 0.245, 0.94, 0.625],
                   colWidths=[0.12, 0.16, 0.17, 0.17, 0.19, 0.19])
    tab.auto_set_font_size(False)
    tab.set_fontsize(8.5)
    for (r, c), cell in tab.get_celld().items():
        cell.set_edgecolor(EDGE)
        cell.set_linewidth(0.8)
        cell.PAD = 0.035
        if r == 0:
            cell.set_facecolor(BLUE)
            cell.get_text().set_color("white")
            cell.get_text().set_weight("bold")
            cell.get_text().set_fontsize(8.6)
        elif r % 2:
            cell.set_facecolor(PALE_BLUE)
        else:
            cell.set_facecolor(PALE_GREEN)
        if r > 0 and c > 0:
            cell.get_text().set_color(GREEN)
            cell.get_text().set_weight("bold")
        cell.get_text().set_wrap(True)
        cell.get_text().set_va("center")
    box(ax, (0.05, 0.060), (0.90, 0.125), "ACCEPTANCE RULE",
        "No model is represented by a plot alone. Each row connects the physical mechanism, active basis, Hamiltonian terms, bulk diagnostic, and an observable or boundary consequence.",
        face=PALE_GOLD, edge=GOLD, title_size=9.7, body_size=8.8, body_width=82)
    save(fig, path)

def grammar(path):
    fig, ax = base_figure()
    title(ax, "VOLUME VIII HAMILTONIAN VISUAL GRAMMAR",
          "Read from the physical setup to an observable consequence or explicit falsifier")
    items = [
        ("1  PHYSICAL SYSTEM", "Geometry, platform, active degrees of freedom, and experimental boundary.", PALE_BLUE, BLUE),
        ("2  BASIS / COUPLINGS", "States, sectors, couplings, controls, and the retained Hilbert space.", PALE_GOLD, GOLD),
        ("3  HAMILTONIAN", "Operator terms, parameter dependence, and declared symmetry constraints.", PALE_GREEN, GREEN),
        ("4  STRUCTURE", "Spectrum, gap or node, invariant, convergence evidence, and regime of validity.", PALE_BLUE, BLUE),
        ("5  CONSEQUENCE", "Boundary state, response, experiment, breakdown mode, or rejection test.", PALE_RED, RED),
    ]
    ys = [0.755, 0.625, 0.495, 0.365, 0.235]
    for idx, ((head, body, face, edge), y) in enumerate(zip(items, ys)):
        box(ax, (0.07, y), (0.86, 0.100), head, body, face=face, edge=edge,
            title_size=9.8, body_size=8.9, body_width=105)
        if idx < len(items) - 1:
            ax.add_patch(FancyArrowPatch((0.50, y - 0.008), (0.50, y - 0.030), transform=ax.transAxes,
                                         arrowstyle="-|>", mutation_scale=12, color=INK, linewidth=1.4))
    box(ax, (0.06, 0.045), (0.42, 0.145), "QUANTITATIVE SUPPLEMENT",
        "Curves, spectra, convergence plots, and numerical benchmarks test one or more links in the chain.",
        face="white", edge=BLUE, body_width=34)
    box(ax, (0.52, 0.045), (0.42, 0.145), "FAILURE MODE",
        "A schematic or plot without a declared Hamiltonian-to-observable link does not satisfy the teaching contract.",
        face="white", edge=RED, body_width=34)
    save(fig, path)

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    parser.add_argument("--output-dir", default="generated/ch62/commit677_release")
    args = parser.parse_args()
    repo = Path(args.repo).resolve()
    out = (repo / args.output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)

    jobs = [
        ("ssh_release_panel.pdf", ssh),
        ("rice_mele_release_panel.pdf", rice),
        ("qwz_release_panel.pdf", qwz),
        ("bhz_release_panel.pdf", bhz),
        ("bbh_release_panel.pdf", bbh),
        ("kitaev_release_panel.pdf", kitaev),
        ("weyl_release_panel.pdf", weyl),
        ("nodal_line_release_panel.pdf", nodal),
        ("topological_hamiltonian_taxonomy_release.pdf", taxonomy),
        ("topology_decision_workflow_release.pdf", decision),
        ("hamiltonian_reference_matrix_a_release.pdf", reference_a),
        ("hamiltonian_reference_matrix_b_release.pdf", reference_b),
        ("symmetry_invariant_boundary_release.pdf", symmap),
        ("chapter62_visual_coverage_release.pdf", coverage),
        ("volume08_visual_grammar_release.pdf", grammar),
    ]
    for name, func in jobs:
        func(out / name)

    manifest = {
        "schema_version": "1.0",
        "commit": 677,
        "generator": "examples/python/ch62/generate_commit677_release_visuals.py",
        "files": [
            {"path": f"generated/ch62/commit677_release/{name}",
             "bytes": (out / name).stat().st_size,
             "sha256": sha256(out / name)}
            for name, _ in jobs
        ],
    }
    manifest_path = out / "commit677_release_visual_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(json.dumps({"output_dir": str(out), "generated": len(jobs), "manifest": str(manifest_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
