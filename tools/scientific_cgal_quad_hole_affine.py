"""Seeded affine square-hole repair with inverse-mapped patch coverage."""
import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import subprocess
import uuid

from scientific_cgal_corpus import sha
from scientific_cgal_mesh_metrics import metrics, parse_obj
from scientific_cgal_metamorphic import parameters_for
from scientific_cgal_quad_fixture import FIXTURE_ROOT, verify as verify_fixture
from scientific_cgal_quad_hole_repair import check_patch


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'scientific/cgal-worker/hole_repair.cpp'
GENERATOR = ROOT / 'tools/scientific_cgal_metamorphic.py'
METRICS = ROOT / 'tools/scientific_cgal_mesh_metrics.py'
PATCH = ROOT / 'tools/scientific_cgal_quad_hole_repair.py'


def serialize(vertices, faces):
    lines = ['v ' + ' '.join(format(value, '.17g') for value in point) for point in vertices]
    lines.extend('f ' + ' '.join(str(index+1) for index in face) for face in faces)
    return ('\n'.join(lines) + '\n').encode('utf-8')


def transform(point, parameters):
    return tuple(parameters['scale'] * point[parameters['axes'][index]]
                 + parameters['translation'][index] for index in range(3))


def inverse(point, parameters):
    restored = [0.0, 0.0, 0.0]
    for index, original_axis in enumerate(parameters['axes']):
        restored[original_axis] = (point[index] - parameters['translation'][index]) / parameters['scale']
    return tuple(restored)


def generated(parameters, name):
    vertices, faces = parse_obj(FIXTURE_ROOT / name)
    return serialize([transform(point, parameters) for point in vertices], faces)


def normalized(output, parameters):
    vertices, faces = parse_obj(output)
    return serialize([inverse(point, parameters) for point in vertices], faces)


def check_case(item, parameters):
    directory = Path(item['directory']).resolve(strict=True)
    source, expected, output, normalized_path, result_path = (directory / name for name in
        ('input.obj', 'expected-closed.obj', 'output.obj', 'normalized.obj', 'results.json'))
    if (source.read_bytes() != generated(parameters, 'cube-one-quad-hole.obj')
            or expected.read_bytes() != generated(parameters, 'cube-closed.obj')
            or normalized_path.read_bytes() != normalized(output, parameters)
            or sha(source) != item['inputSha256'] or sha(expected) != item['expectedSha256']
            or sha(output) != item['outputSha256'] or sha(normalized_path) != item['normalizedSha256']
            or sha(result_path) != item['resultSha256']):
        raise ValueError('Affine square-hole repair artifact changed.')
    result = json.loads(result_path.read_text(encoding='utf-8-sig'))
    measured, canonical = metrics(output), metrics(expected)
    patch = check_patch(normalized_path)
    if (result.get('schemaVersion') != 1 or result.get('recipeId') != 'cgal.fill-quad-hole'
            or result.get('state') != 'succeeded' or result.get('exitCode') != 0
            or result.get('beforeFaces') != 10 or result.get('afterFaces') != 12
            or result.get('boundaryEdgesBefore') != 4 or result.get('patchFaces') != 2
            or measured['vertices'] != 8 or measured['faces'] != 12
            or measured['components'] != 1 or measured['boundaryEdges'] != 0
            or measured['boundaryLoops'] != 0 or measured['eulerCharacteristic'] != 2
            or measured['degenerateFaces'] != 0 or measured['maximumEdgeIncidence'] != 2
            or measured['bounds'] != canonical['bounds']
            or not math.isclose(measured['area'], 6 * parameters['scale']**2, abs_tol=1e-9)
            or not math.isclose(measured['signedVolume'], parameters['scale']**3, abs_tol=1e-9)
            or not math.isclose(result['signedVolumeAfter'], measured['signedVolume'], abs_tol=1e-9)
            or measured != item['metrics'] or patch != item['patch']):
        raise ValueError('Affine square-hole repair changed expected geometry.')


