"""Seeded affine checks for protected open-square remeshing and its rim."""
import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import subprocess
import uuid

from scientific_cgal_boundary import verify_unit_square_boundary
from scientific_cgal_corpus import CORPUS, sha, verify_corpus
from scientific_cgal_mesh_metrics import metrics, parse_obj
from scientific_cgal_metamorphic import parameters_for


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'scientific/cgal-worker/main.cpp'
GENERATOR = ROOT / 'tools/scientific_cgal_metamorphic.py'
METRICS = ROOT / 'tools/scientific_cgal_mesh_metrics.py'
BOUNDARY = ROOT / 'tools/scientific_cgal_boundary.py'


def transform(vertex, parameters):
    return tuple(parameters['scale'] * vertex[parameters['axes'][axis]]
                 + parameters['translation'][axis] for axis in range(3))


def inverse(vertex, parameters):
    result = [0.0] * 3
    for axis, source_axis in enumerate(parameters['axes']):
        result[source_axis] = (vertex[axis] - parameters['translation'][axis]) / parameters['scale']
    return result


def obj(vertices, faces):
    lines = ['v ' + ' '.join(format(value, '.17g') for value in vertex) for vertex in vertices]
    lines.extend('f ' + ' '.join(str(index + 1) for index in face) for face in faces)
    return ('\n'.join(lines) + '\n').encode('utf-8')


def expected_input(parameters):
    vertices, faces = parse_obj(CORPUS / 'open-square.obj')
    return obj([transform(vertex, parameters) for vertex in vertices], faces)


def check_geometry(measured, parameters, normalized):
    scale = parameters['scale']
    if (measured['components'] != 1 or measured['boundaryLoops'] != 1
            or measured['eulerCharacteristic'] != 1 or measured['maximumEdgeIncidence'] != 2
            or measured['degenerateFaces'] != 0 or measured['boundaryEdges'] != normalized['boundaryEdges']):
        raise ValueError('Affine protected remesh topology changed.')
    for key, expected in (('area', scale * scale), ('boundaryLength', 4 * scale)):
        if not math.isclose(measured[key], expected, rel_tol=1e-8, abs_tol=1e-8):
            raise ValueError('Affine protected remesh scaling changed: ' + key)
    corners = [transform(vertex, parameters) for vertex in parse_obj(CORPUS / 'open-square.obj')[0]]
    expected_bounds = [[min(vertex[axis] for vertex in corners),
                        max(vertex[axis] for vertex in corners)] for axis in range(3)]
    if any(not math.isclose(actual, expected, abs_tol=1e-8)
           for actual_axis, expected_axis in zip(measured['bounds'], expected_bounds)
           for actual, expected in zip(actual_axis, expected_axis)):
        raise ValueError('Affine protected remesh bounds changed.')


def check_case(item, parameters):
    directory = Path(item['directory']).resolve(strict=True)
    source, output, normalized_path = (directory / name for name in
                                       ('input.obj', 'output.obj', 'normalized.obj'))
    result_path = directory / 'results.json'
    if (source.read_bytes() != expected_input(parameters)
            or sha(source) != item['inputSha256'] or sha(output) != item['outputSha256']
            or sha(normalized_path) != item['normalizedSha256']
            or sha(result_path) != item['resultSha256']):
        raise ValueError('Affine protected remesh evidence changed.')
    vertices, faces = parse_obj(output)
    if normalized_path.read_bytes() != obj([inverse(vertex, parameters) for vertex in vertices], faces):
        raise ValueError('Affine protected remesh inverse geometry changed.')
    normalized = verify_unit_square_boundary(normalized_path)
    measured = metrics(output)
    result = json.loads(result_path.read_text(encoding='utf-8-sig'))
    if (result.get('recipeId') != 'cgal.remesh' or result.get('state') != 'succeeded'
            or result.get('exitCode') != 0 or result.get('after', {}).get('faces') != measured['faces']
            or result['after'].get('boundaryEdges') != measured['boundaryEdges']
            or normalized != item['boundary'] or measured != item['metrics']):
        raise ValueError('Affine protected remesh worker or measurements changed.')
    check_geometry(measured, parameters, normalized)


