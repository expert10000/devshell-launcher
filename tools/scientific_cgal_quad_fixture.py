"""Verify authored unit cube and its exact one-square-hole derivative."""
import argparse
import json
from pathlib import Path

from scientific_cgal_corpus import sha
from scientific_cgal_mesh_metrics import metrics, parse_obj


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT / 'scientific/fixtures/cgal-repair-quad'


def verify(root=FIXTURE_ROOT):
    root = Path(root).resolve(strict=True)
    manifest_path = root / 'manifest.v1.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    closed, opened = root / 'cube-closed.obj', root / 'cube-one-quad-hole.obj'
    if (manifest.get('schemaVersion') != 1
            or manifest.get('kind') != 'scientific.cgal-quad-hole-fixture'
            or manifest.get('license') != 'CC0-1.0'
            or manifest.get('source') != 'Project-authored triangulated unit cube and exact top-face removal'
            or manifest.get('closed') != closed.name or manifest.get('open') != opened.name
            or manifest.get('closedSha256') != sha(closed)
            or manifest.get('openSha256') != sha(opened)
            or manifest.get('removedFaces') != [[5, 6, 7], [5, 7, 8]]
            or {path.name for path in root.glob('*.obj')} != {closed.name, opened.name}):
        raise ValueError('CGAL quad-hole fixture identity or rights changed.')
    closed_vertices, closed_faces = parse_obj(closed)
    open_vertices, open_faces = parse_obj(opened)
    removed = [tuple(index-1 for index in face) for face in manifest['removedFaces']]
    if (open_vertices != closed_vertices or open_faces != [face for face in closed_faces
                                                            if face not in removed]
            or len(closed_faces) - len(open_faces) != 2):
        raise ValueError('CGAL quad-hole fixture is not the authored top-face removal.')
    checked = {}
    for key, path in (('Closed', closed), ('Open', opened)):
        measured, expected = metrics(path), manifest['expected' + key]
        if (measured['maximumEdgeIncidence'] != 2 or any(
                abs(measured[name] - value) > 1e-12 if isinstance(value, float)
                else measured[name] != value for name, value in expected.items())):
            raise ValueError('CGAL quad-hole fixture topology changed: ' + key)
        checked[key.lower()] = measured
    return {'schemaVersion': 1, 'kind': 'scientific.cgal-quad-hole-fixture-check',
            'manifestSha256': sha(manifest_path), 'closedSha256': sha(closed),
            'openSha256': sha(opened), 'metrics': checked, 'verdict': 'passed'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('verify',))
    parser.add_argument('--root', default=str(FIXTURE_ROOT))
    options = parser.parse_args()
    print(json.dumps(verify(options.root), separators=(',', ':')))
