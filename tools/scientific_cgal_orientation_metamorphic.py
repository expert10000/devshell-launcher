"""Seeded inward tetrahedra, native repair and independent reopen checks."""
import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import subprocess
import uuid

from scientific_cgal_corpus import geometry, sha, verify_corpus
from scientific_cgal_metamorphic import generate, parameters_for
from scientific_cgal_orientation_fixture import verify as verify_fixture


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'scientific/cgal-worker/orientation.cpp'
GENERATOR = ROOT / 'tools/scientific_cgal_metamorphic.py'


def inward_bytes(parameters):
    lines = generate(parameters).decode('utf-8').splitlines()
    reversed_lines = []
    for line in lines:
        if line.startswith('f '):
            reversed_lines.append('f ' + ' '.join(reversed(line.split()[1:])))
        else:
            reversed_lines.append(line)
    return ('\n'.join(reversed_lines) + '\n').encode('utf-8')


def check_case(item):
    parameters = item['parameters']
    directory = Path(item['directory']).resolve(strict=True)
    source = directory / 'inward.obj'
    output = directory / 'outward.obj'
    orient_result = directory / 'orient/results.json'
    inspect_result = directory / 'inspect/results.json'
    if (source.read_bytes() != inward_bytes(parameters) or sha(source) != item['inputSha256']
            or sha(output) != item['outputSha256']
            or sha(orient_result) != item['orientResultSha256']
            or sha(inspect_result) != item['inspectResultSha256']):
        raise ValueError('Seeded orientation artifact hash or generated input changed.')
    before, after = geometry(source), geometry(output)
    expected = parameters['scale'] ** 3 / 6
    for measured, signed in ((before, -expected), (after, expected)):
        if (measured['vertices'] != 4 or measured['faces'] != 4
                or measured['boundaryEdges'] != 0 or measured['degenerateFaces'] != 0
                or not math.isclose(measured['signedVolume'], signed, abs_tol=1e-10)):
            raise ValueError('Seeded orientation topology or signed volume changed.')
    repaired = json.loads(orient_result.read_text(encoding='utf-8'))
    reopened = json.loads(inspect_result.read_text(encoding='utf-8'))
    if (repaired.get('state') != 'succeeded' or repaired.get('operation') != 'orient'
            or repaired.get('beforeOrientation') != 'inward'
            or repaired.get('afterOrientation') != 'outward'
            or repaired.get('orientationChanged') is not True
            or reopened.get('state') != 'succeeded' or reopened.get('operation') != 'inspect'
            or reopened.get('beforeOrientation') != 'outward'
            or reopened.get('afterOrientation') != 'outward'
            or not math.isclose(repaired.get('signedVolumeBefore', 0), -expected, abs_tol=1e-10)
            or not math.isclose(repaired.get('signedVolumeAfter', 0), expected, abs_tol=1e-10)
            or not math.isclose(reopened.get('signedVolumeBefore', 0), expected, abs_tol=1e-10)):
        raise ValueError('Seeded CGAL repair or independent reopen changed.')


def invoke(worker, environment, directory, operation, source, output=None):
    directory.mkdir()
    args = [str(worker), operation, str(source)] + ([str(output)] if output else [])
    process = subprocess.run(args, cwd=directory, env=environment,
                             capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=30)
    (directory / 'stdout.log').write_text(process.stdout, encoding='utf-8')
    (directory / 'stderr.log').write_text(process.stderr, encoding='utf-8')
    if process.returncode:
        raise ValueError('Seeded orientation worker rejected valid geometry: ' + process.stderr[-300:])


def run(worker, prefix, output_root, seed):
    corpus, fixture = verify_corpus(), verify_fixture()
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
    for index, parameters in enumerate(parameters_for(seed)):
        directory = root / f'case-{index}'
        directory.mkdir()
        source = directory / 'inward.obj'
        source.write_bytes(inward_bytes(parameters))
        output = directory / 'outward.obj'
        invoke(worker, environment, directory / 'orient', 'orient', source, output)
        invoke(worker, environment, directory / 'inspect', 'inspect', output)
        item = {'caseIndex': index, 'parameters': parameters, 'directory': str(directory),
                'inputSha256': sha(source), 'outputSha256': sha(output),
                'orientResultSha256': sha(directory / 'orient/results.json'),
                'inspectResultSha256': sha(directory / 'inspect/results.json')}
        check_case(item)
        cases.append(item)
    report = {'schemaVersion': 1, 'kind': 'scientific.cgal-orientation-metamorphic-run',
              'createdAtUtc': datetime.now(timezone.utc).isoformat(), 'seed': seed,
              'corpusManifestSha256': corpus['manifestSha256'],
              'orientationFixtureManifestSha256': fixture['manifestSha256'],
              'generatorSha256': sha(GENERATOR), 'workerSourceSha256': sha(SOURCE),
              'workerPath': str(worker), 'workerSha256': sha(worker),
              'runtimePrefix': str(prefix), 'cases': cases, 'verdict': 'passed'}
    target = root / 'orientation-metamorphic.json'
    with target.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, separators=(',', ':'))
    Path(str(target) + '.sha256').write_text(sha(target), encoding='utf-8')
    verify(target)
    return target, report


def verify(path):
    path = Path(path).resolve(strict=True)
    if sha(path) != Path(str(path) + '.sha256').read_text(encoding='utf-8').strip():
        raise ValueError('Seeded orientation report hash mismatch.')
    report = json.loads(path.read_text(encoding='utf-8'))
    corpus, fixture = verify_corpus(), verify_fixture()
    if (report.get('schemaVersion') != 1
            or report.get('kind') != 'scientific.cgal-orientation-metamorphic-run'
            or report.get('verdict') != 'passed'
            or report.get('corpusManifestSha256') != corpus['manifestSha256']
            or report.get('orientationFixtureManifestSha256') != fixture['manifestSha256']
            or report.get('generatorSha256') != sha(GENERATOR)
            or report.get('workerSourceSha256') != sha(SOURCE)
            or sha(Path(report['workerPath']).resolve(strict=True)) != report.get('workerSha256')):
        raise ValueError('Seeded orientation source identity changed.')
    planned = parameters_for(report['seed'])
    if len(report.get('cases', [])) != len(planned):
        raise ValueError('Seeded orientation case count changed.')
    for index, (item, parameters) in enumerate(zip(report['cases'], planned)):
        directory = Path(item['directory']).resolve(strict=True)
        if (directory.parent != path.parent or directory.name != f'case-{index}'
                or item['caseIndex'] != index or item['parameters'] != parameters):
            raise ValueError('Seeded orientation case identity changed.')
        check_case(item)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('run', 'verify'))
    parser.add_argument('--worker')
    parser.add_argument('--prefix')
    parser.add_argument('--output-root')
    parser.add_argument('--seed', type=int, default=20261108)
    parser.add_argument('--report')
    options = parser.parse_args()
    if options.command == 'run':
        if not all((options.worker, options.prefix, options.output_root)):
            parser.error('run requires worker, prefix and output-root')
        target, value = run(options.worker, options.prefix, options.output_root, options.seed)
        print(json.dumps({'report': str(target), 'verdict': value['verdict'], 'cases': len(value['cases'])}))
    else:
        if not options.report:
            parser.error('verify requires report')
        value = verify(options.report)
        print(json.dumps({'report': str(Path(options.report).resolve()),
                          'verdict': value['verdict'], 'cases': len(value['cases'])}))
