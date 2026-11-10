"""Export only a verified two-hole repair from fixed or affine evidence."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import uuid

from scientific_cgal_corpus import sha
from scientific_cgal_multi_hole_affine import verify as verify_affine
from scientific_cgal_multi_hole_repair import verify as verify_fixed


def selected(source, case_index):
    kind = json.loads(source.read_text(encoding='utf-8')).get('kind')
    if kind == 'scientific.cgal-two-hole-fixed-suite':
        report = verify_fixed(source)
        if case_index != 0:
            raise ValueError('Only the accepted fixed two-hole case can be exported.')
        case = report['cases'][0]
        measurement = case['measurement']
    elif kind == 'scientific.cgal-two-hole-affine':
        report = verify_affine(source)
        if not 0 <= case_index < len(report['cases']):
            raise ValueError('Affine two-hole case index is outside the accepted suite.')
        case = report['cases'][case_index]
        measurement = {'metrics': case['metrics'], 'patches': case['patches']}
    else:
        raise ValueError('Only verified two-hole repair suites can be exported.')
    if case['outputSha256'] is None or measurement is None:
        raise ValueError('Rejected two-hole repair cannot be exported.')
    output = Path(case['directory']) / 'output.obj'
    if sha(output) != case['outputSha256']:
        raise ValueError('Two-hole export source artifact changed.')
    return report, case, measurement, output


def export(source_report, case_index, output_root):
    source = Path(source_report).resolve(strict=True)
    report, case, measurement, output = selected(source, case_index)
    root = Path(output_root).resolve() / uuid.uuid4().hex
    root.mkdir(parents=True)
    mesh = root / 'mesh.obj'
    shutil.copyfile(output, mesh)
    manifest = {'schemaVersion': 1, 'kind': 'scientific.cgal-two-hole-repair-export',
                'createdAtUtc': datetime.now(timezone.utc).isoformat(),
                'sourceReport': str(source), 'sourceReportSha256': sha(source),
                'sourceKind': report['kind'], 'caseIndex': case_index,
                'caseName': case.get('id', case.get('name')),
                'inputSha256': case['inputSha256'],
                'outputSha256': case['outputSha256'],
                'workerSha256': report['workerSha256'],
                'fixtureManifestSha256': report['multiManifestSha256'],
                'measurement': measurement, 'meshSha256': sha(mesh), 'state': 'exported'}
    target = root / 'manifest.json'
    with target.open('x', encoding='utf-8') as stream:
        json.dump(manifest, stream, separators=(',', ':'))
    Path(str(target) + '.sha256').write_text(sha(target), encoding='utf-8')
    verify(target)
    return target, manifest


def verify(path):
    path = Path(path).resolve(strict=True)
    if sha(path) != Path(str(path) + '.sha256').read_text(encoding='utf-8').strip():
        raise ValueError('Two-hole export manifest hash mismatch.')
    manifest = json.loads(path.read_text(encoding='utf-8'))
    source = Path(manifest['sourceReport']).resolve(strict=True)
    report, case, measurement, output = selected(source, manifest['caseIndex'])
    mesh = path.parent / 'mesh.obj'
    if (manifest.get('schemaVersion') != 1
            or manifest.get('kind') != 'scientific.cgal-two-hole-repair-export'
            or manifest.get('state') != 'exported'
            or sha(source) != manifest.get('sourceReportSha256')
            or manifest.get('sourceKind') != report['kind']
            or manifest.get('caseName') != case.get('id', case.get('name'))
            or manifest.get('inputSha256') != case['inputSha256']
            or manifest.get('outputSha256') != case['outputSha256']
            or manifest.get('workerSha256') != report['workerSha256']
            or manifest.get('fixtureManifestSha256') != report['multiManifestSha256']
            or manifest.get('measurement') != measurement
            or sha(mesh) != manifest.get('meshSha256')
            or mesh.read_bytes() != output.read_bytes()):
        raise ValueError('Two-hole export provenance or mesh changed.')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('export', 'verify'))
    parser.add_argument('--source-report')
    parser.add_argument('--case-index', type=int, default=0)
    parser.add_argument('--output-root')
    parser.add_argument('--manifest')
    options = parser.parse_args()
    if options.command == 'export':
        if not options.source_report or not options.output_root:
            parser.error('export requires source-report and output-root')
        target, value = export(options.source_report, options.case_index, options.output_root)
    else:
        if not options.manifest:
            parser.error('verify requires manifest')
        target, value = Path(options.manifest).resolve(), verify(options.manifest)
    print(json.dumps({'manifest': str(target), 'state': value['state']}))
