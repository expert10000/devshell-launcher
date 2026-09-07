from pathlib import Path
import hashlib
ROOT=Path(__file__).resolve().parents[3]
MAN=ROOT/"project_records/current/volume08/chapter60_commit645_freeze_manifest.sha256"
def canonical_bytes(p):
    if p.suffix.lower()==".pdf": return p.read_bytes()
    return p.read_text(encoding="utf-8").replace("\r\n","\n").replace("\r","\n").encode("utf-8")
def test_chapter60_freeze_manifest_matches():
    assert MAN.exists()
    for line in MAN.read_text(encoding="utf-8").splitlines():
        if not line.strip(): continue
        h,rel=line.split("  ",1); p=ROOT/rel
        assert p.exists(), rel
        assert hashlib.sha256(canonical_bytes(p)).hexdigest()==h, rel
