"""Verify the authored inward-winding tetrahedron against the canonical mesh."""
import argparse
import json
from pathlib import Path

from scientific_cgal_corpus import CORPUS, geometry, sha, verify_corpus


ROOT = CORPUS / 'orientation'


def vertices_faces(path):
    vertices, faces = [], []
    for line in path.read_text(encoding='utf-8').splitlines():
        fields = line.split()
        if not fields or fields[0] == '#':
            continue
        if fields[0] == 'v' and len(fields) == 4:
            vertices.append(tuple(float(value) for value in fields[1:]))
        elif fields[0] == 'f' and len(fields) == 4:
            faces.append(tuple(int(value) for value in fields[1:]))
        else:
            raise ValueError('Orientation fixture uses unsupported OBJ geometry.')
    return vertices, faces


def verify(root=ROOT):
    corpus = verify_corpus()
    root = Path(root).resolve(strict=True)
    manifest_path = root / 'manifest.v1.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    original = CORPUS / 'closed-tetra.obj'
    inward = (root / 'inward-tetra.obj').resolve(strict=True)
    if (manifest.get('schemaVersion') != 1
            or manifest.get('kind') != 'scientific.cgal-orientation-fixture'
            or manifest.get('license') != 'CC0-1.0'
            or manifest.get('source') != 'Project-authored face reversal of closed-tetra.obj'
            or manifest.get('sourceFixtureId') != 'closed-tetra'
            or manifest.get('fixtureId') != 'inward-tetra' or manifest.get('fixtureVersion') != 1
            or manifest.get('path') != 'inward-tetra.obj' or inward.parent != root
            or manifest.get('sourceSha256') != sha(original)
            or manifest.get('sha256') != sha(inward)
            or corpus['fixtures'][0]['sha256'] != manifest['sourceSha256']):
        raise ValueError('CGAL orientation fixture provenance or hash changed.')
    source_vertices, source_faces = vertices_faces(original)
    inward_vertices, inward_faces = vertices_faces(inward)
    source_geometry, inward_geometry = geometry(original), geometry(inward)
    if (source_vertices != inward_vertices or inward_faces != [tuple(reversed(face)) for face in source_faces]
            or len(inward_faces) != 4 or inward_geometry['boundaryEdges'] != 0
            or inward_geometry['degenerateFaces'] != 0
            or abs(inward_geometry['signedVolume'] + source_geometry['signedVolume']) > 1e-12
            or abs(inward_geometry['signedVolume'] - manifest['expectedSignedVolume']) > 1e-12):
        raise ValueError('CGAL inward fixture is not the exact closed face reversal.')
    return {'schemaVersion': 1, 'kind': 'scientific.cgal-orientation-fixture-verification',
            'manifestSha256': sha(manifest_path), 'sourceSha256': sha(original),
            'fixtureSha256': sha(inward), 'signedVolume': inward_geometry['signedVolume'],
            'verdict': 'passed'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('verify',))
    parser.add_argument('--root', type=Path, default=ROOT)
    options = parser.parse_args()
    print(json.dumps(verify(options.root), separators=(',', ':')))
