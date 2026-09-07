
from pathlib import Path
import hashlib, json

def test_ch59_commit640_freeze():
    repo=Path(__file__).resolve().parents[3]
    manifest=repo/"project_records/current/ch59/commit640_freeze_manifest.json"
    assert manifest.exists(), "Commit 640 Chapter 59 freeze manifest missing"
    data=json.loads(manifest.read_text(encoding="utf-8"))
    assert data["status"]=="FROZEN"
    for row in data["files"]:
        p=repo/row["path"]
        assert p.exists(), f"Frozen Chapter 59 file missing: {row['path']}"
        got=hashlib.sha256(p.read_bytes()).hexdigest()
        assert got==row["sha256"], f"Frozen Chapter 59 file changed: {row['path']}"
