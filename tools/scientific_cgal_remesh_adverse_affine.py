"""Seeded replay of the tetrahedron's low-fidelity remesh setting."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import uuid

from scientific_cgal_corpus import sha, verify_corpus
from scientific_cgal_mesh_metrics import metrics
from scientific_cgal_metamorphic import generate, parameters_for
from scientific_cgal_remesh_fidelity import classify
from scientific_cgal_surface_samples import surface_samples


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'scientific/cgal-worker/main.cpp'
GENERATOR = ROOT / 'tools/scientific_cgal_metamorphic.py'
METRICS = ROOT / 'tools/scientific_cgal_mesh_metrics.py'
SAMPLES = ROOT / 'tools/scientific_cgal_surface_samples.py'
TARGET_EDGE = 0.5
ITERATIONS = 2


def check_case(item, parameters):
    directory = Path(item['directory']).resolve(strict=True)
    source, output, result_path = (directory / name for name in
                                   ('input.obj', 'output.obj', 'results.json'))
    if (source.read_bytes() != generate(parameters) or sha(source) != item['inputSha256']
            or sha(output) != item['outputSha256'] or sha(result_path) != item['resultSha256']):
        raise ValueError('Adverse affine remesh evidence changed.')
    result = json.loads(result_path.read_text(encoding='utf-8-sig'))
    original, measured = metrics(source), metrics(output)
    if (result.get('recipeId') != 'cgal.remesh' or result.get('state') != 'succeeded'
            or result.get('exitCode') != 0 or result.get('after', {}).get('faces') != measured['faces']
            or result['after'].get('boundaryEdges') != measured['boundaryEdges']
            or item['inputMetrics'] != original or item['outputMetrics'] != measured
            or item['fidelity'] != classify(measured, original)
            or item['surfaceSamples'] != surface_samples(source, output)):
        raise ValueError('Adverse affine remesh measurement changed.')
    if (item['fidelity']['volumeEligible'] or item['fidelity']['relativeVolumeDrift'] < 0.2
            or item['surfaceSamples']['targetFacetSamplesToSource']['maximumDistance']
            / parameters['scale'] < 0.1):
        raise ValueError('Adverse affine remesh no longer reproduces the fidelity failure.')


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
        source, output = directory / 'input.obj', directory / 'output.obj'
        source.write_bytes(generate(parameters))
        process = subprocess.run([str(worker), 'remesh', str(source), str(output),
                                  format(TARGET_EDGE * parameters['scale'], '.12g'),
                                  str(ITERATIONS), '0'], cwd=directory, env=environment,
                                 capture_output=True, text=True, encoding='utf-8',
                                 errors='replace', timeout=60)
        (directory / 'stdout.log').write_text(process.stdout, encoding='utf-8')
        (directory / 'stderr.log').write_text(process.stderr, encoding='utf-8')
        if process.returncode:
            raise ValueError('Adverse affine remesh worker failed: ' + process.stderr[-300:])
        result_path = directory / 'results.json'
        original, measured = metrics(source), metrics(output)
        item = {'name': f'case-{index}', 'parameters': parameters, 'directory': str(directory),
                'inputSha256': sha(source), 'outputSha256': sha(output),
                'resultSha256': sha(result_path), 'inputMetrics': original,
                'outputMetrics': measured, 'fidelity': classify(measured, original),
                'surfaceSamples': surface_samples(source, output)}
        check_case(item, parameters)
        cases.append(item)
    report = {'schemaVersion': 1, 'kind': 'scientific.cgal-remesh-adverse-affine',
              'createdAtUtc': datetime.now(timezone.utc).isoformat(), 'seed': seed,
              'targetEdgeBase': TARGET_EDGE, 'iterations': ITERATIONS,
              'corpusManifestSha256': corpus['manifestSha256'],
              'generatorSha256': sha(GENERATOR), 'metricsSourceSha256': sha(METRICS),
              'samplesSourceSha256': sha(SAMPLES), 'workerSourceSha256': sha(SOURCE),
              'workerPath': str(worker), 'workerSha256': sha(worker),
              'runtimePrefix': str(prefix), 'cases': cases, 'verdict': 'reproduced'}
    target = root / 'adverse-affine.json'
    with target.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, separators=(',', ':'))
    Path(str(target) + '.sha256').write_text(sha(target), encoding='utf-8')
    verify(target)
    return target, report


def verify(path):
    path = Path(path).resolve(strict=True)
    if sha(path) != Path(str(path) + '.sha256').read_text(encoding='utf-8').strip():
        raise ValueError('Adverse affine remesh report hash mismatch.')
    report = json.loads(path.read_text(encoding='utf-8'))
    corpus = verify_corpus()
    if (report.get('schemaVersion') != 1 or report.get('kind') != 'scientific.cgal-remesh-adverse-affine'
            or report.get('verdict') != 'reproduced'
            or report.get('targetEdgeBase') != TARGET_EDGE or report.get('iterations') != ITERATIONS
            or report.get('corpusManifestSha256') != corpus['manifestSha256']
            or report.get('generatorSha256') != sha(GENERATOR)
            or report.get('metricsSourceSha256') != sha(METRICS)
            or report.get('samplesSourceSha256') != sha(SAMPLES)
            or report.get('workerSourceSha256') != sha(SOURCE)
            or sha(Path(report['workerPath']).resolve(strict=True)) != report.get('workerSha256')):
        raise ValueError('Adverse affine remesh report identity changed.')
    planned = parameters_for(report['seed'])
    if len(report.get('cases', [])) != len(planned):
        raise ValueError('Adverse affine remesh case count changed.')
    for index, (item, parameters) in enumerate(zip(report['cases'], planned)):
        directory = Path(item['directory']).resolve(strict=True)
        if (item['name'] != f'case-{index}' or item['parameters'] != parameters
                or directory.parent != path.parent or directory.name != item['name']):
            raise ValueError('Adverse affine remesh case identity changed.')
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
