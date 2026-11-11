"""Versioned, live guarded scope for the dedicated CGAL orientation worker."""
import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

from scientific_cgal_corpus import geometry, sha
from scientific_cgal_orientation_fixture import vertices_faces

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'scientific/fixtures/cgal/orientation/manifest.v2.json'
ADAPTER = ROOT / 'tools/scientific-cgal-worker.py'
CONTRACT = ROOT / 'tools/scientific_worker_contract.py'
WORKER_SOURCE = ROOT / 'scientific/cgal-worker/orientation.cpp'
CASES = ('tetra-inward', 'tetra-outward', 'cube-inward', 'cube-outward',
         'octa-inward', 'octa-outward', 'affine-inward', 'affine-outward',
         'open', 'disconnected', 'nonmanifold', 'degenerate')


def _faces(path, reverse=False):
    vertices, faces = vertices_faces(path)
    def canonical(face):
        sequence = tuple(vertices[index - 1] for index in (reversed(face) if reverse else face))
        return min(sequence[index:] + sequence[:index] for index in range(3))
    return sorted(canonical(face) for face in faces)


def manifest():
    value = json.loads(MANIFEST.read_text(encoding='utf-8'))
    if (value.get('schemaVersion') != 2 or value.get('kind') != 'scientific.cgal-orientation-scope'
            or value.get('capabilityId') != 'mesh.orient' or value.get('suiteId') != 'cgal-orientation-v2'
            or value.get('license') != 'CC0-1.0'
            or [case.get('caseId') for case in value.get('cases', [])] != list(CASES)):
        raise ValueError('Orientation v2 case manifest changed.')
    cases = value['cases']
    for case in cases:
        path = (ROOT / case['path']).resolve(strict=True)
        if not path.is_relative_to(ROOT) or sha(path) != case['sha256']:
            raise ValueError('Orientation fixture hash changed: ' + case['caseId'])
        if case['expected'] == 'accepted':
            measured = geometry(path)
            if (case['orientation'] not in ('inward', 'outward')
                    or measured['vertices'] != case['vertices'] or measured['faces'] != case['faces']
                    or measured['boundaryEdges'] != 0 or measured['maximumEdgeIncidence'] != 2
                    or measured['degenerateFaces'] != 0
                    or not math.isclose(measured['signedVolume'],
                                        (-1 if case['orientation'] == 'inward' else 1) * case['absoluteVolume'],
                                        abs_tol=1e-11)):
                raise ValueError('Orientation fixture geometry changed: ' + case['caseId'])
            if case['orientation'] == 'inward':
                outward = cases[CASES.index(case['caseId']) + 1]
                if (outward['shape'] != case['shape'] or _faces(path, reverse=True) != _faces(ROOT / outward['path'])):
                    raise ValueError('Inward fixture is not an exact face reversal.')
        elif case['expected'] != 'rejected' or not case.get('errorContains'):
            raise ValueError('Orientation adverse-case contract changed.')
    return value


def check_case(case, directory, saved=None):
    request_path, result_path = directory / 'request.json', directory / 'results.json'
    output = directory / 'oriented.obj'
    request = json.loads(request_path.read_text(encoding='utf-8'))
    result = json.loads(result_path.read_text(encoding='utf-8-sig'))
    expected = 'succeeded' if case['expected'] == 'accepted' else 'failed'
    source = Path(request['inputArtifacts'][0]['path']).resolve(strict=True)
    if (request['recipeId'] != 'cgal.repair-orientation' or request['runtimeId'] != 'cgal-win-conda'
            or request['workingDirectory'] != str(directory) or source.parent != directory / 'dataset'
            or sha(source) != case['sha256'] or request['inputArtifacts'][0]['sha256'] != case['sha256']
            or result['runId'] != request['runId'] or result['state'] != expected
            or result.get('validatedCapabilities', []) != (['mesh.read', 'mesh.write', 'mesh.orient'] if expected == 'succeeded' else [])
            or output.is_file() != (expected == 'succeeded')
            or bool(result.get('artifacts')) != (expected == 'succeeded')):
        raise ValueError('Orientation case publication changed: ' + case['caseId'])
    engine = result.get('engineDetails', {})
    if expected == 'failed':
        if case['errorContains'] not in str(engine.get('error', '')):
            raise ValueError('Orientation rejection diagnostic changed: ' + case['caseId'])
    else:
        measured = geometry(output)
        if (engine.get('beforeOrientation') != case['orientation'] or engine.get('afterOrientation') != 'outward'
                or engine.get('orientationChanged') != (case['orientation'] == 'inward')
                or measured['vertices'] != case['vertices'] or measured['faces'] != case['faces']
                or measured['boundaryEdges'] != 0 or measured['maximumEdgeIncidence'] != 2
                or measured['degenerateFaces'] != 0
                or not math.isclose(measured['signedVolume'], case['absoluteVolume'], abs_tol=1e-11)
                or _faces(output) != _faces(ROOT / manifest()['cases'][CASES.index(case['caseId']) + (case['orientation'] == 'inward')]['path'])):
            raise ValueError('Orientation output topology or winding changed: ' + case['caseId'])
        if result['artifacts'][0]['sha256'] != sha(output):
            raise ValueError('Orientation output hash changed.')
    item = {'caseId': case['caseId'], 'directory': str(directory),
            'requestSha256': sha(request_path), 'resultSha256': sha(result_path),
            'state': expected, 'outputSha256': sha(output) if output.is_file() else None}
    if saved is not None and saved != item:
        raise ValueError('Orientation saved case evidence changed: ' + case['caseId'])
    return item


