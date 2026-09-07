"""Commit 631 immutable-layer regression test for frozen Chapter 57."""
from __future__ import annotations
from pathlib import Path
import hashlib
import json
import pytest

MANIFEST_REL = Path("project_records/frozen_locks/CH57_COMMIT631_FROZEN_CONTENT_SHA256.json")


def find_repo_root(start: Path) -> Path:
    for p in [start, *start.parents]:
        if (p / ".git").exists():
            return p
    pytest.skip("Git repository root not available for Chapter 57 freeze test")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def test_ch57_commit631_frozen_content_matches_manifest():
    repo = find_repo_root(Path(__file__).resolve())
    manifest_path = repo / MANIFEST_REL
    assert manifest_path.exists(), f"missing Chapter 57 freeze manifest: {manifest_path}"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert data["commit"] == 631
    assert data["chapter"] == 57
    assert data["status"] == "FROZEN"

    missing = []
    mismatches = []
    for item in data["files"]:
        p = repo / item["path"]
        if not p.exists():
            missing.append(item["path"])
            continue
        actual = sha256(p)
        if actual != item["sha256"]:
            mismatches.append({
                "path": item["path"],
                "expected": item["sha256"],
                "actual": actual,
            })

    assert not missing, f"frozen Chapter 57 files missing: {missing}"
    assert not mismatches, f"frozen Chapter 57 hash mismatches: {mismatches}"
