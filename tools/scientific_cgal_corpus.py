"""Independent, bounded checks for the authored CGAL pathology fixtures."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re


CORPUS = Path(__file__).resolve().parents[1] / 'scientific/fixtures/cgal'
NAME = re.compile(r'[a-z][a-z0-9-]{0,63}\.obj\Z')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def geometry(path):
    if path.stat().st_size > 65536:
        raise ValueError('CGAL fixture exceeds 64 KiB.')
    vertices, faces = [], []
    for line in path.read_text(encoding='utf-8').splitlines():
        fields = line.split()
        if not fields or fields[0] == '#':
            continue
        if fields[0] == 'v' and len(fields) == 4:
            point = tuple(float(value) for value in fields[1:])
            if not all(math.isfinite(value) for value in point):
                raise ValueError('CGAL fixture has non-finite coordinates.')
            vertices.append(point)
        elif fields[0] == 'f' and len(fields) == 4:
            face = tuple(int(value) - 1 for value in fields[1:])
            if any(index < 0 or index >= len(vertices) for index in face):
                raise ValueError('CGAL fixture face references an invalid vertex.')
            faces.append(face)
        else:
            raise ValueError('CGAL fixture uses an unsupported OBJ directive.')
    if not vertices or not faces or len(vertices) > 1024 or len(faces) > 2048:
        raise ValueError('CGAL fixture geometry is empty or over budget.')
    edges = Counter(tuple(sorted((face[index], face[(index + 1) % 3])))
                    for face in faces for index in range(3))
    volume, degenerates = 0.0, 0
    for i, j, k in faces:
        a, b, c = (vertices[index] for index in (i, j, k))
        ab = tuple(b[n] - a[n] for n in range(3))
        ac = tuple(c[n] - a[n] for n in range(3))
        cross = (ab[1]*ac[2] - ab[2]*ac[1], ab[2]*ac[0] - ab[0]*ac[2],
                 ab[0]*ac[1] - ab[1]*ac[0])
        if sum(value * value for value in cross) <= 1e-24:
            degenerates += 1
        volume += (a[0]*(b[1]*c[2] - b[2]*c[1])
                   + a[1]*(b[2]*c[0] - b[0]*c[2])
                   + a[2]*(b[0]*c[1] - b[1]*c[0])) / 6
    return {'vertices': len(vertices), 'faces': len(faces),
            'boundaryEdges': sum(count == 1 for count in edges.values()),
            'maximumEdgeIncidence': max(edges.values()),
            'degenerateFaces': degenerates, 'signedVolume': volume}


def verify_corpus(root=CORPUS):
    root = Path(root).resolve(strict=True)
    manifest_path = root / 'manifest.v1.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    if (manifest.get('schemaVersion') != 1 or manifest.get('kind') != 'scientific.cgal-fixture-corpus'
            or manifest.get('license') != 'CC0-1.0'
            or manifest.get('source') != 'Project-authored geometry; no external mesh files'):
        raise ValueError('CGAL corpus provenance or contract is invalid.')
    entries = manifest.get('fixtures')
    if not isinstance(entries, list) or len(entries) != 4:
        raise ValueError('CGAL corpus must list four authored fixtures.')
    seen, results = set(), []
    for entry in entries:
        name = entry.get('path', '')
        if (not isinstance(name, str) or not NAME.fullmatch(name)
                or entry.get('id') != name[:-4] or name in seen
                or entry.get('version') != 1
                or entry.get('class') not in ('canonical', 'pathological')):
            raise ValueError('CGAL fixture identity is invalid.')
        seen.add(name)
        path = (root / name).resolve(strict=True)
        if path.parent != root or not path.is_file() or sha(path) != entry.get('sha256'):
            raise ValueError('CGAL fixture hash or path mismatch: ' + name)
        measured = geometry(path)
        expected = entry['expected']
        for key, value in expected.items():
            if key not in measured or (abs(measured[key] - value) > 1e-12
                                       if key == 'signedVolume' else measured[key] != value):
                raise ValueError('CGAL fixture invariant mismatch: ' + name + '/' + key)
        results.append({'id': entry['id'], 'version': 1, 'sha256': entry['sha256'],
                        'class': entry['class'], 'geometry': measured})
    if {path.name for path in root.glob('*.obj')} != seen:
        raise ValueError('Unregistered CGAL fixture is present.')
    return {'schemaVersion': 1, 'kind': 'scientific.cgal-corpus-verification',
            'manifestSha256': sha(manifest_path), 'fixtures': results, 'verdict': 'passed'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('verify',))
    parser.add_argument('--root', type=Path, default=CORPUS)
    options = parser.parse_args()
    print(json.dumps(verify_corpus(options.root), separators=(',', ':')))
