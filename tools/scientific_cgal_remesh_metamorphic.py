"""Seeded affine covariance checks for bounded CGAL tetrahedron remeshing."""
import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import subprocess
import uuid

from scientific_cgal_corpus import sha, verify_corpus
from scientific_cgal_mesh_metrics import metrics
from scientific_cgal_metamorphic import generate, parameters_for


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'scientific/cgal-worker/main.cpp'
GENERATOR = ROOT / 'tools/scientific_cgal_metamorphic.py'
METRICS = ROOT / 'tools/scientific_cgal_mesh_metrics.py'
BASELINE = {'scale': 1.0, 'translation': [0, 0, 0], 'axes': [0, 1, 2]}


def close(actual, expected):
    return math.isclose(actual, expected, rel_tol=1e-8, abs_tol=1e-9)


def check_metrics(reference, measured, scale):
    for key in ('vertices', 'faces', 'edges', 'components', 'boundaryEdges',
                'boundaryLoops', 'maximumEdgeIncidence', 'degenerateFaces', 'eulerCharacteristic'):
        if measured[key] != reference[key]:
            raise ValueError('Affine CGAL remesh topology changed: ' + key)
    if (measured['components'] != 1 or measured['eulerCharacteristic'] != 2
            or measured['boundaryEdges'] != 0 or measured['degenerateFaces'] != 0):
        raise ValueError('Affine CGAL remesh is not a closed tetrahedral surface.')
    for key, power in (('area', 2), ('signedVolume', 3),
                       ('minimumEdgeLength', 1), ('maximumEdgeLength', 1)):
        if not close(measured[key], reference[key] * scale ** power):
            raise ValueError('Affine CGAL remesh scaling changed: ' + key)


def execute(worker, environment, root, name, parameters):
    directory = root / name
    directory.mkdir()
    source = directory / 'input.obj'
    output = directory / 'output.obj'
    source.write_bytes(generate(parameters))
    process = subprocess.run([str(worker), 'remesh', str(source), str(output),
                              format(0.75 * parameters['scale'], '.12g'), '1', '0'],
                             cwd=directory, env=environment, capture_output=True, text=True,
                             encoding='utf-8', errors='replace', timeout=60)
    (directory / 'stdout.log').write_text(process.stdout, encoding='utf-8')
    (directory / 'stderr.log').write_text(process.stderr, encoding='utf-8')
    result_path = directory / 'results.json'
    result = json.loads(result_path.read_text(encoding='utf-8-sig'))
    if (process.returncode != 0 or result.get('state') != 'succeeded'
            or result.get('recipeId') != 'cgal.remesh' or not output.is_file()):
        raise ValueError('Valid affine CGAL remesh failed: ' + str(result.get('error')))
    measured = metrics(output)
    if (result.get('after', {}).get('faces') != measured['faces']
            or result['after'].get('boundaryEdges') != measured['boundaryEdges']):
        raise ValueError('Affine CGAL remesh worker statistics changed.')
    return {'name': name, 'parameters': parameters, 'directory': str(directory),
            'inputSha256': sha(source), 'outputSha256': sha(output),
            'resultSha256': sha(result_path), 'metrics': measured}


def check_case(item, reference):
    directory = Path(item['directory']).resolve(strict=True)
    source = directory / 'input.obj'
    output = directory / 'output.obj'
    result_path = directory / 'results.json'
    if (source.read_bytes() != generate(item['parameters'])
            or sha(source) != item['inputSha256'] or sha(output) != item['outputSha256']
            or sha(result_path) != item['resultSha256'] or metrics(output) != item['metrics']):
        raise ValueError('Affine CGAL remesh evidence changed.')
    result = json.loads(result_path.read_text(encoding='utf-8-sig'))
    if (result.get('state') != 'succeeded' or result.get('recipeId') != 'cgal.remesh'
            or result.get('after', {}).get('faces') != item['metrics']['faces']):
        raise ValueError('Affine CGAL remesh saved result changed.')
    check_metrics(reference, item['metrics'], item['parameters']['scale'])


def run(worker, prefix, output_root, seed):
    corpus = verify_corpus()
    worker = Path(worker).resolve(strict=True)
    prefix = Path(prefix).resolve(strict=True)
    if worker.name.lower() != 'devshell_cgal_worker.exe' or not (prefix / 'Library/bin').is_dir():
        raise ValueError('CGAL mesh worker and runtime prefix are required.')
    root = Path(output_root).resolve() / uuid.uuid4().hex
    root.mkdir(parents=True)
    environment = os.environ.copy()
    environment['PATH'] = os.pathsep.join((str(prefix), str(prefix / 'Library/bin'),
                                           str(prefix / 'Scripts'), environment.get('PATH', '')))
    baseline = execute(worker, environment, root, 'baseline', BASELINE)
    check_metrics(baseline['metrics'], baseline['metrics'], 1)
    cases = []
    for index, parameters in enumerate(parameters_for(seed)):
        item = execute(worker, environment, root, f'case-{index}', parameters)
        check_case(item, baseline['metrics'])
        cases.append(item)
    report = {'schemaVersion': 1, 'kind': 'scientific.cgal-remesh-metamorphic-run',
              'createdAtUtc': datetime.now(timezone.utc).isoformat(), 'seed': seed,
              'corpusManifestSha256': corpus['manifestSha256'],
              'generatorSha256': sha(GENERATOR), 'metricsSourceSha256': sha(METRICS),
              'workerSourceSha256': sha(SOURCE), 'workerPath': str(worker),
              'workerSha256': sha(worker), 'runtimePrefix': str(prefix),
              'baseline': baseline, 'cases': cases, 'verdict': 'passed'}
    target = root / 'remesh-metamorphic.json'
    with target.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, separators=(',', ':'))
    Path(str(target) + '.sha256').write_text(sha(target), encoding='utf-8')
    verify(target)
    return target, report


def verify(path):
    path = Path(path).resolve(strict=True)
    if sha(path) != Path(str(path) + '.sha256').read_text(encoding='utf-8').strip():
        raise ValueError('CGAL remesh metamorphic report hash mismatch.')
    report = json.loads(path.read_text(encoding='utf-8'))
    corpus = verify_corpus()
    if (report.get('schemaVersion') != 1 or report.get('kind') != 'scientific.cgal-remesh-metamorphic-run'
            or report.get('verdict') != 'passed' or report.get('corpusManifestSha256') != corpus['manifestSha256']
            or report.get('generatorSha256') != sha(GENERATOR)
            or report.get('metricsSourceSha256') != sha(METRICS)
            or report.get('workerSourceSha256') != sha(SOURCE)
            or sha(Path(report['workerPath']).resolve(strict=True)) != report.get('workerSha256')):
        raise ValueError('CGAL remesh metamorphic identity changed.')
    baseline = report['baseline']
    if (baseline['name'] != 'baseline' or baseline['parameters'] != BASELINE
            or Path(baseline['directory']).resolve().parent != path.parent):
        raise ValueError('CGAL remesh baseline identity changed.')
    check_case(baseline, baseline['metrics'])
    planned = parameters_for(report['seed'])
    if len(report.get('cases', [])) != len(planned):
        raise ValueError('CGAL remesh metamorphic case count changed.')
    for index, (item, parameters) in enumerate(zip(report['cases'], planned)):
        directory = Path(item['directory']).resolve(strict=True)
        if (directory.parent != path.parent or directory.name != f'case-{index}'
                or item['name'] != f'case-{index}' or item['parameters'] != parameters):
            raise ValueError('CGAL remesh metamorphic case identity changed.')
        check_case(item, baseline['metrics'])
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
