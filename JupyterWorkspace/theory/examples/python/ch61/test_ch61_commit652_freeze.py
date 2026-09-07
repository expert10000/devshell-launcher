from pathlib import Path
import hashlib,json

ROOT=Path(__file__).resolve().parents[3]
MANIFEST=ROOT/"project_records/freeze/volume08/chapter61_commit652_freeze.json"
TEXT_EXT={".tex",".py",".md",".json"}

def digest(p):
    data=p.read_bytes()
    if p.suffix.lower() in TEXT_EXT:
        data=data.replace(b"\r\n",b"\n").replace(b"\r",b"\n")
    return hashlib.sha256(data).hexdigest()

def test_chapter61_commit652_freeze_manifest_matches():
    data=json.loads(MANIFEST.read_text(encoding="utf-8"))
    missing=[]; changed=[]
    for item in data["files"]:
        p=ROOT/item["path"]
        if not p.exists(): missing.append(item["path"])
        elif digest(p)!=item["sha256"]: changed.append(item["path"])
    assert not missing, f"Missing frozen Chapter 61 files: {missing}"
    assert not changed, f"Modified frozen Chapter 61 files: {changed}"