def run(worker, prefix, output_root):
    cases = manifest()['cases']
    worker = Path(worker).resolve(strict=True)
    prefix = Path(prefix).resolve(strict=True)
    if worker.name.lower() != 'devshell_cgal_orientation.exe' or not (prefix / 'Library/bin').is_dir():
        raise ValueError('Dedicated orientation worker and CGAL prefix are required.')
    folder = Path(output_root).resolve() / uuid.uuid4().hex
    folder.mkdir(parents=True)
    environment = os.environ.copy()
    environment['PATH'] = os.pathsep.join((str(prefix), str(prefix / 'Library/bin'),
                                           str(prefix / 'Scripts'), environment.get('PATH', '')))
    evidence = []
    for case in cases:
        directory = folder / case['caseId']
        dataset = directory / 'dataset'
        dataset.mkdir(parents=True)
        source = dataset / 'input.obj'
        shutil.copyfile(ROOT / case['path'], source)
        request = {'schemaVersion': 1, 'runId': uuid.uuid4().hex, 'runtimeId': 'cgal-win-conda',
                   'recipeId': 'cgal.repair-orientation', 'workingDirectory': str(directory),
                   'datasetRoot': str(dataset), 'inputArtifacts': [{'path': str(source), 'sha256': sha(source)}],
                   'outputArtifacts': [{'path': 'oriented.obj'}], 'parameters': {}, 'timeoutSeconds': 120}
        (directory / 'request.json').write_text(json.dumps(request), encoding='utf-8')
        completed = subprocess.run([str(prefix / 'python.exe'), str(ADAPTER), '--request', str(directory / 'request.json'),
                                    '--worker', str(worker), '--prefix', str(prefix)], cwd=directory, env=environment,
                                   capture_output=True, text=True, timeout=150)
        (directory / 'stdout.log').write_text(completed.stdout, encoding='utf-8')
        (directory / 'stderr.log').write_text(completed.stderr, encoding='utf-8')
        if completed.returncode != (0 if case['expected'] == 'accepted' else 2):
            raise ValueError('Orientation worker exit changed: ' + case['caseId'] + ': ' + completed.stderr[-500:])
        evidence.append(check_case(case, directory))
    report = {'schemaVersion': 2, 'kind': 'scientific.cgal-orientation-scope-live', 'verdict': 'passed',
              'createdAtUtc': datetime.now(timezone.utc).isoformat(), 'capabilityId': 'mesh.orient',
              'manifestSha256': sha(MANIFEST), 'adapterSha256': sha(ADAPTER), 'contractSha256': sha(CONTRACT),
              'workerSourceSha256': sha(WORKER_SOURCE), 'workerPath': str(worker), 'workerSha256': sha(worker),
              'prefix': str(prefix), 'cases': evidence}
    path = folder / 'orientation-scope.json'
    path.write_text(json.dumps(report, separators=(',', ':')), encoding='utf-8')
    Path(str(path) + '.sha256').write_text(sha(path), encoding='utf-8')
    verify(path)
    return path, report


def verify(path):
    path = Path(path).resolve(strict=True)
    if sha(path) != Path(str(path) + '.sha256').read_text(encoding='utf-8').strip():
        raise ValueError('Orientation scope report seal changed.')
    report = json.loads(path.read_text(encoding='utf-8'))
    if (report.get('schemaVersion') != 2 or report.get('kind') != 'scientific.cgal-orientation-scope-live'
            or report.get('verdict') != 'passed' or report.get('capabilityId') != 'mesh.orient'
            or report.get('manifestSha256') != sha(MANIFEST) or report.get('adapterSha256') != sha(ADAPTER)
            or report.get('contractSha256') != sha(CONTRACT) or report.get('workerSourceSha256') != sha(WORKER_SOURCE)
            or sha(Path(report['workerPath'])) != report['workerSha256']
            or len(report.get('cases', [])) != len(CASES)):
        raise ValueError('Orientation scope source or worker changed.')
    for case, item in zip(manifest()['cases'], report['cases']):
        directory = Path(item['directory']).resolve(strict=True)
        if directory.parent != path.parent or directory.name != case['caseId']:
            raise ValueError('Orientation case escaped its run directory.')
        check_case(case, directory, item)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('run', 'verify'))
    parser.add_argument('--worker', type=Path)
    parser.add_argument('--prefix', type=Path)
    parser.add_argument('--output-root', type=Path)
    parser.add_argument('--record', type=Path)
    args = parser.parse_args()
    if args.command == 'run':
        if not all((args.worker, args.prefix, args.output_root)):
            parser.error('run requires --worker, --prefix and --output-root')
        result, _ = run(args.worker, args.prefix, args.output_root)
    else:
        if not args.record:
            parser.error('verify requires --record')
        result = args.record
        verify(result)
    print(json.dumps({'record': str(result), 'verdict': 'passed'}))
