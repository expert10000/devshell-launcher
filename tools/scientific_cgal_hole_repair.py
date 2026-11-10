"""Fixed native one-hole fill replay with independent exact face checks."""
import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import subprocess
import uuid

from scientific_cgal_corpus import CORPUS, sha, verify_corpus
from scientific_cgal_mesh_metrics import metrics, parse_obj
from scientific_cgal_repair_fixture import FIXTURE_ROOT, verify as verify_fixture


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'scientific/cgal-worker/hole_repair.cpp'
METRICS = ROOT / 'tools/scientific_cgal_mesh_metrics.py'
CASES = (
    ('fill-tetra-hole', FIXTURE_ROOT / 'tetra-one-hole.obj', 'succeeded', ''),
    ('reject-closed', CORPUS / 'closed-tetra.obj', 'failed', 'exactly one boundary loop'),
    ('reject-square', CORPUS / 'open-square.obj', 'failed', 'three-edge boundary'),
    ('reject-degenerate', CORPUS / 'degenerate-triangle.obj', 'failed', 'degenerate triangle'),
    ('reject-nonmanifold', CORPUS / 'nonmanifold-edge.obj', 'failed', 'readable triangle manifold'),
)


def oriented_faces(path):
    vertices, faces = parse_obj(path)
    def cycle(face):
        corners = tuple(vertices[index] for index in face)
        return min(corners, corners[1:] + corners[:1], corners[2:] + corners[:2])
    return sorted(cycle(face) for face in faces)


def check_case(case, result, exit_code, output):
    name, _, state, reason = case
    if (result.get('schemaVersion') != 1 or result.get('recipeId') != 'cgal.fill-one-hole'
            or result.get('state') != state
            or result.get('exitCode') != (0 if state == 'succeeded' else 2)
            or exit_code != result['exitCode']):
        raise ValueError(name + ': native hole-repair state changed.')
    if state == 'failed':
        if output.exists() or reason not in result.get('error', ''):
            raise ValueError(name + ': refused repair wrote output or changed diagnostic.')
        return None
    measured = metrics(output)
    canonical = metrics(CORPUS / 'closed-tetra.obj')
    if (result.get('beforeFaces') != 3 or result.get('afterFaces') != 4
            or result.get('boundaryEdgesBefore') != 3 or result.get('patchFaces') != 1
            or not result.get('versions', {}).get('cgal')
            or measured['components'] != 1 or measured['boundaryEdges'] != 0
            or measured['boundaryLoops'] != 0 or measured['eulerCharacteristic'] != 2
            or measured['degenerateFaces'] != 0 or measured['maximumEdgeIncidence'] != 2
            or measured['vertices'] != 4 or measured['faces'] != 4
            or not math.isclose(measured['signedVolume'], 1/6, abs_tol=1e-10)
            or not math.isclose(result['signedVolumeAfter'], measured['signedVolume'], abs_tol=1e-10)
            or measured['bounds'] != canonical['bounds']
            or oriented_faces(output) != oriented_faces(CORPUS / 'closed-tetra.obj')):
        raise ValueError(name + ': repaired tetrahedron differs from authored closed surface.')
    return measured


def run(worker, prefix, output_root):
    corpus, fixture = verify_corpus(), verify_fixture()
    worker = Path(worker).resolve(strict=True)
    prefix = Path(prefix).resolve(strict=True)
    if worker.name.lower() != 'devshell_cgal_hole_repair.exe' or not (prefix / 'Library/bin').is_dir():
        raise ValueError('Native hole-repair worker and runtime prefix are required.')
    root = Path(output_root).resolve() / uuid.uuid4().hex
    root.mkdir(parents=True)
    environment = os.environ.copy()
    environment['PATH'] = os.pathsep.join((str(prefix), str(prefix / 'Library/bin'),
                                           str(prefix / 'Scripts'), environment.get('PATH', '')))
    cases = []
    for case in CASES:
        name, input_path, _, _ = case
        directory = root / name
        directory.mkdir()
        output = directory / 'output.obj'
        process = subprocess.run([str(worker), 'fill-one-hole', str(input_path), str(output)],
                                 cwd=directory, env=environment, capture_output=True, text=True,
                                 encoding='utf-8', errors='replace', timeout=60)
        (directory / 'stdout.log').write_text(process.stdout, encoding='utf-8')
        (directory / 'stderr.log').write_text(process.stderr, encoding='utf-8')
        result_path = directory / 'results.json'
        result = json.loads(result_path.read_text(encoding='utf-8-sig'))
        measured = check_case(case, result, process.returncode, output)
        cases.append({'id': name, 'inputSha256': sha(input_path), 'directory': str(directory),
                      'exitCode': process.returncode, 'resultSha256': sha(result_path),
                      'outputSha256': sha(output) if output.is_file() else None,
                      'metrics': measured})
    report = {'schemaVersion': 1, 'kind': 'scientific.cgal-hole-repair-fixed-suite',
              'createdAtUtc': datetime.now(timezone.utc).isoformat(),
              'corpusManifestSha256': corpus['manifestSha256'],
              'repairManifestSha256': fixture['manifestSha256'],
              'workerPath': str(worker), 'workerSha256': sha(worker),
              'workerSourceSha256': sha(SOURCE), 'metricsSourceSha256': sha(METRICS),
              'runtimePrefix': str(prefix), 'cases': cases, 'verdict': 'passed'}
    target = root / 'hole-repair.json'
    with target.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, separators=(',', ':'))
    Path(str(target) + '.sha256').write_text(sha(target), encoding='utf-8')
    verify(target)
    return target, report


def verify(path):
    path = Path(path).resolve(strict=True)
    if sha(path) != Path(str(path) + '.sha256').read_text(encoding='utf-8').strip():
        raise ValueError('CGAL hole-repair report hash mismatch.')
    report = json.loads(path.read_text(encoding='utf-8'))
    corpus, fixture = verify_corpus(), verify_fixture()
    if (report.get('schemaVersion') != 1 or report.get('kind') != 'scientific.cgal-hole-repair-fixed-suite'
            or report.get('verdict') != 'passed'
            or report.get('corpusManifestSha256') != corpus['manifestSha256']
            or report.get('repairManifestSha256') != fixture['manifestSha256']
            or sha(Path(report['workerPath']).resolve(strict=True)) != report.get('workerSha256')
            or sha(SOURCE) != report.get('workerSourceSha256')
            or sha(METRICS) != report.get('metricsSourceSha256')
            or len(report.get('cases', [])) != len(CASES)):
        raise ValueError('CGAL hole-repair suite identity changed.')
    for item, case in zip(report['cases'], CASES):
        directory = Path(item['directory']).resolve(strict=True)
        output, result_path = directory / 'output.obj', directory / 'results.json'
        if (item['id'] != case[0] or directory.parent != path.parent or directory.name != case[0]
                or item['inputSha256'] != sha(case[1]) or item['resultSha256'] != sha(result_path)
                or item['outputSha256'] != (sha(output) if output.is_file() else None)):
            raise ValueError('CGAL hole-repair case artifact changed.')
        measured = check_case(case, json.loads(result_path.read_text(encoding='utf-8-sig')),
                              item['exitCode'], output)
        if measured != item['metrics']:
            raise ValueError('CGAL hole-repair independent measurement changed.')
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
    else:
        if not options.report:
            parser.error('verify requires report')
        target, value = Path(options.report).resolve(), verify(options.report)
    print(json.dumps({'report': str(target), 'verdict': value['verdict'],
                      'cases': len(value['cases'])}))
