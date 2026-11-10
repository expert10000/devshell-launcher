"""Verify authored one-hole tetrahedron identity, rights and topology."""
import argparse
import json
from pathlib import Path

from scientific_cgal_corpus import CORPUS, sha, verify_corpus
from scientific_cgal_mesh_metrics import metrics, parse_obj


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT / 'scientific/fixtures/cgal-repair'


def verify(root=FIXTURE_ROOT):
    root = Path(root).resolve(strict=True)
    manifest_path = root / 'manifest.v1.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    source = CORPUS / 'closed-tetra.obj'
    fixture = root / 'tetra-one-hole.obj'
    corpus = verify_corpus()
    if (manifest.get('schemaVersion') != 1
            or manifest.get('kind') != 'scientific.cgal-hole-repair-fixture'
            or manifest.get('license') != 'CC0-1.0'
            or manifest.get('source') != 'Project-authored removal of one face from the authored closed tetrahedron'
            or manifest.get('sourceFixture') != '../cgal/closed-tetra.obj'
            or manifest.get('fixture') != fixture.name
            or manifest.get('removedFace') != [2, 3, 4]
            or manifest.get('sourceSha256') != sha(source)
            or manifest.get('fixtureSha256') != sha(fixture)
            or len(list(root.glob('*.obj'))) != 1):
        raise ValueError('CGAL repair fixture identity or rights changed.')
    source_vertices, source_faces = parse_obj(source)
    vertices, faces = parse_obj(fixture)
    if (vertices != source_vertices or faces != [face for face in source_faces
                                                  if [index+1 for index in face] != manifest['removedFace']]
            or len(source_faces) - len(faces) != 1):
        raise ValueError('CGAL repair fixture is not the authored one-face removal.')
    measured = metrics(fixture)
    if measured['maximumEdgeIncidence'] != 2 or any(
            abs(measured[key] - value) > 1e-12 if isinstance(value, float)
            else measured[key] != value for key, value in manifest['expected'].items()):
        raise ValueError('CGAL repair fixture topology changed.')
    return {'schemaVersion': 1, 'kind': 'scientific.cgal-hole-repair-fixture-check',
            'manifestSha256': sha(manifest_path), 'corpusManifestSha256': corpus['manifestSha256'],
            'sourceSha256': sha(source), 'fixtureSha256': sha(fixture),
            'metrics': measured, 'verdict': 'passed'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('verify',))
    parser.add_argument('--root', default=str(FIXTURE_ROOT))
    options = parser.parse_args()
    print(json.dumps(verify(options.root), separators=(',', ':')))
