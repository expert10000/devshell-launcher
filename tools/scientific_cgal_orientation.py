"""Fixed local qualification of CGAL closed-mesh orientation inspection and repair."""
import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import subprocess
import uuid

from scientific_cgal_corpus import CORPUS, geometry, sha, verify_corpus
from scientific_cgal_orientation_fixture import ROOT as ORIENTATION, verify as verify_fixture


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'scientific/cgal-worker/orientation.cpp'
CASES = (
    ('inspect-outward', 'inspect', 'closed-tetra', 'succeeded', 'outward', 'outward', False, ''),
    ('inspect-inward', 'inspect', 'inward-tetra', 'succeeded', 'inward', 'inward', False, ''),
    ('inspect-open', 'inspect', 'open-square', 'succeeded', 'undetermined', 'undetermined', False, ''),
    ('orient-inward', 'orient', 'inward-tetra', 'succeeded', 'inward', 'outward', True, ''),
    ('orient-outward', 'orient', 'closed-tetra', 'succeeded', 'outward', 'outward', False, ''),
    ('reject-open', 'orient', 'open-square', 'failed', 'undetermined', 'undetermined', False, 'requires a closed mesh'),
    ('reject-degenerate', 'inspect', 'degenerate-triangle', 'failed', 'unavailable', 'unavailable', False, 'degenerate triangle'),
    ('reject-nonmanifold', 'inspect', 'nonmanifold-edge', 'failed', 'unavailable', 'unavailable', False, 'triangle manifold'),
)


def fixture_path(name):
    return ORIENTATION / 'inward-tetra.obj' if name == 'inward-tetra' else CORPUS / (name + '.obj')


def check_case(case, result, exit_code, output):
    name, operation, _, state, before, after, changed, error = case
    if (result.get('schemaVersion') != 1 or result.get('operation') != operation
            or result.get('state') != state or exit_code != (0 if state == 'succeeded' else 2)
            or result.get('beforeOrientation') != before or result.get('afterOrientation') != after
            or result.get('orientationChanged') is not changed):
        raise ValueError(name + ': orientation state or contract changed.')
    if state == 'failed':
        if error not in result.get('error', '') or output.exists():
            raise ValueError(name + ': invalid orientation case produced output or wrong diagnostic.')
        return
    if result.get('error') or not isinstance(result.get('versions', {}).get('cgal'), str):
        raise ValueError(name + ': successful orientation lacks CGAL provenance.')
    expected_volume = (-1 if before == 'inward' else 1) / 6 if before != 'undetermined' else 0
    after_volume = expected_volume if operation == 'inspect' else 1 / 6 if after == 'outward' else 0
    if (not math.isclose(result.get('signedVolumeBefore', float('nan')), expected_volume, abs_tol=1e-12)
            or not math.isclose(result.get('signedVolumeAfter', float('nan')), after_volume, abs_tol=1e-12)):
        raise ValueError(name + ': signed volume changed.')
    if operation == 'inspect':
        if output.exists():
            raise ValueError(name + ': inspection wrote an output mesh.')
    else:
        if not output.is_file():
            raise ValueError(name + ': repair output is missing.')
        measured = geometry(output)
        if (measured['vertices'] != 4 or measured['faces'] != 4
                or measured['boundaryEdges'] != 0 or measured['degenerateFaces'] != 0
                or not math.isclose(measured['signedVolume'], 1/6, abs_tol=1e-12)):
            raise ValueError(name + ': repaired geometry is not an outward unit tetrahedron.')


