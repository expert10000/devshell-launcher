"""Fixed AABB point-to-surface distance suite for the standalone CGAL query worker."""
import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import subprocess
import uuid

from scientific_cgal_corpus import CORPUS, sha, verify_corpus


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'scientific/cgal-worker/query.cpp'
CASES = (
    ('tetra-vertex', 'closed-tetra', ('0', '0', '0'), 0.0, (0.0, 0.0, 0.0), None),
    ('tetra-outside', 'closed-tetra', ('-1', '0', '0'), 1.0, (0.0, 0.0, 0.0), None),
    ('tetra-inside', 'closed-tetra', ('0.1', '0.1', '0.1'), 0.01, None, None),
    ('square-above', 'open-square', ('0.25', '0.75', '2'), 4.0, (0.25, 0.75, 0.0), None),
    ('square-outside', 'open-square', ('2', '0.5', '0'), 1.0, (1.0, 0.5, 0.0), None),
    ('reject-degenerate', 'degenerate-triangle', ('0', '0', '0'), None, None, 'degenerate triangle'),
    ('reject-nonmanifold', 'nonmanifold-edge', ('0', '0', '0'), None, None, 'triangle manifold'),
    ('reject-nonfinite', 'closed-tetra', ('nan', '0', '0'), None, None, 'finite'),
    ('reject-unbounded', 'closed-tetra', ('1000001', '0', '0'), None, None, '+/-1000000'),
)


def check_result(case, result, exit_code):
    name, _, point, squared, closest, error = case
    if result.get('schemaVersion') != 1:
        raise ValueError(name + ': query schema changed.')
    if error is not None:
        if exit_code != 2 or result.get('state') != 'failed' or error not in result.get('error', ''):
            raise ValueError(name + ': expected rejection changed.')
        return
    if exit_code != 0 or result.get('state') != 'succeeded':
        raise ValueError(name + ': valid query failed.')
    coordinates = tuple(float(value) for value in point)
    actual = result.get('closestPoint')
    if (len(actual or []) != 3 or len(result.get('query', [])) != 3
            or any(abs(a - b) > 1e-10 for a, b in zip(result['query'], coordinates))
            or not math.isclose(result.get('squaredDistance', float('nan')), squared, abs_tol=1e-10)
            or not math.isclose(result.get('distance', float('nan')) ** 2, squared, abs_tol=1e-10)
            or not math.isclose(sum((a - b) ** 2 for a, b in zip(actual, coordinates)), squared, abs_tol=1e-10)
            or (closest is not None and any(abs(a - b) > 1e-10 for a, b in zip(actual, closest)))):
        raise ValueError(name + ': AABB distance or closest point changed.')
    if result.get('faces') != (4 if case[1] == 'closed-tetra' else 2):
        raise ValueError(name + ': query mesh face count changed.')


def run(worker, prefix, output_root):
    corpus = verify_corpus()
    worker = Path(worker).resolve(strict=True)
    prefix = Path(prefix).resolve(strict=True)
    if worker.name.lower() != 'devshell_cgal_query.exe' or not (prefix / 'Library/bin').is_dir():
        raise ValueError('CGAL query worker and runtime prefix are required.')
    root = Path(output_root).resolve() / uuid.uuid4().hex
    root.mkdir(parents=True)
    environment = os.environ.copy()
    environment['PATH'] = os.pathsep.join((str(prefix), str(prefix / 'Library/bin'),
                                           str(prefix / 'Scripts'), environment.get('PATH', '')))
    cases = []
    fixtures = {item['id']: item for item in corpus['fixtures']}
    for case in CASES:
        name, fixture, point, _, _, _ = case
        directory = root / name
        directory.mkdir()
        process = subprocess.run([str(worker), str(CORPUS / (fixture + '.obj')), *point],
                                 cwd=directory, env=environment, capture_output=True, text=True,
                                 encoding='utf-8', errors='replace', timeout=30)
        (directory / 'stdout.log').write_text(process.stdout, encoding='utf-8')
        (directory / 'stderr.log').write_text(process.stderr, encoding='utf-8')
        result_path = directory / 'results.json'
        result = json.loads(result_path.read_text(encoding='utf-8'))
        check_result(case, result, process.returncode)
        cases.append({'id': name, 'fixtureId': fixture, 'fixtureSha256': fixtures[fixture]['sha256'],
                      'query': list(point), 'directory': str(directory),
                      'resultSha256': sha(result_path), 'exitCode': process.returncode,
                      'state': result['state']})
    report = {'schemaVersion': 1, 'kind': 'scientific.cgal-aabb-fixed-suite',
              'createdAtUtc': datetime.now(timezone.utc).isoformat(),
              'corpusManifestSha256': corpus['manifestSha256'],
              'workerPath': str(worker), 'workerSha256': sha(worker),
              'workerSourceSha256': sha(SOURCE), 'runtimePrefix': str(prefix),
              'cases': cases, 'verdict': 'passed'}
    target = root / 'query-suite.json'
    with target.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, separators=(',', ':'))
    Path(str(target) + '.sha256').write_text(sha(target), encoding='utf-8')
    verify(target)
    return target, report


def verify(path):
    path = Path(path).resolve(strict=True)
    if sha(path) != Path(str(path) + '.sha256').read_text(encoding='utf-8').strip():
        raise ValueError('CGAL query suite report hash mismatch.')
    report = json.loads(path.read_text(encoding='utf-8'))
    corpus = verify_corpus()
    if (report.get('schemaVersion') != 1 or report.get('kind') != 'scientific.cgal-aabb-fixed-suite'
            or report.get('verdict') != 'passed' or report.get('corpusManifestSha256') != corpus['manifestSha256']
            or sha(Path(report['workerPath']).resolve(strict=True)) != report.get('workerSha256')
            or sha(SOURCE) != report.get('workerSourceSha256')
            or [item.get('id') for item in report.get('cases', [])] != [case[0] for case in CASES]):
        raise ValueError('CGAL query suite identity changed.')
    fixtures = {item['id']: item for item in corpus['fixtures']}
    for case, item in zip(CASES, report['cases']):
        directory = Path(item['directory']).resolve(strict=True)
        if (directory.parent != path.parent or directory.name != case[0]
                or item['fixtureId'] != case[1] or item['fixtureSha256'] != fixtures[case[1]]['sha256']
                or item['query'] != list(case[2])):
            raise ValueError('CGAL query case provenance changed.')
        result_path = directory / 'results.json'
        if sha(result_path) != item['resultSha256']:
            raise ValueError('CGAL query result hash mismatch.')
        result = json.loads(result_path.read_text(encoding='utf-8'))
        if item['state'] != result.get('state'):
            raise ValueError('CGAL query saved state changed.')
        check_result(case, result, item['exitCode'])
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
