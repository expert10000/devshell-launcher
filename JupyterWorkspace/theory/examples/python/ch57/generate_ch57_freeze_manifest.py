"""Generate the immutable Chapter 57 freeze manifest for Commit 631."""
from __future__ import annotations
from pathlib import Path
import hashlib
import json
import sys
from datetime import datetime, timezone

LOCKED_ROOTS = [
    "book/development/volume08_schrodinger_hamiltonian_physics/chapters/chapter57_spin_exchange_and_magnetic_hamiltonians",
    "figures/ch57",
    "examples/python/ch57",
    "generated/ch57/computational",
]
EXCLUDED_PARTS = {"__pycache__", ".pytest_cache"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def locked_files(repo: Path):
    out = []
    for rel_root in LOCKED_ROOTS:
        base = repo / rel_root
        if not base.exists():
            continue
        for p in sorted(base.rglob("*")):
            if not p.is_file():
                continue
            rel_parts = p.relative_to(repo).parts
            if any(part in EXCLUDED_PARTS for part in rel_parts):
                continue
            if p.suffix.lower() in EXCLUDED_SUFFIXES:
                continue
            out.append(p)
    return out


def main():
    if len(sys.argv) != 3:
        raise SystemExit("usage: generate_ch57_freeze_manifest.py REPO OUTPUT_JSON")
    repo = Path(sys.argv[1]).resolve()
    out = Path(sys.argv[2]).resolve()
    files = locked_files(repo)
    if not files:
        raise SystemExit("no Chapter 57 freeze files found")

    entries = []
    for p in files:
        rel = p.relative_to(repo).as_posix()
        entries.append({
            "path": rel,
            "sha256": sha256(p),
            "bytes": p.stat().st_size,
        })

    payload = {
        "schema": 1,
        "commit": 631,
        "chapter": 57,
        "title": "Spin, Exchange, and Magnetic Hamiltonians",
        "status": "FROZEN",
        "freeze_policy": (
            "Chapter 57 scientific/source/figure/computational content is immutable after Commit 631. "
            "Later changes require an explicit erratum or freeze-revision commit and regeneration of this manifest."
        ),
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "locked_roots": LOCKED_ROOTS,
        "file_count": len(entries),
        "files": entries,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "manifest": out.relative_to(repo).as_posix() if repo in out.parents else str(out),
        "file_count": len(entries),
        "status": "FROZEN",
    }, indent=2))


if __name__ == "__main__":
    main()