def run(worker, prefix, output_root):
    corpus = verify_corpus()
    fixture = verify_fixture()
    worker = Path(worker).resolve(strict=True)
    prefix = Path(prefix).resolve(strict=True)
    if worker.name.lower() != 'devshell_cgal_orientation.exe' or not (prefix / 'Library/bin').is_dir():
        raise ValueError('CGAL orientation worker and runtime prefix are required.')
    root = Path(output_root).resolve() / uuid.uuid4().hex
    root.mkdir(parents=True)
    environment = os.environ.copy()
    environment['PATH'] = os.pathsep.join((str(prefix), str(prefix / 'Library/bin'),
                                           str(prefix / 'Scripts'), environment.get('PATH', '')))
    cases = []
    for case in CASES:
        name, operation, fixture_id, *_ = case
        directory = root / name
        directory.mkdir()
        source = fixture_path(fixture_id)
        output = directory / 'output.obj'
        args = [str(worker), operation, str(source)] + ([str(output)] if operation == 'orient' else [])
        process = subprocess.run(args, cwd=directory, env=environment,
                                 capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=30)
        (directory / 'stdout.log').write_text(process.stdout, encoding='utf-8')
        (directory / 'stderr.log').write_text(process.stderr, encoding='utf-8')
        result_path = directory / 'results.json'
        result = json.loads(result_path.read_text(encoding='utf-8'))
        check_case(case, result, process.returncode, output)
        cases.append({'id': name, 'operation': operation, 'fixtureId': fixture_id,
                      'fixtureSha256': sha(source), 'directory': str(directory),
                      'resultSha256': sha(result_path), 'exitCode': process.returncode,
                      'outputSha256': sha(output) if output.is_file() else None})
    report = {'schemaVersion': 1, 'kind': 'scientific.cgal-orientation-fixed-suite',
              'createdAtUtc': datetime.now(timezone.utc).isoformat(),
              'corpusManifestSha256': corpus['manifestSha256'],
              'orientationFixtureManifestSha256': fixture['manifestSha256'],
              'workerPath': str(worker), 'workerSha256': sha(worker),
              'workerSourceSha256': sha(SOURCE), 'runtimePrefix': str(prefix),
              'cases': cases, 'verdict': 'passed'}
    target = root / 'orientation-suite.json'
    with target.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, separators=(',', ':'))
    Path(str(target) + '.sha256').write_text(sha(target), encoding='utf-8')
    verify(target)
    return target, report


def verify(path):
    path = Path(path).resolve(strict=True)
    if sha(path) != Path(str(path) + '.sha256').read_text(encoding='utf-8').strip():
        raise ValueError('CGAL orientation suite report hash mismatch.')
    report = json.loads(path.read_text(encoding='utf-8'))
    corpus, fixture = verify_corpus(), verify_fixture()
    if (report.get('schemaVersion') != 1 or report.get('kind') != 'scientific.cgal-orientation-fixed-suite'
            or report.get('verdict') != 'passed' or report.get('corpusManifestSha256') != corpus['manifestSha256']
            or report.get('orientationFixtureManifestSha256') != fixture['manifestSha256']
            or sha(Path(report['workerPath']).resolve(strict=True)) != report.get('workerSha256')
            or sha(SOURCE) != report.get('workerSourceSha256')
            or [item.get('id') for item in report.get('cases', [])] != [case[0] for case in CASES]):
        raise ValueError('CGAL orientation suite identity changed.')
    for case, item in zip(CASES, report['cases']):
        directory = Path(item['directory']).resolve(strict=True)
        source = fixture_path(case[2])
        output = directory / 'output.obj'
        result_path = directory / 'results.json'
        if (directory.parent != path.parent or directory.name != case[0]
                or item['operation'] != case[1] or item['fixtureId'] != case[2]
                or sha(source) != item['fixtureSha256'] or sha(result_path) != item['resultSha256']
                or (sha(output) if output.is_file() else None) != item['outputSha256']):
            raise ValueError('CGAL orientation case evidence changed.')
        check_case(case, json.loads(result_path.read_text(encoding='utf-8')),
                   item['exitCode'], output)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('run', 'verify'))
    parser.add_argument('--worker')
    parser.add_argument('--prefix')
    parser.add_argument('--output-root')
    parser.add_argument('--report')
    options = parser.parse_args()
    if options.command == 'run':
        if not all((options.worker, options.prefix, options.output_root)):
            parser.error('run requires worker, prefix and output-root')
        target, value = run(options.worker, options.prefix, options.output_root)
        print(json.dumps({'report': str(target), 'verdict': value['verdict'], 'cases': len(value['cases'])}))
    else:
        if not options.report:
            parser.error('verify requires report')
        value = verify(options.report)
        print(json.dumps({'report': str(Path(options.report).resolve()),
                          'verdict': value['verdict'], 'cases': len(value['cases'])}))