def run(worker, prefix, output_root, seed):
    fixture = verify_fixture()
    worker = Path(worker).resolve(strict=True)
    prefix = Path(prefix).resolve(strict=True)
    if worker.name.lower() != 'devshell_cgal_hole_repair.exe' or not (prefix / 'Library/bin').is_dir():
        raise ValueError('Native square-hole worker and runtime prefix are required.')
    root = Path(output_root).resolve() / uuid.uuid4().hex
    root.mkdir(parents=True)
    environment = os.environ.copy()
    environment['PATH'] = os.pathsep.join((str(prefix), str(prefix / 'Library/bin'),
                                           str(prefix / 'Scripts'), environment.get('PATH', '')))
    cases = []
    for index, parameters in enumerate(parameters_for(seed)):
        directory = root / f'case-{index}'
        directory.mkdir()
        source, expected, output, normalized_path = (directory / name for name in
            ('input.obj', 'expected-closed.obj', 'output.obj', 'normalized.obj'))
        source.write_bytes(generated(parameters, 'cube-one-quad-hole.obj'))
        expected.write_bytes(generated(parameters, 'cube-closed.obj'))
        process = subprocess.run([str(worker), 'fill-quad-hole', str(source), str(output)],
                                 cwd=directory, env=environment, capture_output=True, text=True,
                                 encoding='utf-8', errors='replace', timeout=60)
        (directory / 'stdout.log').write_text(process.stdout, encoding='utf-8')
        (directory / 'stderr.log').write_text(process.stderr, encoding='utf-8')
        if process.returncode:
            raise ValueError('Affine square-hole repair failed: ' + process.stderr[-300:])
        normalized_path.write_bytes(normalized(output, parameters))
        result_path = directory / 'results.json'
        item = {'name': f'case-{index}', 'parameters': parameters, 'directory': str(directory),
                'inputSha256': sha(source), 'expectedSha256': sha(expected),
                'outputSha256': sha(output), 'normalizedSha256': sha(normalized_path),
                'resultSha256': sha(result_path), 'metrics': metrics(output),
                'patch': check_patch(normalized_path)}
        check_case(item, parameters)
        cases.append(item)
    report = {'schemaVersion': 1, 'kind': 'scientific.cgal-quad-hole-affine',
              'createdAtUtc': datetime.now(timezone.utc).isoformat(), 'seed': seed,
              'quadManifestSha256': fixture['manifestSha256'],
              'generatorSha256': sha(GENERATOR), 'metricsSourceSha256': sha(METRICS),
              'patchSourceSha256': sha(PATCH), 'workerSourceSha256': sha(SOURCE),
              'workerPath': str(worker), 'workerSha256': sha(worker),
              'runtimePrefix': str(prefix), 'cases': cases, 'verdict': 'passed'}
    target = root / 'quad-hole-affine.json'
    with target.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, separators=(',', ':'))
    Path(str(target) + '.sha256').write_text(sha(target), encoding='utf-8')
    verify(target)
    return target, report


def verify(path):
    path = Path(path).resolve(strict=True)
    if sha(path) != Path(str(path) + '.sha256').read_text(encoding='utf-8').strip():
        raise ValueError('Affine square-hole report hash mismatch.')
    report = json.loads(path.read_text(encoding='utf-8'))
    fixture = verify_fixture()
    if (report.get('schemaVersion') != 1 or report.get('kind') != 'scientific.cgal-quad-hole-affine'
            or report.get('verdict') != 'passed'
            or report.get('quadManifestSha256') != fixture['manifestSha256']
            or report.get('generatorSha256') != sha(GENERATOR)
            or report.get('metricsSourceSha256') != sha(METRICS)
            or report.get('patchSourceSha256') != sha(PATCH)
            or report.get('workerSourceSha256') != sha(SOURCE)
            or sha(Path(report['workerPath']).resolve(strict=True)) != report.get('workerSha256')):
        raise ValueError('Affine square-hole report identity changed.')
    planned = parameters_for(report['seed'])
    if len(report.get('cases', [])) != len(planned):
        raise ValueError('Affine square-hole case count changed.')
    for index, (item, parameters) in enumerate(zip(report['cases'], planned)):
        directory = Path(item['directory']).resolve(strict=True)
        if (item['name'] != f'case-{index}' or item['parameters'] != parameters
                or directory.parent != path.parent or directory.name != item['name']):
            raise ValueError('Affine square-hole case identity changed.')
        check_case(item, parameters)
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
    else:
        if not options.report:
            parser.error('verify requires report')
        target, value = Path(options.report).resolve(), verify(options.report)
    print(json.dumps({'report': str(target), 'verdict': value['verdict'],
                      'cases': len(value['cases'])}))
