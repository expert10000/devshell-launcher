"""Fixed native two-square-hole replay with independent dual-patch coverage."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import subprocess
import uuid

from scientific_cgal_corpus import CORPUS, sha, verify_corpus
from scientific_cgal_hole_repair import oriented_faces
from scientific_cgal_mesh_metrics import metrics
from scientific_cgal_multi_fixture import FIXTURE_ROOT, verify as verify_fixture
from scientific_cgal_quad_fixture import FIXTURE_ROOT as QUAD_ROOT, verify as verify_quad
from scientific_cgal_repair_fixture import FIXTURE_ROOT as TRI_ROOT, verify as verify_triangle


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'scientific/cgal-worker/hole_repair.cpp'
METRICS = ROOT / 'tools/scientific_cgal_mesh_metrics.py'
CASES = (
    ('fill-two-cube-holes', 'fill-two-quad-holes', FIXTURE_ROOT / 'cube-two-square-holes.obj', 'succeeded', ''),
    ('reject-one-hole', 'fill-two-quad-holes', QUAD_ROOT / 'cube-one-quad-hole.obj', 'failed', 'exactly two boundary loops'),
    ('reject-closed', 'fill-two-quad-holes', QUAD_ROOT / 'cube-closed.obj', 'failed', 'exactly two boundary loops'),
    ('reject-triangle-hole', 'fill-two-quad-holes', TRI_ROOT / 'tetra-one-hole.obj', 'failed', 'exactly two boundary loops'),
    ('reject-wrong-operation', 'fill-quad-hole', FIXTURE_ROOT / 'cube-two-square-holes.obj', 'failed', 'exactly one boundary loop'),
    ('reject-degenerate', 'fill-two-quad-holes', CORPUS / 'degenerate-triangle.obj', 'failed', 'degenerate triangle'),
    ('reject-nonmanifold', 'fill-two-quad-holes', CORPUS / 'nonmanifold-edge.obj', 'failed', 'readable triangle manifold'),
)


def check_two_patches(output):
    original = Counter(oriented_faces(FIXTURE_ROOT / 'cube-two-square-holes.obj'))
    repaired = Counter(oriented_faces(output))
    if any(repaired[face] != count for face, count in original.items()):
        raise ValueError('Two-hole repair changed an original cube side face.')
    patch = list((repaired - original).elements())
    if len(patch) != 4:
        raise ValueError('Two-hole repair did not add four patch faces.')
    measurements = []
    for level in (0.0, 1.0):
        corners = {(0.0, 0.0, level), (1.0, 0.0, level),
                   (1.0, 1.0, level), (0.0, 1.0, level)}
        faces = [face for face in patch if set(face) <= corners]
        if len(faces) != 2:
            raise ValueError('Two-hole repair patch left a cube cap plane.')
        edges = Counter()
        area = 0.0
        for face in faces:
            if len(set(face)) != 3:
                raise ValueError('Two-hole repair patch has a degenerate face.')
            a, b, c = face
            signed_twice_area = (b[0]-a[0])*(c[1]-a[1]) - (b[1]-a[1])*(c[0]-a[0])
            if signed_twice_area * (1 if level == 1 else -1) <= 0:
                raise ValueError('Two-hole repair patch orientation changed.')
            area += abs(signed_twice_area) / 2
            edges.update(tuple(sorted((face[index], face[(index+1) % 3]))) for index in range(3))
        rim = {edge for edge, count in edges.items() if count == 1}
        perimeter = [(0.0, 0.0, level), (1.0, 0.0, level),
                     (1.0, 1.0, level), (0.0, 1.0, level)]
        expected_rim = {tuple(sorted((perimeter[index], perimeter[(index+1) % 4])))
                        for index in range(4)}
        if (rim != expected_rim or sorted(edges.values()) != [1, 1, 1, 1, 2]
                or not math.isclose(area, 1, abs_tol=1e-10)):
            raise ValueError('Two-hole repair patch does not cover a full square rim.')
        measurements.append({'z': level, 'faces': 2, 'area': area, 'rimEdges': len(rim)})
    return measurements


def check_case(case, result, exit_code, output):
    name, operation, _, state, reason = case
    if (result.get('schemaVersion') != 1 or result.get('recipeId') != 'cgal.' + operation
            or result.get('state') != state or result.get('exitCode') != (0 if state == 'succeeded' else 2)
            or exit_code != result['exitCode']):
        raise ValueError(name + ': native two-hole state changed.')
    if state == 'failed':
        if output.exists() or reason not in result.get('error', ''):
            raise ValueError(name + ': refused two-hole repair wrote output or changed diagnostic.')
        return None
    measured = metrics(output)
    canonical = metrics(QUAD_ROOT / 'cube-closed.obj')
    if (result.get('beforeFaces') != 8 or result.get('afterFaces') != 12
            or result.get('boundaryLoopsBefore') != 2 or result.get('boundaryEdgesBefore') != 8
            or result.get('holesFilled') != 2 or result.get('patchFaces') != 4
            or result.get('patchFaceCounts') != [2, 2]
            or not result.get('versions', {}).get('cgal')
            or measured['vertices'] != 8 or measured['faces'] != 12
            or measured['components'] != 1 or measured['boundaryEdges'] != 0
            or measured['boundaryLoops'] != 0 or measured['eulerCharacteristic'] != 2
            or measured['degenerateFaces'] != 0 or measured['maximumEdgeIncidence'] != 2
            or measured['bounds'] != canonical['bounds']
            or not math.isclose(measured['area'], 6, abs_tol=1e-10)
            or not math.isclose(measured['signedVolume'], 1, abs_tol=1e-10)
            or not math.isclose(result['signedVolumeAfter'], measured['signedVolume'], abs_tol=1e-10)):
        raise ValueError(name + ': repaired two-hole cube topology or volume changed.')
    return {'metrics': measured, 'patches': check_two_patches(output)}


def run(worker, prefix, output_root):
    corpus, fixture, quad, triangle = verify_corpus(), verify_fixture(), verify_quad(), verify_triangle()
    worker = Path(worker).resolve(strict=True)
    prefix = Path(prefix).resolve(strict=True)
    if worker.name.lower() != 'devshell_cgal_hole_repair.exe' or not (prefix / 'Library/bin').is_dir():
        raise ValueError('Native two-hole worker and runtime prefix are required.')
    root = Path(output_root).resolve() / uuid.uuid4().hex
    root.mkdir(parents=True)
    environment = os.environ.copy()
    environment['PATH'] = os.pathsep.join((str(prefix), str(prefix / 'Library/bin'),
                                           str(prefix / 'Scripts'), environment.get('PATH', '')))
    cases = []
    for case in CASES:
        name, operation, input_path, _, _ = case
        directory = root / name
        directory.mkdir()
        output = directory / 'output.obj'
        process = subprocess.run([str(worker), operation, str(input_path), str(output)],
                                 cwd=directory, env=environment, capture_output=True, text=True,
                                 encoding='utf-8', errors='replace', timeout=60)
        (directory / 'stdout.log').write_text(process.stdout, encoding='utf-8')
        (directory / 'stderr.log').write_text(process.stderr, encoding='utf-8')
        result_path = directory / 'results.json'
        measurement = check_case(case, json.loads(result_path.read_text(encoding='utf-8-sig')),
                                 process.returncode, output)
        cases.append({'id': name, 'operation': operation, 'inputSha256': sha(input_path),
                      'directory': str(directory), 'exitCode': process.returncode,
                      'resultSha256': sha(result_path),
                      'outputSha256': sha(output) if output.is_file() else None,
                      'measurement': measurement})
    report = {'schemaVersion': 1, 'kind': 'scientific.cgal-two-hole-fixed-suite',
              'createdAtUtc': datetime.now(timezone.utc).isoformat(),
              'corpusManifestSha256': corpus['manifestSha256'],
              'multiManifestSha256': fixture['manifestSha256'],
              'quadManifestSha256': quad['manifestSha256'],
              'triangleManifestSha256': triangle['manifestSha256'],
              'workerPath': str(worker), 'workerSha256': sha(worker),
              'workerSourceSha256': sha(SOURCE), 'metricsSourceSha256': sha(METRICS),
              'runtimePrefix': str(prefix), 'cases': cases, 'verdict': 'passed'}
    target = root / 'two-hole.json'
    with target.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, separators=(',', ':'))
    Path(str(target) + '.sha256').write_text(sha(target), encoding='utf-8')
    verify(target)
    return target, report


def verify(path):
    path = Path(path).resolve(strict=True)
    if sha(path) != Path(str(path) + '.sha256').read_text(encoding='utf-8').strip():
        raise ValueError('CGAL two-hole report hash mismatch.')
    report = json.loads(path.read_text(encoding='utf-8'))
    corpus, fixture, quad, triangle = verify_corpus(), verify_fixture(), verify_quad(), verify_triangle()
    if (report.get('schemaVersion') != 1 or report.get('kind') != 'scientific.cgal-two-hole-fixed-suite'
            or report.get('verdict') != 'passed'
            or report.get('corpusManifestSha256') != corpus['manifestSha256']
            or report.get('multiManifestSha256') != fixture['manifestSha256']
            or report.get('quadManifestSha256') != quad['manifestSha256']
            or report.get('triangleManifestSha256') != triangle['manifestSha256']
            or sha(Path(report['workerPath']).resolve(strict=True)) != report.get('workerSha256')
            or sha(SOURCE) != report.get('workerSourceSha256')
            or sha(METRICS) != report.get('metricsSourceSha256')
            or len(report.get('cases', [])) != len(CASES)):
        raise ValueError('CGAL two-hole suite identity changed.')
    for item, case in zip(report['cases'], CASES):
        directory = Path(item['directory']).resolve(strict=True)
        output, result_path = directory / 'output.obj', directory / 'results.json'
        if (item['id'] != case[0] or item['operation'] != case[1]
                or directory.parent != path.parent or directory.name != case[0]
                or item['inputSha256'] != sha(case[2]) or item['resultSha256'] != sha(result_path)
                or item['outputSha256'] != (sha(output) if output.is_file() else None)):
            raise ValueError('CGAL two-hole case artifact changed.')
        measured = check_case(case, json.loads(result_path.read_text(encoding='utf-8-sig')),
                              item['exitCode'], output)
        if measured != item['measurement']:
            raise ValueError('CGAL two-hole independent measurement changed.')
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
