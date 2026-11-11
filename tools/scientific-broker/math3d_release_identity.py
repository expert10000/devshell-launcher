"""Pin the MATH3D source, built desktop payload, package and five-smoke consumer contract."""
import hashlib
import json
from pathlib import Path
import subprocess

PACKAGE = ('package.json', 'package-lock.json', 'apps/desktop/package.json', 'renderer/package.json')
CONSUMER = ('renderer/src/mesh/surfaceMesh.ts', 'packages/core/src/meshDocument.ts',
            'packages/core/src/tetrahedralMeshDocument.ts',
            'renderer/src/volume/tetrahedralMeshDocumentAdapter.ts',
            'renderer/src/volume/TetrahedralMeshViewport.tsx',
            'src/main/python/nativeCgalProtocol.ts', 'scientific/volume-consumer.v1.json')
BUILD = ('dist/build-identity.json', 'dist/main.js', 'dist/preload.js')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def compact(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode('utf-8')


def file_hashes(root, names):
    result = {}
    for name in names:
        path = root / name
        if not path.is_file():
            raise ValueError('MATH3D identity file is missing: ' + name)
        result[name] = sha(path.read_bytes())
    return result


def capture(root):
    root = Path(root).resolve(strict=True)
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
    package = file_hashes(root, PACKAGE)
    consumer = file_hashes(root, CONSUMER)
    build = file_hashes(root, BUILD)
    renderer = root / 'renderer/dist'
    if not (renderer / 'index.html').is_file():
        raise ValueError('MATH3D renderer package is missing.')
    for path in sorted(renderer.rglob('*')):
        if path.is_file():
            build[path.relative_to(root).as_posix()] = sha(path.read_bytes())
    declared = json.loads((root / 'dist/build-identity.json').read_text(encoding='utf-8'))
    version = json.loads((root / 'package.json').read_text(encoding='utf-8'))['version']
    if (declared.get('commit') != commit or declared.get('version') != version
            or declared.get('rendererHash') != build['renderer/dist/index.html']):
        raise ValueError('MATH3D build identity is stale.')
    value = {'schemaVersion': 1, 'kind': 'math3d.release-identity', 'commit': commit,
             'version': version, 'buildDeclaredDirty': declared.get('dirty'),
             'package': package, 'build': build, 'consumerContract': consumer}
    value['identitySha256'] = sha(compact(value))
    return value


def verify(root, expected):
    current = capture(root)
    if current != expected:
        raise ValueError('MATH3D source, build, package or consumer contract drifted.')
    return current
