"""Fixed native remeshing replay with independent topology and volume gates."""
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
CASES = (
    ('closed-tetra-remesh', 'closed-tetra', '0.75', '1', '0', 'succeeded', ''),
    ('protected-open-square', 'open-square', '0.4', '1', '1', 'succeeded', ''),
    ('reject-degenerate', 'degenerate-triangle', '0.75', '1', '0', 'failed', 'Degenerate triangles'),
    ('reject-nonmanifold', 'nonmanifold-edge', '0.75', '1', '0', 'failed', 'not a readable manifold'),
    ('reject-budget', 'closed-tetra', '0.000001', '1', '0', 'failed', 'conservative laboratory budget'),
    ('reject-iterations', 'closed-tetra', '0.75', '0', '0', 'failed', 'Invalid remesh parameters'),
    ('reject-nonfinite', 'closed-tetra', 'nan', '1', '0', 'failed', 'Expected a finite number'),
)


def check_case(case, result, exit_code, output):
    name, fixture, _, _, _, state, reason = case
    if (result.get('schemaVersion') != 1 or result.get('runtimeId') != 'cgal-win-conda'
            or result.get('recipeId') != 'cgal.remesh' or result.get('state') != state
            or result.get('exitCode') != (0 if state == 'succeeded' else 2)
            or exit_code != result['exitCode']):
        raise ValueError(name + ': remesh worker state changed.')
    if state == 'failed':
        if output.exists() or reason not in result.get('error', ''):
            raise ValueError(name + ': rejected remesh wrote output or changed diagnostic.')
        return None
    if not output.is_file() or not result.get('versions', {}).get('cgal'):
        raise ValueError(name + ': remesh artifact or CGAL version is missing.')
    measured = metrics(output)
    if (measured['components'] != 1 or measured['maximumEdgeIncidence'] != 2
            or measured['degenerateFaces'] != 0 or measured['minimumEdgeLength'] <= 0
            or result.get('after', {}).get('vertices') != measured['vertices']
            or result['after'].get('faces') != measured['faces']
            or result['after'].get('boundaryEdges') != measured['boundaryEdges']):
        raise ValueError(name + ': remesh output topology changed.')
    if fixture == 'closed-tetra':
        if (measured['boundaryEdges'] != 0 or measured['boundaryLoops'] != 0
                or measured['eulerCharacteristic'] != 2
                or not math.isclose(measured['signedVolume'], 1/6, abs_tol=1e-8)):
            raise ValueError(name + ': closed tetra volume or Euler characteristic changed.')
    elif (measured['boundaryLoops'] != 1 or measured['eulerCharacteristic'] != 1
          or not math.isclose(measured['area'], 1, abs_tol=1e-8)
          or not math.isclose(measured['boundaryLength'], 4, abs_tol=1e-8)
          or any(not math.isclose(value, expected, abs_tol=1e-8)
                 for axis, expected_axis in zip(measured['bounds'], ((0, 1), (0, 1), (0, 0)))
                 for value, expected in zip(axis, expected_axis))):
        raise ValueError(name + ': protected square area, rim or bounds changed.')
    return measured


def run(worker, prefix, output_root):
    corpus = verify_corpus()
    fixtures = {item['id']: item for item in corpus['fixtures']}
    worker = Path(worker).resolve(strict=True)
    prefix = Path(prefix).resolve(strict=True)
    if worker.name.lower() != 'devshell_cgal_worker.exe' or not (prefix / 'Library/bin').is_dir():
        raise ValueError('CGAL mesh worker and runtime prefix are required.')
    root = Path(output_root).resolve() / uuid.uuid4().hex
    root.mkdir(parents=True)
    environment = os.environ.copy()
    environment['PATH'] = os.pathsep.join((str(prefix), str(prefix / 'Library/bin'),
                                           str(prefix / 'Scripts'), environment.get('PATH', '')))
    cases = []
    for case in CASES:
        name, fixture, target, iterations, boundary, _, _ = case
        directory = root / name
        directory.mkdir()
        output = directory / 'output.obj'
        source = CORPUS / (fixture + '.obj')
        process = subprocess.run([str(worker), 'remesh', str(source), str(output),
                                  target, iterations, boundary], cwd=directory, env=environment,
                                 capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=60)
        (directory / 'stdout.log').write_text(process.stdout, encoding='utf-8')
        (directory / 'stderr.log').write_text(process.stderr, encoding='utf-8')
        result_path = directory / 'results.json'
        result = json.loads(result_path.read_text(encoding='utf-8-sig'))
        measured = check_case(case, result, process.returncode, output)
        cases.append({'id': name, 'fixtureId': fixture, 'fixtureSha256': fixtures[fixture]['sha256'],
                      'directory': str(directory), 'resultSha256': sha(result_path),
                      'outputSha256': sha(output) if output.is_file() else None,
                      'exitCode': process.returncode, 'metrics': measured})
    report = {'schemaVersion': 1, 'kind': 'scientific.cgal-remesh-fixed-suite',
              'createdAtUtc': datetime.now(timezone.utc).isoformat(),
              'corpusManifestSha256': corpus['manifestSha256'],
              'workerPath': str(worker), 'workerSha256': sha(worker),
              'workerSourceSha256': sha(SOURCE), 'metricsSourceSha256': sha(METRICS),
              'runtimePrefix': str(prefix), 'cases': cases, 'verdict': 'passed'}
    target = root / 'remesh-suite.json'
    with target.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, separators=(',', ':'))
    Path(str(target) + '.sha256').write_text(sha(target), encoding='utf-8')
    verify(target)
    return target, report


def verify(path):
    path = Path(path).resolve(strict=True)
    if sha(path) != Path(str(path) + '.sha256').read_text(encoding='utf-8').strip():
        raise ValueError('CGAL remesh report hash mismatch.')
    report = json.loads(path.read_text(encoding='utf-8'))
    corpus = verify_corpus()
    fixtures = {item['id']: item for item in corpus['fixtures']}
    if (report.get('schemaVersion') != 1 or report.get('kind') != 'scientific.cgal-remesh-fixed-suite'
            or report.get('verdict') != 'passed' or report.get('corpusManifestSha256') != corpus['manifestSha256']
            or sha(Path(report['workerPath']).resolve(strict=True)) != report.get('workerSha256')
            or sha(SOURCE) != report.get('workerSourceSha256')
            or sha(METRICS) != report.get('metricsSourceSha256')
            or [item.get('id') for item in report.get('cases', [])] != [case[0] for case in CASES]):
        raise ValueError('CGAL remesh suite identity changed.')
    for case, item in zip(CASES, report['cases']):
        directory = Path(item['directory']).resolve(strict=True)
        output = directory / 'output.obj'
        result_path = directory / 'results.json'
        if (directory.parent != path.parent or directory.name != case[0]
                or item['fixtureId'] != case[1] or item['fixtureSha256'] != fixtures[case[1]]['sha256']
                or sha(result_path) != item['resultSha256']
                or (sha(output) if output.is_file() else None) != item['outputSha256']):
            raise ValueError('CGAL remesh case evidence changed.')
        measured = check_case(case, json.loads(result_path.read_text(encoding='utf-8-sig')),
                              item['exitCode'], output)
        if measured != item['metrics']:
            raise ValueError('CGAL remesh independently measured geometry changed.')
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
        print(json.dumps({'report': str(target), 'verdict': value['verdict'], 'cases': len(value['cases'])}))
    else:
        if not options.report:
            parser.error('verify requires report')
        value = verify(options.report)
        print(json.dumps({'report': str(Path(options.report).resolve()),
                          'verdict': value['verdict'], 'cases': len(value['cases'])}))
