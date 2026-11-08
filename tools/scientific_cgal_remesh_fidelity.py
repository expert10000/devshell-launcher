"""Measure and gate volume fidelity across bounded tetrahedron remesh settings."""
import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import subprocess
import uuid

from scientific_cgal_corpus import CORPUS, sha, verify_corpus
from scientific_cgal_mesh_metrics import metrics


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'scientific/cgal-worker/main.cpp'
METRICS = ROOT / 'tools/scientific_cgal_mesh_metrics.py'
SETTINGS = ((1.0, 1), (1.0, 2), (0.75, 1), (0.75, 2), (0.5, 1), (0.5, 2))
VOLUME_TOLERANCE = 1e-8


def classify(measured, original):
    if (measured['components'] != 1 or measured['boundaryEdges'] != 0
            or measured['boundaryLoops'] != 0 or measured['eulerCharacteristic'] != 2
            or measured['maximumEdgeIncidence'] != 2 or measured['degenerateFaces'] != 0):
        raise ValueError('Remesh fidelity profile found invalid closed topology.')
    drift = abs(measured['signedVolume'] - original['signedVolume'])
    return {'absoluteVolumeDrift': drift, 'relativeVolumeDrift': drift / abs(original['signedVolume']),
            'volumeEligible': math.isclose(measured['signedVolume'], original['signedVolume'],
                                           rel_tol=0, abs_tol=VOLUME_TOLERANCE)}


def check_case(item, setting, original):
    directory = Path(item['directory']).resolve(strict=True)
    output, result_path = directory / 'output.obj', directory / 'results.json'
    if sha(output) != item['outputSha256'] or sha(result_path) != item['resultSha256']:
        raise ValueError('Remesh fidelity profile artifact changed.')
    result = json.loads(result_path.read_text(encoding='utf-8-sig'))
    measured = metrics(output)
    if (result.get('recipeId') != 'cgal.remesh' or result.get('state') != 'succeeded'
            or result.get('exitCode') != 0 or result.get('after', {}).get('faces') != measured['faces']
            or result['after'].get('boundaryEdges') != measured['boundaryEdges']
            or measured != item['metrics'] or classify(measured, original) != item['fidelity']):
        raise ValueError('Remesh fidelity profile measurement changed.')
    if item['targetEdge'] != setting[0] or item['iterations'] != setting[1]:
        raise ValueError('Remesh fidelity profile setting changed.')


def run(worker, prefix, output_root):
    corpus = verify_corpus()
    worker = Path(worker).resolve(strict=True)
    prefix = Path(prefix).resolve(strict=True)
    original = metrics(CORPUS / 'closed-tetra.obj')
    root = Path(output_root).resolve() / uuid.uuid4().hex
    root.mkdir(parents=True)
    environment = os.environ.copy()
    environment['PATH'] = os.pathsep.join((str(prefix), str(prefix / 'Library/bin'),
                                           str(prefix / 'Scripts'), environment.get('PATH', '')))
    cases = []
    for target_edge, iterations in SETTINGS:
        name = f'edge-{format(target_edge, ".2f")}-iteration-{iterations}'
        directory = root / name
        directory.mkdir()
        output = directory / 'output.obj'
        process = subprocess.run([str(worker), 'remesh', str(CORPUS / 'closed-tetra.obj'),
                                  str(output), str(target_edge), str(iterations), '0'],
                                 cwd=directory, env=environment, capture_output=True, text=True,
                                 encoding='utf-8', errors='replace', timeout=60)
        (directory / 'stdout.log').write_text(process.stdout, encoding='utf-8')
        (directory / 'stderr.log').write_text(process.stderr, encoding='utf-8')
        if process.returncode:
            raise ValueError('Remesh fidelity profile worker failed: ' + process.stderr[-300:])
        result_path = directory / 'results.json'
        measured = metrics(output)
        item = {'name': name, 'directory': str(directory), 'targetEdge': target_edge,
                'iterations': iterations, 'outputSha256': sha(output),
                'resultSha256': sha(result_path), 'metrics': measured,
                'fidelity': classify(measured, original)}
        check_case(item, (target_edge, iterations), original)
        cases.append(item)
    report = {'schemaVersion': 1, 'kind': 'scientific.cgal-remesh-fidelity-profile',
              'createdAtUtc': datetime.now(timezone.utc).isoformat(),
              'corpusManifestSha256': corpus['manifestSha256'],
              'fixtureSha256': sha(CORPUS / 'closed-tetra.obj'),
              'metricsSourceSha256': sha(METRICS), 'workerSourceSha256': sha(SOURCE),
              'workerPath': str(worker), 'workerSha256': sha(worker),
              'runtimePrefix': str(prefix), 'settings': SETTINGS,
              'volumeTolerance': VOLUME_TOLERANCE, 'cases': cases,
              'eligibleCount': sum(item['fidelity']['volumeEligible'] for item in cases),
              'verdict': 'measured'}
    target = root / 'fidelity.json'
    with target.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, separators=(',', ':'))
    Path(str(target) + '.sha256').write_text(sha(target), encoding='utf-8')
    verify(target)
    return target, report


def verify(path):
    path = Path(path).resolve(strict=True)
    if sha(path) != Path(str(path) + '.sha256').read_text(encoding='utf-8').strip():
        raise ValueError('Remesh fidelity report hash mismatch.')
    report = json.loads(path.read_text(encoding='utf-8'))
    corpus = verify_corpus()
    original = metrics(CORPUS / 'closed-tetra.obj')
    if (report.get('schemaVersion') != 1 or report.get('kind') != 'scientific.cgal-remesh-fidelity-profile'
            or report.get('verdict') != 'measured' or report.get('corpusManifestSha256') != corpus['manifestSha256']
            or report.get('fixtureSha256') != sha(CORPUS / 'closed-tetra.obj')
            or report.get('metricsSourceSha256') != sha(METRICS)
            or report.get('workerSourceSha256') != sha(SOURCE)
            or sha(Path(report['workerPath']).resolve(strict=True)) != report.get('workerSha256')
            or report.get('settings') != [list(setting) for setting in SETTINGS]
            or report.get('volumeTolerance') != VOLUME_TOLERANCE
            or len(report.get('cases', [])) != len(SETTINGS)):
        raise ValueError('Remesh fidelity report identity changed.')
    for item, setting in zip(report['cases'], SETTINGS):
        directory = Path(item['directory']).resolve(strict=True)
        name = f'edge-{format(setting[0], ".2f")}-iteration-{setting[1]}'
        if directory.parent != path.parent or directory.name != name or item['name'] != name:
            raise ValueError('Remesh fidelity case identity changed.')
        check_case(item, setting, original)
    if report.get('eligibleCount') != sum(item['fidelity']['volumeEligible'] for item in report['cases']):
        raise ValueError('Remesh fidelity eligibility count changed.')
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
                      'eligible': value['eligibleCount'], 'cases': len(value['cases'])}))
