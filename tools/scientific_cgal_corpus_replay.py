"""Replay authored CGAL fixtures against a specific local C++ worker build."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import uuid

from scientific_cgal_corpus import CORPUS, geometry, sha, verify_corpus


EXPECT = {'closed-tetra': ('succeeded', ''),
          'open-square': ('succeeded', ''),
          'degenerate-triangle': ('failed', 'Degenerate triangles or self-intersections'),
          'nonmanifold-edge': ('failed', 'not a readable manifold polygon mesh')}


def verify_case(item, entry, worker_hash):
    directory = Path(item['directory']).resolve(strict=True)
    result_path = directory / 'results.json'
    if sha(result_path) != item['resultSha256']:
        raise ValueError('CGAL corpus worker result hash mismatch.')
    result = json.loads(result_path.read_text(encoding='utf-8-sig'))
    state, reason = EXPECT[entry['id']]
    output = directory / 'output.obj'
    if (item['fixtureSha256'] != entry['sha256'] or item['workerSha256'] != worker_hash
            or result.get('recipeId') != 'cgal.validate' or result.get('state') != state
            or result.get('exitCode') != (0 if state == 'succeeded' else 2)
            or item.get('state') != state):
        raise ValueError('CGAL corpus worker state or identity mismatch.')
    if state == 'succeeded':
        if not output.is_file() or sha(output) != item.get('outputSha256'):
            raise ValueError('CGAL corpus output hash mismatch.')
        measured = geometry(output)
        expected = entry['geometry']
        if any(abs(measured[key] - expected[key]) > 1e-10 if key == 'signedVolume'
               else measured[key] != expected[key] for key in expected):
            raise ValueError('CGAL corpus output geometry changed.')
        if (result.get('after', {}).get('vertices') != expected['vertices']
                or result['after'].get('faces') != expected['faces']
                or result['after'].get('boundaryEdges') != expected['boundaryEdges']):
            raise ValueError('CGAL corpus worker statistics changed.')
    elif output.exists() or reason not in result.get('error', ''):
        raise ValueError('CGAL corpus rejected fixture produced output or wrong diagnostic.')


def run(worker, prefix, output_root):
    worker = Path(worker).resolve(strict=True)
    prefix = Path(prefix).resolve(strict=True)
    if worker.name.lower() != 'devshell_cgal_worker.exe' or not (prefix / 'Library/bin').is_dir():
        raise ValueError('A CGAL worker executable and matching runtime prefix are required.')
    corpus = verify_corpus()
    directory = Path(output_root).resolve() / uuid.uuid4().hex
    directory.mkdir(parents=True)
    environment = os.environ.copy()
    environment['PATH'] = os.pathsep.join((str(prefix), str(prefix / 'Library/bin'),
                                           str(prefix / 'Scripts'), environment.get('PATH', '')))
    cases = []
    for entry in corpus['fixtures']:
        case = directory / entry['id']
        case.mkdir()
        fixture = CORPUS / (entry['id'] + '.obj')
        process = subprocess.run([str(worker), 'validate', str(fixture), str(case / 'output.obj'),
                                  '0.25', '1', '1'], cwd=case, env=environment,
                                 capture_output=True, text=True, encoding='utf-8', errors='replace',
                                 timeout=30)
        (case / 'stdout.log').write_text(process.stdout, encoding='utf-8')
        (case / 'stderr.log').write_text(process.stderr, encoding='utf-8')
        result_path = case / 'results.json'
        item = {'id': entry['id'], 'directory': str(case), 'fixtureSha256': entry['sha256'],
                'workerSha256': sha(worker), 'exitCode': process.returncode,
                'resultSha256': sha(result_path),
                'state': json.loads(result_path.read_text(encoding='utf-8-sig'))['state']}
        if (case / 'output.obj').is_file():
            item['outputSha256'] = sha(case / 'output.obj')
        verify_case(item, entry, item['workerSha256'])
        cases.append(item)
    report = {'schemaVersion': 1, 'kind': 'scientific.cgal-corpus-replay',
              'createdAtUtc': datetime.now(timezone.utc).isoformat(),
              'corpusManifestSha256': corpus['manifestSha256'],
              'workerPath': str(worker), 'workerSha256': sha(worker),
              'runtimePrefix': str(prefix), 'cases': cases, 'verdict': 'passed'}
    report_path = directory / 'replay.json'
    with report_path.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, separators=(',', ':'))
    Path(str(report_path) + '.sha256').write_text(sha(report_path), encoding='utf-8')
    verify(report_path)
    return report_path, report


def verify(path):
    path = Path(path).resolve(strict=True)
    if sha(path) != Path(str(path) + '.sha256').read_text(encoding='utf-8').strip():
        raise ValueError('CGAL corpus replay report hash mismatch.')
    report = json.loads(path.read_text(encoding='utf-8'))
    corpus = verify_corpus()
    worker = Path(report['workerPath']).resolve(strict=True)
    if (report.get('schemaVersion') != 1 or report.get('kind') != 'scientific.cgal-corpus-replay'
            or report.get('verdict') != 'passed' or report.get('corpusManifestSha256') != corpus['manifestSha256']
            or sha(worker) != report.get('workerSha256')
            or [item.get('id') for item in report.get('cases', [])]
            != [item['id'] for item in corpus['fixtures']]):
        raise ValueError('CGAL corpus replay identity changed.')
    for item, entry in zip(report['cases'], corpus['fixtures']):
        if Path(item['directory']).resolve().parent != path.parent:
            raise ValueError('CGAL corpus replay case escaped its run directory.')
        verify_case(item, entry, report['workerSha256'])
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
        path, value = run(options.worker, options.prefix, options.output_root)
        print(json.dumps({'report': str(path), 'verdict': value['verdict'], 'cases': len(value['cases'])}))
    else:
        if not options.report:
            parser.error('verify requires report')
        value = verify(options.report)
        print(json.dumps({'report': str(Path(options.report).resolve()),
                          'verdict': value['verdict'], 'cases': len(value['cases'])}))
