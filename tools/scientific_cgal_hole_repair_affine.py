"""Seeded affine triangular-hole fill with exact oriented-face replay."""
import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import subprocess
import uuid

from scientific_cgal_corpus import sha
from scientific_cgal_hole_repair import oriented_faces
from scientific_cgal_mesh_metrics import metrics, parse_obj
from scientific_cgal_metamorphic import generate, parameters_for
from scientific_cgal_repair_fixture import FIXTURE_ROOT, verify as verify_fixture


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'scientific/cgal-worker/hole_repair.cpp'
GENERATOR = ROOT / 'tools/scientific_cgal_metamorphic.py'
METRICS = ROOT / 'tools/scientific_cgal_mesh_metrics.py'


def open_mesh(parameters):
    vertices, faces = parse_obj(FIXTURE_ROOT / 'tetra-one-hole.obj')
    scale, axes, shift = parameters['scale'], parameters['axes'], parameters['translation']
    transformed = [tuple(scale * point[axes[index]] + shift[index] for index in range(3))
                   for point in vertices]
    lines = ['# Generated from authored tetra-one-hole.obj']
    lines.extend('v ' + ' '.join(format(value, '.12g') for value in point)
                 for point in transformed)
    lines.extend('f ' + ' '.join(str(index+1) for index in face) for face in faces)
    return ('\n'.join(lines) + '\n').encode('utf-8')


def check_case(item, parameters):
    directory = Path(item['directory']).resolve(strict=True)
    source, expected, output, result_path = (directory / name for name in
                                            ('input.obj', 'expected-closed.obj', 'output.obj', 'results.json'))
    if (source.read_bytes() != open_mesh(parameters)
            or expected.read_bytes() != generate(parameters)
            or sha(source) != item['inputSha256'] or sha(expected) != item['expectedSha256']
            or sha(output) != item['outputSha256'] or sha(result_path) != item['resultSha256']):
        raise ValueError('Affine hole-repair artifact changed.')
    result = json.loads(result_path.read_text(encoding='utf-8-sig'))
    measured = metrics(output)
    scale = parameters['scale']
    if (result.get('schemaVersion') != 1 or result.get('recipeId') != 'cgal.fill-one-hole'
            or result.get('state') != 'succeeded' or result.get('exitCode') != 0
            or result.get('beforeFaces') != 3 or result.get('afterFaces') != 4
            or result.get('boundaryEdgesBefore') != 3 or result.get('patchFaces') != 1
            or measured['components'] != 1 or measured['boundaryEdges'] != 0
            or measured['boundaryLoops'] != 0 or measured['eulerCharacteristic'] != 2
            or measured['degenerateFaces'] != 0 or measured['maximumEdgeIncidence'] != 2
            or not math.isclose(measured['signedVolume'], scale**3/6, abs_tol=1e-9)
            or not math.isclose(result['signedVolumeAfter'], measured['signedVolume'], abs_tol=1e-9)
            or oriented_faces(output) != oriented_faces(expected)
            or item['metrics'] != measured):
        raise ValueError('Affine hole repair changed expected closed geometry.')


def run(worker, prefix, output_root, seed):
    fixture = verify_fixture()
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
    for index, parameters in enumerate(parameters_for(seed)):
        directory = root / f'case-{index}'
        directory.mkdir()
        source, expected, output = (directory / name for name in
                                    ('input.obj', 'expected-closed.obj', 'output.obj'))
        source.write_bytes(open_mesh(parameters))
        expected.write_bytes(generate(parameters))
        process = subprocess.run([str(worker), 'fill-one-hole', str(source), str(output)],
                                 cwd=directory, env=environment, capture_output=True, text=True,
                                 encoding='utf-8', errors='replace', timeout=60)
        (directory / 'stdout.log').write_text(process.stdout, encoding='utf-8')
        (directory / 'stderr.log').write_text(process.stderr, encoding='utf-8')
        if process.returncode:
            raise ValueError('Affine hole repair failed: ' + process.stderr[-300:])
        result_path = directory / 'results.json'
        item = {'name': f'case-{index}', 'parameters': parameters, 'directory': str(directory),
                'inputSha256': sha(source), 'expectedSha256': sha(expected),
                'outputSha256': sha(output), 'resultSha256': sha(result_path),
                'metrics': metrics(output)}
        check_case(item, parameters)
        cases.append(item)
    report = {'schemaVersion': 1, 'kind': 'scientific.cgal-hole-repair-affine',
              'createdAtUtc': datetime.now(timezone.utc).isoformat(), 'seed': seed,
              'repairManifestSha256': fixture['manifestSha256'],
              'generatorSha256': sha(GENERATOR), 'metricsSourceSha256': sha(METRICS),
              'workerSourceSha256': sha(SOURCE), 'workerPath': str(worker),
              'workerSha256': sha(worker), 'runtimePrefix': str(prefix),
              'cases': cases, 'verdict': 'passed'}
    target = root / 'hole-repair-affine.json'
    with target.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, separators=(',', ':'))
    Path(str(target) + '.sha256').write_text(sha(target), encoding='utf-8')
    verify(target)
    return target, report


def verify(path):
    path = Path(path).resolve(strict=True)
    if sha(path) != Path(str(path) + '.sha256').read_text(encoding='utf-8').strip():
        raise ValueError('Affine hole-repair report hash mismatch.')
    report = json.loads(path.read_text(encoding='utf-8'))
    fixture = verify_fixture()
    if (report.get('schemaVersion') != 1 or report.get('kind') != 'scientific.cgal-hole-repair-affine'
            or report.get('verdict') != 'passed'
            or report.get('repairManifestSha256') != fixture['manifestSha256']
            or report.get('generatorSha256') != sha(GENERATOR)
            or report.get('metricsSourceSha256') != sha(METRICS)
            or report.get('workerSourceSha256') != sha(SOURCE)
            or sha(Path(report['workerPath']).resolve(strict=True)) != report.get('workerSha256')):
        raise ValueError('Affine hole-repair report identity changed.')
    planned = parameters_for(report['seed'])
    if len(report.get('cases', [])) != len(planned):
        raise ValueError('Affine hole-repair case count changed.')
    for index, (item, parameters) in enumerate(zip(report['cases'], planned)):
        directory = Path(item['directory']).resolve(strict=True)
        if (item['name'] != f'case-{index}' or item['parameters'] != parameters
                or directory.parent != path.parent or directory.name != item['name']):
            raise ValueError('Affine hole-repair case identity changed.')
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
