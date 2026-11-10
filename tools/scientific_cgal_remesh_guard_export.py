"""Export only a verified accepted local remesh with a sealed manifest."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import uuid

from scientific_cgal_corpus import sha
from scientific_cgal_remesh_guard import verify as verify_guard


def export(guard_report, output_root):
    source = Path(guard_report).resolve(strict=True)
    guard = verify_guard(source)
    if guard['state'] != 'accepted':
        raise ValueError('Rejected guarded remesh cannot be exported.')
    root = Path(output_root).resolve() / uuid.uuid4().hex
    root.mkdir(parents=True)
    mesh = root / 'mesh.obj'
    shutil.copyfile(source.parent / 'accepted.obj', mesh)
    manifest = {'schemaVersion': 1, 'kind': 'scientific.cgal-remesh-guard-export',
                'createdAtUtc': datetime.now(timezone.utc).isoformat(),
                'guardReport': str(source), 'guardReportSha256': sha(source),
                'inputSha256': guard['inputSha256'], 'workerSha256': guard['workerSha256'],
                'policy': guard['policy'], 'parameters': guard['parameters'],
                'meshSha256': sha(mesh), 'state': 'accepted'}
    target = root / 'manifest.json'
    with target.open('x', encoding='utf-8') as stream:
        json.dump(manifest, stream, separators=(',', ':'))
    Path(str(target) + '.sha256').write_text(sha(target), encoding='utf-8')
    verify(target)
    return target, manifest


def verify(path):
    path = Path(path).resolve(strict=True)
    if sha(path) != Path(str(path) + '.sha256').read_text(encoding='utf-8').strip():
        raise ValueError('Guard export manifest hash mismatch.')
    manifest = json.loads(path.read_text(encoding='utf-8'))
    source = Path(manifest['guardReport']).resolve(strict=True)
    guard = verify_guard(source)
    mesh = path.parent / 'mesh.obj'
    if (manifest.get('schemaVersion') != 1
            or manifest.get('kind') != 'scientific.cgal-remesh-guard-export'
            or manifest.get('state') != 'accepted' or guard['state'] != 'accepted'
            or sha(source) != manifest.get('guardReportSha256')
            or manifest.get('inputSha256') != guard['inputSha256']
            or manifest.get('workerSha256') != guard['workerSha256']
            or manifest.get('policy') != guard['policy']
            or manifest.get('parameters') != guard['parameters']
            or sha(mesh) != manifest.get('meshSha256')
            or mesh.read_bytes() != (source.parent / 'accepted.obj').read_bytes()):
        raise ValueError('Guard export provenance or mesh changed.')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('export', 'verify'))
    parser.add_argument('--guard-report')
    parser.add_argument('--output-root')
    parser.add_argument('--manifest')
    options = parser.parse_args()
    if options.command == 'export':
        if not options.guard_report or not options.output_root:
            parser.error('export requires guard-report and output-root')
        target, value = export(options.guard_report, options.output_root)
    else:
        if not options.manifest:
            parser.error('verify requires manifest')
        target, value = Path(options.manifest).resolve(), verify(options.manifest)
    print(json.dumps({'manifest': str(target), 'state': value['state']}))
