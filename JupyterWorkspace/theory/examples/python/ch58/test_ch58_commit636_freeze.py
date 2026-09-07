from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[3]
MANIFEST=ROOT/'project_records/current/ch58/commit636_freeze_manifest.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def test_commit636_ch58_freeze_manifest_exists():assert MANIFEST.exists()
def test_commit636_ch58_frozen_files_unchanged():
 data=json.loads(MANIFEST.read_text(encoding='utf-8'));missing=[];bad=[]
 for rel,want in data['files'].items():
  p=ROOT/rel
  if not p.exists():missing.append(rel)
  elif sha(p)!=want:bad.append(rel)
 assert not missing, 'Missing frozen files: '+', '.join(missing)
 assert not bad, 'Modified frozen files: '+', '.join(bad)