def run(worker, prefix, output_root, seed):
    corpus = verify_corpus()
    worker = Path(worker).resolve(strict=True)
    prefix = Path(prefix).resolve(strict=True)
    root = Path(output_root).resolve() / uuid.uuid4().hex
    root.mkdir(parents=True)
    environment = os.environ.copy()
    environment['PATH'] = os.pathsep.join((str(prefix), str(prefix / 'Library/bin'),
                                           str(prefix / 'Scripts'), environment.get('PATH', '')))
    cases = []
    for index, parameters in enumerate(parameters_for(seed)):
        directory = root / f'case-{index}'
        directory.mkdir()
        source, output, normalized_path = (directory / name for name in
                                           ('input.obj', 'output.obj', 'normalized.obj'))
        source.write_bytes(expected_input(parameters))
        process = subprocess.run([str(worker), 'remesh', str(source), str(output),
                                  format(0.4 * parameters['scale'], '.12g'), '1', '1'],
                                 cwd=directory, env=environment, capture_output=True, text=True,
                                 encoding='utf-8', errors='replace', timeout=60)
        (directory / 'stdout.log').write_text(process.stdout, encoding='utf-8')
        (directory / 'stderr.log').write_text(process.stderr, encoding='utf-8')
        if process.returncode:
            raise ValueError('Affine protected remesh failed: ' + process.stderr[-300:])
        vertices, faces = parse_obj(output)
        normalized_path.write_bytes(obj([inverse(vertex, parameters) for vertex in vertices], faces))
        result_path = directory / 'results.json'
        item = {'name': f'case-{index}', 'parameters': parameters, 'directory': str(directory),
                'inputSha256': sha(source), 'outputSha256': sha(output),
                'normalizedSha256': sha(normalized_path), 'resultSha256': sha(result_path),
                'metrics': metrics(output), 'boundary': verify_unit_square_boundary(normalized_path)}
        check_case(item, parameters)
        cases.append(item)
    report = {'schemaVersion': 1, 'kind': 'scientific.cgal-remesh-open-affine',
              'createdAtUtc': datetime.now(timezone.utc).isoformat(), 'seed': seed,
              'corpusManifestSha256': corpus['manifestSha256'],
              'generatorSha256': sha(GENERATOR), 'metricsSourceSha256': sha(METRICS),
              'boundarySourceSha256': sha(BOUNDARY), 'workerSourceSha256': sha(SOURCE),
              'workerPath': str(worker), 'workerSha256': sha(worker), 'runtimePrefix': str(prefix),
              'cases': cases, 'verdict': 'passed'}
    target = root / 'open-affine.json'
    with target.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, separators=(',', ':'))
    Path(str(target) + '.sha256').write_text(sha(target), encoding='utf-8')
    verify(target)
    return target, report


def verify(path):
    path = Path(path).resolve(strict=True)
    if sha(path) != Path(str(path) + '.sha256').read_text(encoding='utf-8').strip():
        raise ValueError('Affine protected remesh report hash mismatch.')
    report = json.loads(path.read_text(encoding='utf-8'))
    corpus = verify_corpus()
    if (report.get('schemaVersion') != 1 or report.get('kind') != 'scientific.cgal-remesh-open-affine'
            or report.get('verdict') != 'passed'
            or report.get('corpusManifestSha256') != corpus['manifestSha256']
            or report.get('generatorSha256') != sha(GENERATOR)
            or report.get('metricsSourceSha256') != sha(METRICS)
            or report.get('boundarySourceSha256') != sha(BOUNDARY)
            or report.get('workerSourceSha256') != sha(SOURCE)
            or sha(Path(report['workerPath']).resolve(strict=True)) != report.get('workerSha256')):
        raise ValueError('Affine protected remesh report identity changed.')
    parameters = parameters_for(report['seed'])
    if len(report.get('cases', [])) != len(parameters):
        raise ValueError('Affine protected remesh case count changed.')
    for index, (item, planned) in enumerate(zip(report['cases'], parameters)):
        directory = Path(item['directory']).resolve(strict=True)
        if (item['name'] != f'case-{index}' or item['parameters'] != planned
                or directory.parent != path.parent or directory.name != item['name']):
            raise ValueError('Affine protected remesh case identity changed.')
        check_case(item, planned)
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
    print(json.dumps({'report': str(target), 'verdict': value['verdict'], 'cases': len(value['cases'])}))
