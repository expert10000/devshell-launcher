from __future__ import annotations
from pathlib import Path
import re, json, sys

repo=Path(sys.argv[1]).resolve()
chapter=repo/"book/development/volume08_schrodinger_hamiltonian_physics/chapters/chapter57_spin_exchange_and_magnetic_hamiltonians"
secdir=chapter/"sections"
text="\n".join(p.read_text(encoding="utf-8",errors="ignore") for p in secdir.glob("*.tex"))
labels=re.findall(r"\\label\{([^}]+)\}",text)
dups=sorted({x for x in labels if labels.count(x)>1})

required=[
"liouvillian_single_spin_complex_plane.pdf",
"liouvillian_two_spin_complex_plane.pdf",
"liouvillian_exceptional_point.pdf",
"finite_chain_magnon_heatmap.pdf",
"disorder_clean_vs_localized.pdf",
"noise_models_coherence_comparison.pdf",
"superradiance_scaling.pdf",
]
figdir=repo/"generated/ch57/computational"
missing=[f for f in required if not (figdir/f).exists()]

commit630=[p for p in secdir.glob("57_*.tex") if "commit630" in p.name or any(k in p.name for k in [
"liouvillian_spectrum_single_spin","two_spin_liouvillian_spectra","liouvillian_gap_metastability",
"exceptional_points_jordan_dynamics","finite_chain_exact_propagation","disorder_localization_transport",
"noise_model_comparison","quantitative_superradiance_scaling","small_system_liouvillian_diagnostics",
"ch57_exercises_commit630","ch57_hints_solutions_commit630","commit630_prefreeze_qa"
])]

result={
"labels_total_ch57":len(labels),
"duplicate_labels":dups,
"missing_commit630_figures":missing,
"commit630_section_files_detected":len(commit630),
"figure_count_required":len(required),
}
print(json.dumps(result,indent=2))
if dups or missing or len(commit630)<12:
    raise SystemExit(1)
