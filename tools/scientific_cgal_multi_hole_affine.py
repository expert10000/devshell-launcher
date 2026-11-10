"""Seeded affine two-hole repair with inverse-mapped dual-patch checks."""
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
from scientific_cgal_multi_fixture import FIXTURE_ROOT, verify as verify_fixture
from scientific_cgal_multi_hole_repair import check_two_patches
from scientific_cgal_quad_hole_affine import generated as closed_cube, inverse, serialize, transform


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'scientific/cgal-worker/hole_repair.cpp'
GENERATOR = ROOT / 'tools/scientific_cgal_metamorphic.py'
METRICS = ROOT / 'tools/scientific_cgal_mesh_metrics.py'
PATCH = ROOT / 'tools/scientific_cgal_multi_hole_repair.py'
TRANSFORM = ROOT / 'tools/scientific_cgal_quad_hole_affine.py'


def generated_open(parameters):
    vertices, faces = parse_obj(FIXTURE_ROOT / 'cube-two-square-holes.obj')
    return serialize([transform(point, parameters) for point in vertices], faces)


def normalized(output, parameters):
    vertices, faces = parse_obj(output)
    return serialize([inverse(point, parameters) for point in vertices], faces)


def check_case(item, parameters):
    directory = Path(item['directory']).resolve(strict=True)
    source, expected, output, normalized_path, result_path = (directory / name for name in
        ('input.obj', 'expected-closed.obj', 'output.obj', 'normalized.obj', 'results.json'))
    if (source.read_bytes() != generated_open(parameters)
            or expected.read_bytes() != closed_cube(parameters, 'cube-closed.obj')
            or normalized_path.read_bytes() != normalized(output, parameters)
            or sha(source) != item['inputSha256'] or sha(expected) != item['expectedSha256']
            or sha(output) != item['outputSha256'] or sha(normalized_path) != item['normalizedSha256']
            or sha(result_path) != item['resultSha256']):
        raise ValueError('Affine two-hole repair artifact changed.')
    result = json.loads(result_path.read_text(encoding='utf-8-sig'))
    measured, canonical = metrics(output), metrics(expected)
    patches = check_two_patches(normalized_path)
    scale = parameters['scale']
    if (result.get('schemaVersion') != 1 or result.get('recipeId') != 'cgal.fill-two-quad-holes'
            or result.get('state') != 'succeeded' or result.get('exitCode') != 0
            or result.get('beforeFaces') != 8 or result.get('afterFaces') != 12
            or result.get('boundaryLoopsBefore') != 2 or result.get('boundaryEdgesBefore') != 8
            or result.get('holesFilled') != 2 or result.get('patchFaceCounts') != [2, 2]
            or measured['vertices'] != 8 or measured['faces'] != 12
            or measured['components'] != 1 or measured['boundaryEdges'] != 0
            or measured['boundaryLoops'] != 0 or measured['eulerCharacteristic'] != 2
            or measured['degenerateFaces'] != 0 or measured['maximumEdgeIncidence'] != 2
            or measured['bounds'] != canonical['bounds']
            or not math.isclose(measured['area'], 6 * scale**2, abs_tol=1e-9)
            or not math.isclose(measured['signedVolume'], scale**3, abs_tol=1e-9)
            or not math.isclose(result['signedVolumeAfter'], measured['signedVolume'], abs_tol=1e-9)
            or item['metrics'] != measured or item['patches'] != patches):
        raise ValueError('Affine two-hole repair changed expected geometry.')


def run(worker, prefix, output_root, seed):
    fixture = verify_fixture()
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
    for index, parameters in enumerate(parameters_for(seed)):
        directory = root / f'case-{index}'
        directory.mkdir()
        source, expected, output, normalized_path = (directory / name for name in
            ('input.obj', 'expected-closed.obj', 'output.obj', 'normalized.obj'))
        source.write_bytes(generated_open(parameters))
        expected.write_bytes(closed_cube(parameters, 'cube-closed.obj'))
        process = subprocess.run([str(worker), 'fill-two-quad-holes', str(source), str(output)],
                                 cwd=directory, env=environment, capture_output=True, text=True,
                                 encoding='utf-8', errors='replace', timeout=60)
        (directory / 'stdout.log').write_text(process.stdout, encoding='utf-8')
        (directory / 'stderr.log').write_text(process.stderr, encoding='utf-8')
        if process.returncode:
            raise ValueError('Affine two-hole repair failed: ' + process.stderr[-300:])
        normalized_path.write_bytes(normalized(output, parameters))
        result_path = directory / 'results.json'
        item = {'name': f'case-{index}', 'parameters': parameters, 'directory': str(directory),
                'inputSha256': sha(source), 'expectedSha256': sha(expected),
                'outputSha256': sha(output), 'normalizedSha256': sha(normalized_path),
                'resultSha256': sha(result_path), 'metrics': metrics(output),
                'patches': check_two_patches(normalized_path)}
        check_case(item, parameters)
        cases.append(item)
    report = {'schemaVersion': 1, 'kind': 'scientific.cgal-two-hole-affine',
              'createdAtUtc': datetime.now(timezone.utc).isoformat(), 'seed': seed,
              'multiManifestSha256': fixture['manifestSha256'],
              'generatorSha256': sha(GENERATOR), 'metricsSourceSha256': sha(METRICS),
              'patchSourceSha256': sha(PATCH), 'transformSourceSha256': sha(TRANSFORM),
              'workerSourceSha256': sha(SOURCE), 'workerPath': str(worker),
              'workerSha256': sha(worker), 'runtimePrefix': str(prefix),
              'cases': cases, 'verdict': 'passed'}
    target = root / 'two-hole-affine.json'
    with target.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, separators=(',', ':'))
    Path(str(target) + '.sha256').write_text(sha(target), encoding='utf-8')
    verify(target)
    return target, report


def verify(path):
    path = Path(path).resolve(strict=True)
    if sha(path) != Path(str(path) + '.sha256').read_text(encoding='utf-8').strip():
        raise ValueError('Affine two-hole report hash mismatch.')
    report = json.loads(path.read_text(encoding='utf-8'))
    fixture = verify_fixture()
    if (report.get('schemaVersion') != 1 or report.get('kind') != 'scientific.cgal-two-hole-affine'
            or report.get('verdict') != 'passed'
            or report.get('multiManifestSha256') != fixture['manifestSha256']
            or report.get('generatorSha256') != sha(GENERATOR)
            or report.get('metricsSourceSha256') != sha(METRICS)
            or report.get('patchSourceSha256') != sha(PATCH)
            or report.get('transformSourceSha256') != sha(TRANSFORM)
            or report.get('workerSourceSha256') != sha(SOURCE)
            or sha(Path(report['workerPath']).resolve(strict=True)) != report.get('workerSha256')):
        raise ValueError('Affine two-hole report identity changed.')
    planned = parameters_for(report['seed'])
    if len(report.get('cases', [])) != len(planned):
        raise ValueError('Affine two-hole case count changed.')
    for index, (item, parameters) in enumerate(zip(report['cases'], planned)):
        directory = Path(item['directory']).resolve(strict=True)
        if (item['name'] != f'case-{index}' or item['parameters'] != parameters
                or directory.parent != path.parent or directory.name != item['name']):
            raise ValueError('Affine two-hole case identity changed.')
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
