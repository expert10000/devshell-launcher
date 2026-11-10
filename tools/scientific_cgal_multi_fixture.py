"""Verify the authored two-square-hole cube against its closed source."""
import argparse
import json
from pathlib import Path

from scientific_cgal_corpus import sha
from scientific_cgal_mesh_metrics import metrics, parse_obj
from scientific_cgal_quad_fixture import FIXTURE_ROOT as QUAD_ROOT, verify as verify_quad


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT / 'scientific/fixtures/cgal-repair-multi'
EXPECTED_REMOVED = [[1, 3, 2], [1, 4, 3], [5, 6, 7], [5, 7, 8]]


def verify(root=FIXTURE_ROOT):
    root = Path(root).resolve(strict=True)
    manifest_path = root / 'manifest.v1.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    closed = QUAD_ROOT / 'cube-closed.obj'
    opened = root / 'cube-two-square-holes.obj'
    quad = verify_quad()
    if (manifest.get('schemaVersion') != 1
            or manifest.get('kind') != 'scientific.cgal-two-square-holes-fixture'
            or manifest.get('license') != 'CC0-1.0'
            or manifest.get('source') != 'Project-authored exact top-and-bottom removal from the authored unit cube'
            or manifest.get('closedFixture') != '../cgal-repair-quad/cube-closed.obj'
            or manifest.get('openFixture') != opened.name
            or manifest.get('removedFaces') != EXPECTED_REMOVED
            or manifest.get('closedSha256') != quad['closedSha256']
            or manifest.get('openSha256') != sha(opened)
            or {path.name for path in root.glob('*.obj')} != {opened.name}):
        raise ValueError('CGAL multi-hole fixture identity or rights changed.')
    closed_vertices, closed_faces = parse_obj(closed)
    open_vertices, open_faces = parse_obj(opened)
    removed = {tuple(index-1 for index in face) for face in EXPECTED_REMOVED}
    if (open_vertices != closed_vertices
            or open_faces != [face for face in closed_faces if face not in removed]
            or len(closed_faces) - len(open_faces) != 4):
        raise ValueError('CGAL multi-hole fixture is not the exact top-and-bottom removal.')
    measured = metrics(opened)
    if any((abs(measured[key] - value) > 1e-12 if isinstance(value, float)
            else measured[key] != value) for key, value in manifest['expected'].items()):
        raise ValueError('CGAL multi-hole fixture topology changed.')
    return {'schemaVersion': 1, 'kind': 'scientific.cgal-two-square-holes-fixture-check',
            'manifestSha256': sha(manifest_path), 'quadManifestSha256': quad['manifestSha256'],
            'closedSha256': sha(closed), 'openSha256': sha(opened),
            'metrics': measured, 'verdict': 'passed'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('verify',))
    parser.add_argument('--root', default=str(FIXTURE_ROOT))
    options = parser.parse_args()
    print(json.dumps(verify(options.root), separators=(',', ':')))
