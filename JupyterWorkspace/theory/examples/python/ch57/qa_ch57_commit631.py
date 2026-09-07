"""Chapter 57 freeze QA summary for Commit 631."""
from __future__ import annotations
from pathlib import Path
import json
import re
import sys

def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: qa_ch57_commit631.py REPO")
    repo = Path(sys.argv[1]).resolve()
    chapter = repo / "book/development/volume08_schrodinger_hamiltonian_physics/chapters/chapter57_spin_exchange_and_magnetic_hamiltonians"
    secdir = chapter / "sections"
    if not secdir.exists():
        raise SystemExit(f"missing Chapter 57 sections: {secdir}")

    tex_files = sorted(chapter.rglob("*.tex"))
    all_text = "\n".join(p.read_text(encoding="utf-8", errors="ignore") for p in tex_files)
    labels = re.findall(r"\\label\{([^}]+)\}", all_text)
    duplicates = sorted({x for x in labels if labels.count(x) > 1})

    section_files = sorted(secdir.glob("57_*.tex"))
    includegraphics = re.findall(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", all_text)
    input_figures = re.findall(r"\\input\{(figures/ch57/[^}]+)\}", all_text)

    missing = []
    for ref in includegraphics:
        if ref.startswith("generated/ch57/"):
            p = repo / ref
            if p.suffix:
                candidates = [p]
            else:
                candidates = [p.with_suffix(s) for s in [".pdf", ".png", ".jpg", ".jpeg"]]
            if not any(c.exists() for c in candidates):
                missing.append(ref)
    for ref in input_figures:
        p = repo / ref
        if not p.suffix:
            p = p.with_suffix(".tex")
        if not p.exists():
            missing.append(ref)

    # Pedagogical counts are reported, not used as brittle freeze gates; the established
    # Chapter 57 regression suite remains the authoritative quota gate.
    exercise_items = 0
    hint_items = 0
    solution_markers = 0
    for p in section_files:
        name = p.name.lower()
        txt = p.read_text(encoding="utf-8", errors="ignore")
        items = len(re.findall(r"(?m)^\s*\\item\b", txt))
        if "exercise" in name:
            exercise_items += items
        if "hint" in name:
            hint_items += items
        if "solution" in name:
            solution_markers += len(re.findall(r"(?i)complete solution|\\subsection\*?\{[^}]*solution", txt))

    out = {
        "chapter": 57,
        "section_files": len(section_files),
        "labels": len(labels),
        "duplicate_labels": duplicates,
        "missing_ch57_figure_refs": sorted(set(missing)),
        "reported_exercise_items_in_named_files": exercise_items,
        "reported_hint_items_in_named_files": hint_items,
        "reported_solution_markers_in_named_files": solution_markers,
        "qa_pass": not duplicates and not missing,
    }
    print(json.dumps(out, indent=2))
    if duplicates or missing:
        raise SystemExit(1)

if __name__ == "__main__":
    main()
